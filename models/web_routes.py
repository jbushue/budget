"""
Non-GraphQL HTTP routes for the web UI:

* /auth/*   — user accounts: first-run setup, sign in, invite sign-up,
              password changes and resets, and admin user management
              (see models/auth.py)
* /files/*  — Excel export / import / template, database backup / restore,
              transactions CSV
* the built web UI (web-ui/dist), when it has been built, so one server
  can serve everything (and the app can be installed as a PWA)

Access rules (applied to /graphql and /files/*):
* once an account exists → a valid session (cookie or "Authorization: Bearer")
  is required, from every device
* before any account exists → only requests from this computer are allowed
  (the web UI asks for the first, admin, account)
* database backup / restore → admins only
"""

from __future__ import annotations

import csv
import io
import mimetypes
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from functools import wraps

from flask import g, jsonify, request, send_file, send_from_directory

from models import auth
from models import database as db

COOKIE = "budget_session"
PROTECTED = ("/graphql", "/files/")
ADMIN_ONLY = ("/files/backup.db", "/files/restore")
LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}
DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web-ui", "dist")
SQLITE_MAGIC = b"SQLite format 3\x00"
TOO_MANY = "Too many failed attempts — wait 15 minutes and try again"

# Windows takes MIME types from the registry, where .js is often "text/plain" —
# browsers refuse to run module scripts served that way, leaving a blank page.
for _type, _ext in (("text/javascript", ".js"), ("text/javascript", ".mjs"), ("text/css", ".css"),
                    ("application/manifest+json", ".webmanifest"), ("image/svg+xml", ".svg"),
                    ("application/json", ".json"), ("image/png", ".png")):
    mimetypes.add_type(_type, _ext)


def client_is_local() -> bool:
    """True for requests from this computer (including through the local Vite proxy)."""
    if request.remote_addr not in LOCAL_ADDRS:
        return False
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() in LOCAL_ADDRS
    return True


def client_key() -> str:
    """Who to count failed sign-in attempts against."""
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "?")


def request_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def current_user() -> dict | None:
    if "user" not in g:
        g.user = auth.session_user(request_token())
    return g.user


def _fail(message: str, status: int, error: str | None = None):
    body = {"success": False, "message": message}
    if error:
        body["error"] = error
    return jsonify(body), status


def _signed_in(user: dict, message: str = "Signed in"):
    """Response that starts a session for ``user``."""
    token = auth.create_session(user["id"])
    resp = jsonify({"success": True, "message": message, "token": token, "user": user})
    resp.set_cookie(COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="Lax",
                    secure=request.is_secure)
    return resp


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return _fail("Please sign in", 401, "login_required")
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return _fail("Please sign in", 401, "login_required")
        if not user["is_admin"]:
            return _fail("Only an admin can do that", 403, "admin_required")
        return fn(*args, **kwargs)
    return wrapper


