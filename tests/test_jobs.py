"""Tests for background jobs: automatic backups, push notifications, SimpleFIN sync, maintenance."""

import io
import os
import urllib.error
from datetime import date, datetime, timedelta

import pytest

from models import backups, jobs, notify
from models.app_settings import get_settings, update_settings
from tests.test_accounts import PW, device, invite, setup_admin
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_phase4 import client, gql  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)


def state_and_lock(client):
    return client.application.config["BUDGET_STATE"], client.application.config["BUDGET_LOCK"]


class TestBackups:

    def test_run_list_prune(self, temp_db):  # noqa: F811
        t0 = datetime(2026, 1, 1, 3, 0)
        for i in range(5):
            info = backups.run_backup("auto", t0 + timedelta(days=i))
            os.utime(backups.path_for(info["name"]), (t0.timestamp() + i * 86400,) * 2)
        backups.run_backup("manual")
        assert len(backups.list_backups()) == 6
        removed = backups.prune(2)
        assert len(removed) == 3
        kinds = [b["kind"] for b in backups.list_backups()]
        assert kinds.count("auto") == 2 and kinds.count("manual") == 1  # manual ones are never pruned
        newest_auto = [b["name"] for b in backups.list_backups() if b["kind"] == "auto"]
        assert newest_auto == ["auto-20260105-030000.db", "auto-20260104-030000.db"]

    def test_names_cannot_escape_the_folder(self, temp_db):  # noqa: F811
        backups.run_backup("manual")
        for bad in ("../finance.db", "..\\finance.db", "sub/x.db", "x.txt", "", "finance.db"):
            assert backups.path_for(bad) is None

    def test_due_once_a_day_after_the_hour(self, temp_db):  # noqa: F811
        update_settings({"backup_hour": 3})
        assert not backups.backup_due(datetime(2026, 3, 1, 2, 59))
        assert backups.backup_due(datetime(2026, 3, 1, 3, 0))
        backups.run_scheduled(datetime(2026, 3, 1, 3, 0))
        assert not backups.backup_due(datetime(2026, 3, 1, 23, 0))
        assert backups.backup_due(datetime(2026, 3, 2, 3, 0))
        update_settings({"auto_backup": False})
        assert not backups.backup_due(datetime(2026, 3, 2, 3, 0))

    def test_http_admin_only(self, client):
        setup_admin(client)
        gql(client, 'mutation { createBank(name: "Before") { success } }')
        r = client.post("/files/backups")
        assert r.status_code == 200
        name = r.get_json()["backup"]["name"]
        listing = client.get("/files/backups").get_json()
        assert [b["name"] for b in listing["backups"]] == [name] and listing["auto_backup"] is True
        download = client.get(f"/files/backups/{name}")
        assert download.status_code == 200 and download.data[:15] == b"SQLite format 3"
        download.close()
        assert client.get("/files/backups/..%2Ffinance.db").status_code == 404

        gql(client, 'mutation { createBank(name: "After") { success } }')
        r = client.post(f"/files/backups/{name}/restore")
        assert r.status_code == 200, r.get_json()
        banks = [b["name"] for b in gql(client, "{ allBanks { name } }").get_json()["data"]["allBanks"]]
        assert banks == ["Before"]
        assert any(b["kind"] == "before-restore" for b in client.get("/files/backups").get_json()["backups"])
        assert client.delete(f"/files/backups/{name}").status_code == 200
        assert client.get(f"/files/backups/{name}").status_code == 404

        member = device(client)
        member.post("/auth/register", json={"code": invite(client), "username": "casey", "password": PW})
        for method, path in (("get", "/files/backups"), ("post", "/files/backups")):
            assert getattr(member, method)(path).status_code == 403


class FakeNtfy:
    """Stands in for urllib.request.urlopen and records what would have been sent."""

    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def __call__(self, req, timeout=None):
        if self.fail:
            raise self.fail
        self.sent.append({"url": req.full_url, "headers": dict(req.header_items()), "body": req.data.decode()})
        return io.BytesIO(b"{}")


