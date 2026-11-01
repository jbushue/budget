"""Tests for the activity history and signed-in device management."""

import json
from datetime import datetime, timedelta

from models import activity, auth
from tests.test_accounts import PW, REMOTE, device, invite, login, setup_admin
from tests.test_phase4 import client, gql  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


def history(client, **kw):
    out = gql(client, "{ activity(limit: 50) }", **kw).get_json()["data"]["activity"]
    return json.loads(out) if isinstance(out, str) else out


class TestDescribe:

    def test_humanize_and_describe(self):
        assert activity.humanize("createBill") == "Create bill"
        assert activity.humanize("markBillPaid") == "Mark bill paid"
        assert activity.describe({"billName": "Rent", "amount": 1200}) == "Rent · $1,200.00"
        assert activity.describe({"bankName": "Chase", "accountName": "Checking", "newBalance": 50.5})             == "Chase · Checking · new balance $50.50"
        text = activity.describe({"changes": json.dumps({"cushion": 300, "smtp_password": "hunter2"})})
        assert "cushion" in text and "1 secret value(s)" in text and "hunter2" not in text
        assert "abc" not in activity.describe({"setupToken": "abc", "name": "x"})

    def test_prune(self, temp_db):  # noqa: F811
        old = datetime.now() - timedelta(days=400)
        activity.log("Old thing", at=old)
        activity.log("New thing")
        assert activity.prune() == 1
        assert [a["action"] for a in activity.recent()] == ["New thing"]


class TestHistory:

    def test_mutations_and_account_events_are_recorded(self, client):
        setup_admin(client)
        gql(client, 'mutation { createBank(name: "Chase") { success } }')
        gql(client, 'mutation { createBill(billName: "Rent", amount: 1200, dueDate: 1) { success } }')
        gql(client, "{ allBanks { name } }")  # queries aren't recorded
        gql(client, 'mutation { dismissAlert(key: "x") { success } }')  # housekeeping isn't either
        bad = gql(client, 'mutation { deleteBill(billName: "Nope") { success } }')
        assert bad.status_code == 200
        member = device(client)
        member.post("/auth/register", json={"code": invite(client), "username": "casey", "password": PW})
        gql(member, 'mutation { updateSettings(changes: "{\\"cushion\\": 300}") { success } }')

        rows = history(client)
        actions = [(r["username"], r["action"]) for r in rows]
        assert ("jordan", "Create bank") in actions and ("jordan", "Create bill") in actions
        assert ("jordan", "Created an invite link") in actions and ("casey", "Joined with an invite") in actions
        assert ("casey", "Update settings") in actions
        assert not any(a == "Dismiss alert" for _, a in actions)
        assert not any(a == "Delete bill" for _, a in actions)  # it failed
        rent = next(r for r in rows if r["action"] == "Create bill")
        assert rent["detail"] == "Rent · $1,200.00"
        # Paging and filtering
        newest = rows[0]["id"]
        older = json.loads(json.dumps(activity.recent(50, before_id=newest)))
        assert all(r["id"] < newest for r in older)
        assert all(r["username"] == "casey" for r in activity.recent(50, username="casey"))

    def test_named_operation_with_variables(self, client):
        setup_admin(client)
        q = ("query Q { allBanks { name } } "
             "mutation M($n: String!) { createBank(name: $n) { success } }")
        r = client.post("/graphql", json={"query": q, "variables": {"n": "Ally"}, "operationName": "M"})
        assert r.get_json()["data"]["createBank"]["success"]
        assert any(row["action"] == "Create bank" and "Ally" in row["detail"] for row in history(client))


class TestSessions:

    def test_list_and_sign_out_devices(self, client):
        setup_admin(client)
        laptop = device(client)
        login(laptop, "jordan", headers={"User-Agent": CHROME_WIN})
        phone = device(client)
        login(phone, "jordan", headers={"User-Agent": SAFARI_IPHONE})

        sessions = laptop.get("/auth/sessions").get_json()["sessions"]
        assert len(sessions) == 3
        assert sessions[0]["current"] and sessions[0]["device"] == "Chrome on Windows"
        assert {s["device"] for s in sessions} >= {"Chrome on Windows", "Safari on iPhone"}
        assert next(s for s in sessions if s["device"] == "Safari on iPhone")["ip"] == REMOTE["REMOTE_ADDR"]

        phone_id = next(s["id"] for s in sessions if s["device"] == "Safari on iPhone")
        assert laptop.delete(f"/auth/sessions/{phone_id}").status_code == 200
        assert gql(phone, "{ allBanks { name } }").status_code == 401
        assert laptop.delete("/auth/sessions/notarealid0000").status_code == 404

        # Someone else's session can't be revoked by id
        member = device(client)
        member.post("/auth/register", json={"code": invite(client), "username": "casey", "password": PW})
        mine = laptop.get("/auth/sessions").get_json()["sessions"][0]["id"]
        assert member.delete(f"/auth/sessions/{mine}").status_code == 404

        assert laptop.delete("/auth/sessions/others").status_code == 200
        assert gql(client, "{ allBanks { name } }").status_code == 401  # the setup session
        assert gql(laptop, "{ allBanks { name } }").status_code == 200
        assert [s["current"] for s in laptop.get("/auth/sessions").get_json()["sessions"]] == [True]

    def test_device_names(self):
        assert auth.describe_device(CHROME_WIN) == "Chrome on Windows"
        assert auth.describe_device(SAFARI_IPHONE) == "Safari on iPhone"
        assert auth.describe_device("curl/8.4.0") == "curl/8.4.0"
        assert auth.describe_device("") == "Unknown device"
        assert auth.describe_device("seed-script") == "seed-script"
        firefox_linux = "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
        assert auth.describe_device(firefox_linux) == "Firefox on Linux"
        edge = CHROME_WIN + " Edg/130.0"
        assert auth.describe_device(edge) == "Edge on Windows"

    def test_last_seen_updates(self, client, monkeypatch):
        setup_admin(client)
        token = client.get("/auth/status")  # noqa: F841
        laptop = device(client)
        r = login(laptop, "jordan")
        tok = r.get_json()["token"]
        later = datetime.now() + timedelta(minutes=10)
        monkeypatch.setattr(auth, "datetime", type("D", (), {"now": staticmethod(lambda: later)}))
        auth.session_user(tok)
        monkeypatch.undo()
        seen = next(s for s in auth.list_sessions(1, tok) if s["current"])["last_seen"]
        assert seen.startswith(later.date().isoformat()) and seen[11:16] == later.strftime("%H:%M")

    def test_unsent_variables_are_not_logged(self, client):
        setup_admin(client)
        client.post("/graphql", json={"query": 'mutation { createBill(billName: "Water", amount: 40, dueDate: 5) { success } }'})
        q = "mutation M($b: String!, $a: Float, $f: String) { updateBill(billName: $b, amount: $a, frequency: $f) { success } }"
        client.post("/graphql", json={"query": q, "variables": {"b": "Water", "f": "monthly"}, "operationName": "M"})
        rows = [r for r in history(client) if "Water" in r["detail"]]
        assert rows and not any("Undefined" in r["detail"] for r in rows)