def throttled(fn):
    """Refuse clients with too many recent failed attempts."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if auth.throttled(client_key()):
            return _fail(TOO_MANY, 429)
        return fn(*args, **kwargs)
    return wrapper


def register(app, state: dict, lock) -> None:
    """Add the routes. ``state['manager']`` is the shared FinanceManager (replaced on restore)."""

    auth.migrate_legacy_password()

    @app.before_request
    def _guard():
        path = request.path
        if request.method == "OPTIONS" or not path.startswith(PROTECTED):
            return None
        if auth.has_users():
            user = current_user()
            if user is None:
                return _fail("Please sign in", 401, "login_required")
            if path in ADMIN_ONLY and not user["is_admin"]:
                return _fail("Only an admin can back up or restore the database", 403, "admin_required")
        elif not client_is_local():
            return _fail("Create the first account on the computer running the app, "
                         "then sign in here", 403, "setup_required")
        return None

    # ── Auth ──────────────────────────────────────────────────────────

    @app.route("/auth/status", methods=["GET"])
    def auth_status():
        user = current_user()
        return jsonify({"needs_setup": not auth.has_users(), "authenticated": user is not None,
                        "user": user, "local": client_is_local()})

    @app.route("/auth/setup", methods=["POST"])
    def auth_setup():
        """Create the first (admin) account — only from this computer, only once."""
        if not client_is_local():
            return _fail("Create the first account on the computer running the app", 403)
        data = request.get_json(silent=True) or {}
        try:
            user = auth.create_first_admin(data.get("username", ""), data.get("password", ""))
        except ValueError as e:
            return _fail(str(e), 400)
        return _signed_in(user, "Account created")

    @app.route("/auth/login", methods=["POST"])
    @throttled
    def auth_login():
        data = request.get_json(silent=True) or {}
        user = auth.authenticate(data.get("username", ""), data.get("password", ""))
        if user is None:
            auth.record_failure(client_key())
            return _fail("Wrong username or password", 401)
        auth.clear_failures(client_key())
        return _signed_in(user)

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
        auth.logout(request_token())
        resp = jsonify({"success": True})
        resp.delete_cookie(COOKIE)
        return resp

    @app.route("/auth/code/<code>", methods=["GET"])
    @throttled
    def auth_code(code):
        """What an invite / reset code is for, so the page can show the right form."""
        info = auth.inspect_code(code)
        if info is None:
            auth.record_failure(client_key())
            return _fail("That link isn't valid — it may have expired or already been used", 404)
        return jsonify({"success": True, **info})

    @app.route("/auth/register", methods=["POST"])
    @throttled
    def auth_register():
        """Create an account with an invite code."""
        data = request.get_json(silent=True) or {}
        if auth.inspect_code(data.get("code")) is None:
            auth.record_failure(client_key())
        try:
            user = auth.register(data.get("code", ""), data.get("username", ""), data.get("password", ""))
        except ValueError as e:
            return _fail(str(e), 400)
        return _signed_in(user, "Welcome!")

    @app.route("/auth/reset", methods=["POST"])
    @throttled
    def auth_reset():
        """Set a new password with a reset code from an admin."""
        data = request.get_json(silent=True) or {}
        if auth.inspect_code(data.get("code")) is None:
            auth.record_failure(client_key())
        try:
            user = auth.reset_password(data.get("code", ""), data.get("password", ""))
        except ValueError as e:
            return _fail(str(e), 400)
        return _signed_in(user, "Password changed")

    @app.route("/auth/password", methods=["POST"])
    @login_required
    def auth_password():
        """Change your own password; your other devices are signed out."""
        data = request.get_json(silent=True) or {}
        user = current_user()
        try:
            auth.change_password(user["id"], data.get("current_password", ""), data.get("new_password", ""))
        except ValueError as e:
            return _fail(str(e), 400)
        auth.logout_user(user["id"], keep_token=request_token())
        return jsonify({"success": True, "message": "Password changed — your other devices were signed out"})

    # Admin: users and invites

    @app.route("/auth/users", methods=["GET"])
    @admin_required
    def auth_users():
        return jsonify({"success": True, "users": auth.list_users(), "invites": auth.pending_invites()})

    @app.route("/auth/invites", methods=["POST"])
    @admin_required
    def auth_create_invite():
        data = request.get_json(silent=True) or {}
        code = auth.create_invite(current_user()["id"], bool(data.get("make_admin")),
                                  data.get("days") or auth.INVITE_DAYS)
        return jsonify({"success": True, "code": code})

    @app.route("/auth/invites/<int:invite_id>", methods=["DELETE"])
    @admin_required
    def auth_revoke_invite(invite_id):
        auth.revoke_invite(invite_id)
        return jsonify({"success": True})

    @app.route("/auth/users/<int:user_id>", methods=["PATCH"])
    @admin_required
    def auth_update_user(user_id):
        data = request.get_json(silent=True) or {}
        try:
            if "is_admin" in data:
                auth.set_admin(user_id, bool(data["is_admin"]))
        except ValueError as e:
            return _fail(str(e), 400)
        return jsonify({"success": True})

    @app.route("/auth/users/<int:user_id>", methods=["DELETE"])
    @admin_required
    def auth_delete_user(user_id):
        if user_id == current_user()["id"]:
            return _fail("You can't delete your own account", 400)
        try:
            auth.delete_user(user_id)
        except ValueError as e:
            return _fail(str(e), 400)
        return jsonify({"success": True})

    @app.route("/auth/users/<int:user_id>/reset", methods=["POST"])
    @admin_required
    def auth_reset_code(user_id):
        """A one-time code for someone who forgot their password (signs them out)."""
        try:
            code = auth.create_reset(user_id, current_user()["id"])
        except ValueError as e:
            return _fail(str(e), 400)
        auth.logout_user(user_id)
        return jsonify({"success": True, "code": code})

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
