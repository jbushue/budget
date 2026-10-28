"""Tests for alerts, password login / access rules, file routes, and per-bill late fees."""

import io
import sqlite3
from datetime import date, timedelta

import pytest

from models import alerts, auth, ledger
from models import database as db
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

REMOTE = {"REMOTE_ADDR": "192.168.1.50"}


@pytest.fixture
def client(temp_db):  # noqa: F811
    from api_server import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    c.app = app
    return c


def gql(client, query, **kw):
    return client.post("/graphql", json={"query": query}, **kw)


class TestAlerts:

    def test_due_soon_low_balance_budget_and_dismiss(self, api):  # noqa: F811
        soon = date.today() + timedelta(days=1)
        api(f'mutation {{ createBill(billName: "Phone", amount: 80, dueDate: {soon.day}) {{ success }} }}')
        api('mutation { createBill(billName: "Big", amount: 5000, dueDate: 27) { success } }')
        # Spending, unlike a bill, can't be held back — it drags checking under the cushion
        api('mutation { updateSettings(changes: "{\\"everyday_weekly\\": 1400}") { success } }')
        ledger.set_budget("Dining", 10)
        ledger.add_transaction(date.today(), "Chipotle", -25, category="Dining")
        found = {a["key"].split(":")[0]: a for a in alerts.build_alerts(api.manager)}
        assert found["budget-over"]["severity"] == "warning"
        assert found["low"]["severity"] in ("warning", "danger")
        assert found["short"]["title"] == "Not enough to pay Big"
        if soon.day <= 28:  # monthly bills on the 29th-31st shift in short months
            assert found["due"]["title"].startswith("Phone due")
        alerts.dismiss(found["budget-over"]["key"])
        keys = [a["key"] for a in alerts.build_alerts(api.manager)]
        assert found["budget-over"]["key"] not in keys
        assert found["budget-over"]["key"] in [a["key"] for a in alerts.build_alerts(api.manager, include_dismissed=True)]

    def test_snooze_expires(self, temp_db):  # noqa: F811
        alerts.dismiss("x", days=2, today=date(2026, 1, 1))
        assert "x" in alerts._dismissed(date(2026, 1, 3))
        assert "x" not in alerts._dismissed(date(2026, 1, 4))

    def test_api_and_digest_text(self, api):  # noqa: F811
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 1) { success } }')
        out = api('{ alerts { key severity title detail link } digestPreview }')
        assert out["digestPreview"].startswith("Subject: ")
        assert "Safe to spend" in out["digestPreview"]
        bad = api('mutation { sendDigestEmail { success message } }')["sendDigestEmail"]
        assert not bad["success"] and "SMTP" in bad["message"]


class TestPasswords:

    def test_hash_roundtrip(self):
        h = auth.hash_password("correct horse")
        assert h.startswith("pbkdf2_sha256$") and auth.verify_password("correct horse", h)
        assert not auth.verify_password("wrong", h) and not auth.verify_password("x", "garbage")

    def test_set_change_remove(self, temp_db):  # noqa: F811
        with pytest.raises(ValueError):
            auth.set_password("short")
        auth.set_password("longenough1")
        assert auth.password_set() and auth.check_password("longenough1")
        with pytest.raises(ValueError):
            auth.set_password("another-one", "wrong")
        token = auth.create_session()
        assert auth.valid_session(token)
        auth.set_password("another-one", "longenough1")
        assert not auth.valid_session(token)  # changing the password signs everyone out
        auth.set_password("", "another-one")
        assert not auth.password_set()


