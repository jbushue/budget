"""
Non-GraphQL HTTP routes for the web UI:

* /auth/*   — password login (see models/auth.py) and the access rules
* /files/*  — Excel export / import / template, database backup / restore,
              transactions CSV
* the built web UI (web-ui/dist), when it has been built, so one server
  can serve everything (and the app can be installed as a PWA)

Access rules (applied to /graphql and /files/*):
* password set   → a valid session (cookie or "Authorization: Bearer") is required
* no password    → only requests from this computer are allowed
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

from flask import jsonify, request, send_file, send_from_directory

from models import auth
from models import database as db

COOKIE = "budget_session"
PROTECTED = ("/graphql", "/files/")
LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}
DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web-ui", "dist")
SQLITE_MAGIC = b"SQLite format 3\x00"


def client_is_local() -> bool:
    """True for requests from this computer (including through the local Vite proxy)."""
    if request.remote_addr not in LOCAL_ADDRS:
        return False
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() in LOCAL_ADDRS
    return True


def request_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def is_authenticated() -> bool:
    return auth.valid_session(request_token())


def register(app, state: dict, lock) -> None:
    """Add the routes. ``state['manager']`` is the shared FinanceManager (replaced on restore)."""

    @app.before_request
    def _guard():
        path = request.path
        if request.method == "OPTIONS" or not path.startswith(PROTECTED):
            return None
        if auth.password_set():
            if not is_authenticated():
                return jsonify({"error": "login_required", "message": "Please sign in"}), 401
        elif not client_is_local():
            return jsonify({"error": "password_required",
                            "message": "Set a password (Settings → Security) on the computer running the app "
                                       "to use it from other devices"}), 403
        return None

    # ── Auth ──────────────────────────────────────────────────────────

    @app.route("/auth/status", methods=["GET"])
    def auth_status():
        pw = auth.password_set()
        local = client_is_local()
        return jsonify({"password_set": pw, "authenticated": is_authenticated() if pw else local,
                        "local": local})

    @app.route("/auth/login", methods=["POST"])
    def auth_login():
        data = request.get_json(silent=True) or {}
        if not auth.password_set():
            return jsonify({"success": False, "message": "No password is set"}), 400
        if not auth.check_password(data.get("password", "")):
            return jsonify({"success": False, "message": "Wrong password"}), 401
        token = auth.create_session()
        resp = jsonify({"success": True, "token": token})
        resp.set_cookie(COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="Lax",
                        secure=request.is_secure)
        return resp

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
        auth.logout(request_token())
        resp = jsonify({"success": True})
        resp.delete_cookie(COOKIE)
        return resp

    @app.route("/auth/password", methods=["POST"])
    def auth_password():
        """Set / change / remove (empty new_password) the password."""
        if auth.password_set():
            if not is_authenticated():
                return jsonify({"success": False, "message": "Please sign in"}), 401
        elif not client_is_local():
            return jsonify({"success": False, "message": "Set the first password from the computer running the app"}), 403
        data = request.get_json(silent=True) or {}
        try:
            auth.set_password(data.get("new_password") or "", data.get("current_password"))
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        if data.get("new_password"):
            token = auth.create_session()
            resp = jsonify({"success": True, "message": "Password saved", "token": token})
            resp.set_cookie(COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="Lax",
                            secure=request.is_secure)
            return resp
        resp = jsonify({"success": True, "message": "Password removed — only this computer can open the app now"})
        resp.delete_cookie(COOKIE)
        return resp

    # ── Files ─────────────────────────────────────────────────────────

    def _stamp() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _send_temp(path: str, name: str, mimetype: str):
        with open(path, "rb") as f:
            data = io.BytesIO(f.read())
        try:
            os.remove(path)
        except OSError:
            pass
        return send_file(data, mimetype=mimetype, as_attachment=True, download_name=name)

    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @app.route("/files/export.xlsx", methods=["GET"])
    def files_export():
        from models.data_import_export import DataImportExport
        path = os.path.join(tempfile.mkdtemp(), "export.xlsx")
        with lock:
            out = DataImportExport(state["manager"]).export_current_data(path)
        if not out:
            return jsonify({"success": False, "message": "Excel support (openpyxl) isn't installed"}), 500
        return _send_temp(out, f"budget-export-{_stamp()}.xlsx", XLSX)

    @app.route("/files/template.xlsx", methods=["GET"])
    def files_template():
        from models.data_import_export import DataImportExport
        path = os.path.join(tempfile.mkdtemp(), "template.xlsx")
        out = DataImportExport(None).generate_template(path)
        if not out:
            return jsonify({"success": False, "message": "Excel support (openpyxl) isn't installed"}), 500
        return _send_temp(out, "budget-template.xlsx", XLSX)

    @app.route("/files/import", methods=["POST"])
    def files_import():
        from models.data_import_export import DataImportExport
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"success": False, "message": "Choose an Excel file"}), 400
        if not upload.filename.lower().endswith((".xlsx", ".xlsm")):
            return jsonify({"success": False, "message": "That isn't an Excel (.xlsx) file"}), 400
        tmp = os.path.join(tempfile.mkdtemp(), "import.xlsx")
        upload.save(tmp)
        try:
            with lock:
                manager = state["manager"]
                results = DataImportExport(manager).import_from_excel(tmp)
                created = sum(v for k, v in results.items() if k.endswith("_created") and isinstance(v, int))
                if created:
                    manager.save_to_database()
        finally:
            shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
        results["created_total"] = created if "error" not in results else 0
        results["message"] = results.get("error") or (
            f"Imported {created} items" + (f" ({len(results.get('warnings', []))} skipped or warnings)"
                                           if results.get("warnings") else ""))
        return jsonify(results), 200 if results.get("success", False) or created else 400

    @app.route("/files/backup.db", methods=["GET"])
    def files_backup():
        tmp = os.path.join(tempfile.mkdtemp(), "backup.db")
        with lock:
            src = sqlite3.connect(db.DB_PATH)
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        return _send_temp(tmp, f"budget-backup-{_stamp()}.db", "application/octet-stream")

    @app.route("/files/restore", methods=["POST"])
    def files_restore():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"success": False, "message": "Choose a backup file"}), 400
        tmpdir = tempfile.mkdtemp()
        tmp = os.path.join(tmpdir, "restore.db")
        upload.save(tmp)
        try:
            with open(tmp, "rb") as f:
                if f.read(16) != SQLITE_MAGIC:
                    return jsonify({"success": False, "message": "That isn't a budget backup file"}), 400
            conn = sqlite3.connect(tmp)
            try:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            finally:
                conn.close()
            if not {"banks", "bills", "income_sources"} <= tables or not ok:
                return jsonify({"success": False, "message": "That file isn't a valid budget backup"}), 400

            with lock:
                # Keep a copy of what's being replaced
                backups = os.path.join(os.path.dirname(db.DB_PATH), "backups")
                os.makedirs(backups, exist_ok=True)
                safety = os.path.join(backups, f"before-restore-{datetime.now():%Y%m%d-%H%M%S}.db")
                _sqlite_copy(db.DB_PATH, safety)
                db.engine.dispose()
                _sqlite_copy(tmp, db.DB_PATH)
                db.init_db()  # bring an older backup up to the current schema
                from models.finance_manager import FinanceManager
                fresh = FinanceManager([], [], [])
                fresh.load_from_database()
                state["manager"] = fresh
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return jsonify({"success": True, "message": "Backup restored",
                        "previous_saved_to": safety})

    @app.route("/files/transactions.csv", methods=["GET"])
    def files_transactions_csv():
        from models.ledger import all_transactions
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Date", "Description", "Amount", "Category", "Bank", "Account", "Bill", "Notes", "Source"])
        for t in all_transactions():
            w.writerow([t["date"], t["description"], f"{t['amount']:.2f}", t["category"] or "", t["bank_name"],
                        t["account_name"], t["matched_bill"] or "", t["notes"], t["source"]])
        data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
        return send_file(data, mimetype="text/csv", as_attachment=True,
                         download_name=f"transactions-{_stamp()}.csv")

    # ── Built web UI (optional) ───────────────────────────────────────

    if os.path.isdir(DIST_DIR):
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def web_ui(path):
            full = os.path.join(DIST_DIR, path)
            if path and os.path.isfile(full):
                resp = send_from_directory(DIST_DIR, path)
                if path == "sw.js":
                    resp.headers["Cache-Control"] = "no-cache"
                return resp
            if path.startswith(("graphql", "files/", "auth/", "health")):
                return jsonify({"error": "not found"}), 404
            return send_from_directory(DIST_DIR, "index.html")


def _sqlite_copy(src_path: str, dst_path: str) -> None:
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