@pytest.fixture
def ntfy(monkeypatch):
    fake = FakeNtfy()
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake)
    return fake


def _bill_due_tomorrow_and_short(api):
    soon = date.today() + timedelta(days=1)
    api(f'mutation {{ createBill(billName: "Big", amount: 50000, dueDate: {soon.day}) {{ success }} }}')


class TestPush:

    def test_send_headers_and_errors(self, temp_db, ntfy, monkeypatch):  # noqa: F811
        with pytest.raises(ValueError, match="topic URL"):
            notify.send("x", "y")
        update_settings({"ntfy_url": "https://ntfy.example/budget", "ntfy_token": "tk_secret"})
        notify.send("Rent is overdue 🚨", "pay it", "high", "warning", "https://b.example/bills")
        sent = ntfy.sent[0]
        assert sent["url"] == "https://ntfy.example/budget" and sent["body"] == "pay it"
        h = {k.lower(): v for k, v in sent["headers"].items()}
        assert h["title"].startswith("=?UTF-8?B?")  # emoji survives the Latin-1 header
        assert h["priority"] == "high" and h["click"] == "https://b.example/bills"
        assert h["authorization"] == "Bearer tk_secret"
        monkeypatch.setattr(notify.urllib.request, "urlopen", FakeNtfy(fail=urllib.error.URLError("no route")))
        with pytest.raises(OSError, match="Couldn't reach ntfy"):
            notify.send("x", "y")

    def test_settings_validation_and_secret(self, temp_db):  # noqa: F811
        from models.app_settings import public_settings
        with pytest.raises(ValueError):
            update_settings({"ntfy_url": "ntfy.sh/topic"})
        with pytest.raises(ValueError):
            update_settings({"push_min_severity": "info"})
        update_settings({"ntfy_token": "secret"})
        pub = public_settings()
        assert "ntfy_token" not in pub and pub["ntfy_token_set"] is True

    def test_new_alerts_pushed_once(self, api, ntfy):  # noqa: F811
        _bill_due_tomorrow_and_short(api)
        update_settings({"push_enabled": True, "ntfy_url": "https://ntfy.example/t",
                         "public_url": "https://budget.example"})
        first = notify.push_new_alerts(api.manager)
        assert first >= 1
        titles = [s["headers"].get("Title") for s in ntfy.sent]
        assert any("Big" in (t or "") for t in titles)
        assert all(s["headers"].get("Click", "").startswith("https://budget.example") for s in ntfy.sent)
        assert notify.push_new_alerts(api.manager) == 0  # nothing new
        update_settings({"push_enabled": False})
        assert notify.push_new_alerts(api.manager) == 0

    def test_severity_floor(self, api, ntfy):  # noqa: F811
        _bill_due_tomorrow_and_short(api)
        update_settings({"push_enabled": True, "ntfy_url": "https://ntfy.example/t", "push_min_severity": "danger"})
        notify.push_new_alerts(api.manager)
        assert all(s["headers"].get("Priority") == "high" for s in ntfy.sent)

    def test_daily_summary(self, api, ntfy):  # noqa: F811
        update_settings({"push_enabled": True, "ntfy_url": "https://ntfy.example/t", "push_daily_summary": True})
        morning = datetime.now().replace(hour=8)
        assert notify.summary_due(morning)
        notify.push_summary(api.manager, morning)
        assert "safe to spend" in ntfy.sent[-1]["headers"]["Title"].lower() or ntfy.sent[-1]["headers"]["Title"].startswith("=?")
        assert not notify.summary_due(morning)

    def test_graphql_test_push(self, api, ntfy):  # noqa: F811
        bad = api("mutation { sendTestPush { success message } }")["sendTestPush"]
        assert not bad["success"] and "topic URL" in bad["message"]
        update_settings({"ntfy_url": "https://ntfy.example/t"})
        ok = api("mutation { sendTestPush { success message } }")["sendTestPush"]
        assert ok["success"] and len(ntfy.sent) == 1