class TestAccessRules:

    def test_no_password_local_only(self, client):
        assert gql(client, "{ allBanks { name } }").status_code == 200
        r = gql(client, "{ allBanks { name } }", environ_base=REMOTE)
        assert r.status_code == 403 and r.get_json()["error"] == "password_required"
        # Through the Vite proxy: loopback address, real client in X-Forwarded-For
        r = gql(client, "{ allBanks { name } }", headers={"X-Forwarded-For": "192.168.1.50"})
        assert r.status_code == 403
        assert client.get("/auth/status", environ_base=REMOTE).get_json() == {
            "password_set": False, "authenticated": False, "local": False}
        # The first password must be set from this computer
        assert client.post("/auth/password", json={"new_password": "longenough1"},
                           environ_base=REMOTE).status_code == 403

    def test_password_login_flow(self, client):
        r = client.post("/auth/password", json={"new_password": "longenough1"})
        assert r.status_code == 200 and r.get_json()["success"]
        other = client.application.test_client()  # a second device, no cookie
        assert gql(other, "{ allBanks { name } }", environ_base=REMOTE).status_code == 401
        assert other.post("/auth/login", json={"password": "nope"}, environ_base=REMOTE).status_code == 401
        r = other.post("/auth/login", json={"password": "longenough1"}, environ_base=REMOTE)
        token = r.get_json()["token"]
        assert gql(other, "{ allBanks { name } }", environ_base=REMOTE).status_code == 200  # cookie
        bearer = client.application.test_client()
        assert gql(bearer, "{ allBanks { name } }", environ_base=REMOTE,
                   headers={"Authorization": f"Bearer {token}"}).status_code == 200
        assert other.get("/auth/status", environ_base=REMOTE).get_json()["authenticated"]
        other.post("/auth/logout", environ_base=REMOTE)
        assert gql(other, "{ allBanks { name } }", environ_base=REMOTE).status_code == 401
        # Health stays open for monitoring
        assert client.get("/health", environ_base=REMOTE).status_code == 200

    def test_graphql_cannot_set_password_hash(self, client):
        r = gql(client, 'mutation { updateSettings(changes: "{\\"password_hash\\": \\"x\\"}") { success } }')
        assert r.get_json()["data"]["updateSettings"]["success"] is False
        settings = gql(client, "{ settings }").get_json()["data"]["settings"]
        assert "password_hash" not in settings and "smtp_password\"" not in settings


class TestFiles:

    def test_backup_and_restore(self, client):
        gql(client, 'mutation { createBank(name: "Before") { success } }')
        backup = client.get("/files/backup.db")
        assert backup.status_code == 200 and backup.data.startswith(b"SQLite format 3\x00")

        gql(client, 'mutation { createBank(name: "After") { success } }')
        names = lambda: {b["name"] for b in gql(client, "{ allBanks { name } }").get_json()["data"]["allBanks"]}  # noqa: E731
        assert names() == {"Before", "After"}

        r = client.post("/files/restore", data={"file": (io.BytesIO(backup.data), "backup.db")},
                        content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        assert names() == {"Before"}
        # The replaced database was kept
        saved = sqlite3.connect(r.get_json()["previous_saved_to"])
        assert {n for (n,) in saved.execute("SELECT name FROM banks")} == {"Before", "After"}
        saved.close()

    def test_restore_rejects_junk(self, client):
        r = client.post("/files/restore", data={"file": (io.BytesIO(b"hello"), "x.db")},
                        content_type="multipart/form-data")
        assert r.status_code == 400

    def test_excel_roundtrip_and_csv(self, client):
        pytest.importorskip("openpyxl")
        gql(client, 'mutation { createBank(name: "B") { success } }')
        gql(client, 'mutation { createBill(billName: "Rent", amount: 1000, dueDate: 1) { success } }')
        exported = client.get("/files/export.xlsx")
        assert exported.status_code == 200 and exported.data[:2] == b"PK"
        assert client.get("/files/template.xlsx").data[:2] == b"PK"
        # Importing the same data again skips everything (nothing duplicated)
        r = client.post("/files/import", data={"file": (io.BytesIO(exported.data), "e.xlsx")},
                        content_type="multipart/form-data")
        assert r.get_json()["created_total"] == 0
        ledger.add_transaction(date(2026, 1, 2), "Kroger", -12.5, category="Groceries")
        csv_text = client.get("/files/transactions.csv").data.decode("utf-8-sig")
        assert "2026-01-02,Kroger,-12.50,Groceries" in csv_text

    def test_files_are_protected(self, client):
        assert client.get("/files/backup.db", environ_base=REMOTE).status_code == 403


class TestLateFee:

    def test_bill_late_fee_saved(self, api):  # noqa: F811
        api('mutation { createBill(billName: "Water", amount: 50, dueDate: 3, lateFee: 15) { success } }')
        assert api('{ allBills { billName lateFee } }')["allBills"] == [{"billName": "Water", "lateFee": 15}]
        api('mutation { updateBill(billName: "Water", lateFee: -1) { success } }')
        assert api.manager.bills[0].late_fee is None
        api('mutation { updateBill(billName: "Water", lateFee: 9) { success } }')
        from models.finance_manager import FinanceManager
        fresh = FinanceManager([], [], [])
        fresh.load_from_database()
        assert next(b for b in fresh.bills if b.bill_name == "Water").late_fee == 9


class TestBuiltUi:

    def test_assets_served_with_browser_mime_types(self, client, tmp_path, monkeypatch):
        """The built UI's JS must not be served as text/plain (Windows registry default)."""
        import mimetypes
        from models import web_routes
        assert mimetypes.guess_type("x.js")[0] == "text/javascript"
        assert mimetypes.guess_type("x.css")[0] == "text/css"
        assert mimetypes.guess_type("x.webmanifest")[0] == "application/manifest+json"
        assert web_routes.DIST_DIR.endswith("dist")