class TestScheduler:

    def test_maintenance_backup_and_isolation(self, client, monkeypatch):
        state, lock = state_and_lock(client)
        now = datetime.now().replace(hour=12)
        update_settings({"backup_hour": 0})
        ran = jobs.run_due_jobs(state, lock, now)
        assert "maintenance" in ran and "backup" in ran and not ran["backup"].startswith("failed")
        assert get_settings()["last_maintenance_date"] == now.date().isoformat()
        assert jobs.run_due_jobs(state, lock, now) == {}  # both done for today

        # A failing job is recorded and doesn't stop the others
        tomorrow = now + timedelta(days=1)
        monkeypatch.setattr(backups, "run_scheduled", lambda n: (_ for _ in ()).throw(OSError("disk full")))
        ran = jobs.run_due_jobs(state, lock, tomorrow)
        assert ran["backup"] == "failed: disk full" and "maintenance" in ran
        st = jobs.status()
        assert st["backup"]["ok"] is False and st["maintenance"]["ok"] is True

    def test_maintenance_rolls_bill_periods(self, client):
        state, lock = state_and_lock(client)
        manager = state["manager"]
        calls = []
        manager.auto_reset_periods = lambda: calls.append(1) or 2
        msg = jobs.run_maintenance(manager, datetime.now())
        assert calls and "2 bill period" in msg

    def test_job_status_query(self, client):
        state, lock = state_and_lock(client)
        jobs.run_due_jobs(state, lock, datetime.now().replace(hour=12))
        out = gql(client, "{ jobStatus }").get_json()["data"]["jobStatus"]
        assert "maintenance" in (out if isinstance(out, dict) else __import__("json").loads(out))


class TestSimplefinAutoSync:

    def test_due(self, temp_db):  # noqa: F811
        now = datetime(2026, 5, 1, 12, 0)
        assert not jobs.simplefin_due(now, get_settings())  # off by default
        update_settings({"simplefin_auto_sync_hours": 6})
        assert jobs.simplefin_due(now, get_settings())
        update_settings({"last_simplefin_sync": "2026-05-01T08:00:00"})
        assert not jobs.simplefin_due(now, get_settings())
        assert jobs.simplefin_due(datetime(2026, 5, 1, 14, 0), get_settings())
        with pytest.raises(ValueError):
            update_settings({"simplefin_auto_sync_hours": 5})

    def test_sync_runs_balances_and_transactions(self, client, monkeypatch):
        from types import SimpleNamespace
        from models import ledger, simplefin
        state, lock = state_and_lock(client)
        monkeypatch.setattr(simplefin, "get_simplefin_connection", lambda: {"access_url": "https://x"})
        monkeypatch.setattr(simplefin, "get_simplefin_mappings", lambda: {"acct": {}})
        monkeypatch.setattr(simplefin, "update_simplefin_last_sync", lambda: None)
        monkeypatch.setattr(simplefin.SimplefinClient, "sync_balances",
                            staticmethod(lambda url, maps, m: SimpleNamespace(accounts_updated=2, errors=[])))
        monkeypatch.setattr(ledger, "import_simplefin", lambda days: {"imported": 5, "duplicates": 0, "errors": []})
        update_settings({"simplefin_auto_sync_hours": 4})
        now = datetime(2026, 5, 1, 12, 0)
        ran = jobs.run_due_jobs(state, lock, now)
        assert ran["simplefin"].startswith("2 balance(s) updated, 5 new transaction(s)")
        s = get_settings()
        assert s["last_simplefin_sync"] == "2026-05-01T12:00:00" and "5 new transaction" in s["last_simplefin_result"]

    def test_not_connected_is_retried_next_interval(self, client, monkeypatch):
        from models import simplefin
        state, lock = state_and_lock(client)
        monkeypatch.setattr(simplefin, "get_simplefin_connection", lambda: None)
        update_settings({"simplefin_auto_sync_hours": 1})
        now = datetime(2026, 5, 1, 12, 0)
        assert jobs.run_due_jobs(state, lock, now)["simplefin"].startswith("failed")
        assert "simplefin" not in jobs.run_due_jobs(state, lock, now + timedelta(minutes=10))
