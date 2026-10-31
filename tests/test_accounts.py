"""Tests for user accounts: setup, sign in, invites, resets, admin tools and access rules."""

from datetime import datetime, timedelta

import pytest

from models import auth
from models import database as db
from models.app_settings import get_setting, update_settings
from tests.test_phase4 import client, gql  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

REMOTE = {"REMOTE_ADDR": "192.168.1.50"}
PW = "longenough1"


@pytest.fixture(autouse=True)
def _reset_throttle():
    auth._failures.clear()
    yield
    auth._failures.clear()


def device(client):
    """Another browser on the network: no cookie, remote address."""
    return client.application.test_client()


def setup_admin(client, username="Jordan", password=PW):
    r = client.post("/auth/setup", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def login(c, username, password=PW, **kw):
    return c.post("/auth/login", json={"username": username, "password": password},
                  environ_base=REMOTE, **kw)


def invite(admin, make_admin=False):
    r = admin.post("/auth/invites", json={"make_admin": make_admin})
    assert r.status_code == 200
    return r.get_json()["code"]


class TestPasswords:

    def test_hashing(self):
        h = auth.hash_password("correct horse")
        assert h.startswith("pbkdf2_sha256$") and auth.verify_password("correct horse", h)
        assert not auth.verify_password("wrong", h) and not auth.verify_password("x", "garbage")

    def test_username_and_password_rules(self, temp_db):  # noqa: F811
        for bad in ("ab", "has space", "x" * 33, "-dash", "émile"):
            with pytest.raises(ValueError, match="Usernames"):
                auth.create_user(bad, PW)
        with pytest.raises(ValueError, match="at least 8"):
            auth.create_user("sam", "short")
        auth.create_user("Sam", PW)
        with pytest.raises(ValueError, match="taken"):
            auth.create_user("SAM", PW)  # case-insensitive
        assert auth.authenticate("sAm ", PW)["username"] == "sam"
        assert auth.authenticate("sam", "nope") is None and auth.authenticate("nobody", PW) is None


class TestFirstRun:

    def test_before_any_account_only_this_computer(self, client):
        assert gql(client, "{ allBanks { name } }").status_code == 200
        r = gql(client, "{ allBanks { name } }", environ_base=REMOTE)
        assert r.status_code == 403 and r.get_json()["error"] == "setup_required"
        # Through the Vite proxy: loopback address, real client in X-Forwarded-For
        assert gql(client, "{ allBanks { name } }", headers={"X-Forwarded-For": "192.168.1.50"}).status_code == 403
        assert client.get("/auth/status", environ_base=REMOTE).get_json() == {
            "needs_setup": True, "authenticated": False, "user": None, "local": False}
        r = client.post("/auth/setup", json={"username": "jordan", "password": PW}, environ_base=REMOTE)
        assert r.status_code == 403

    def test_setup_once_then_everyone_signs_in(self, client):
        body = setup_admin(client)
        assert body["user"]["username"] == "jordan" and body["user"]["is_admin"] and body["token"]
        status = client.get("/auth/status").get_json()
        assert status["authenticated"] and not status["needs_setup"] and status["user"]["is_admin"]
        assert client.post("/auth/setup", json={"username": "other", "password": PW}).status_code == 400
        # This computer is no longer trusted on its own
        fresh = device(client)
        assert gql(fresh, "{ allBanks { name } }").status_code == 401
        assert gql(fresh, "{ allBanks { name } }", environ_base=REMOTE).status_code == 401


class TestSignIn:

    def test_cookie_bearer_and_logout(self, client):
        setup_admin(client)
        other = device(client)
        assert login(other, "jordan", "nope").status_code == 401
        r = login(other, "JORDAN")
        assert r.status_code == 200
        token = r.get_json()["token"]
        assert gql(other, "{ allBanks { name } }", environ_base=REMOTE).status_code == 200  # cookie
        bearer = device(client)
        assert gql(bearer, "{ allBanks { name } }", environ_base=REMOTE,
                   headers={"Authorization": f"Bearer {token}"}).status_code == 200
        other.post("/auth/logout", environ_base=REMOTE)
        assert gql(other, "{ allBanks { name } }", environ_base=REMOTE).status_code == 401
        assert client.get("/health", environ_base=REMOTE).status_code == 200  # stays open

    def test_failed_attempts_are_throttled(self, client):
        setup_admin(client)
        other = device(client)
        for _ in range(auth.MAX_FAILURES):
            assert login(other, "jordan", "wrong").status_code == 401
        assert login(other, "jordan").status_code == 429  # even with the right password
        # Other clients aren't affected
        assert device(client).post("/auth/login", json={"username": "jordan", "password": PW},
                                   environ_base={"REMOTE_ADDR": "192.168.1.51"}).status_code == 200

    def test_change_own_password_signs_out_other_devices(self, client):
        setup_admin(client)
        phone = device(client)
        login(phone, "jordan")
        r = client.post("/auth/password", json={"current_password": "wrong", "new_password": "newpass99"})
        assert r.status_code == 400
        r = client.post("/auth/password", json={"current_password": PW, "new_password": "newpass99"})
        assert r.status_code == 200
        assert gql(client, "{ allBanks { name } }").status_code == 200  # this device stays signed in
        assert gql(phone, "{ allBanks { name } }", environ_base=REMOTE).status_code == 401
        assert login(device(client), "jordan", "newpass99").status_code == 200
        assert device(client).post("/auth/password", json={}).status_code == 401


class TestInvites:

    def test_register_with_invite(self, client):
        setup_admin(client)
        code = invite(client)
        guest = device(client)
        info = guest.get(f"/auth/code/{code}", environ_base=REMOTE).get_json()
        assert info == {"success": True, "kind": "invite"}
        bad = guest.post("/auth/register", json={"code": "nope", "username": "casey", "password": PW},
                         environ_base=REMOTE)
        assert bad.status_code == 400
        taken = guest.post("/auth/register", json={"code": code, "username": "Jordan", "password": PW},
                           environ_base=REMOTE)
        assert taken.status_code == 400 and "taken" in taken.get_json()["message"]
        r = guest.post("/auth/register", json={"code": code, "username": "casey", "password": PW},
                       environ_base=REMOTE)
        assert r.status_code == 200 and not r.get_json()["user"]["is_admin"]
        # Signed straight in, sharing the same budget
        gql(client, 'mutation { createBank(name: "Shared") { success } }')
        banks = gql(guest, "{ allBanks { name } }", environ_base=REMOTE).get_json()["data"]["allBanks"]
        assert [b["name"] for b in banks] == ["Shared"]
        # One use only
        again = device(client).post("/auth/register", json={"code": code, "username": "drew", "password": PW},
                                    environ_base=REMOTE)
        assert again.status_code == 400
        assert device(client).get(f"/auth/code/{code}", environ_base=REMOTE).status_code == 404

    def test_admin_invite_expiry_and_revoke(self, client, monkeypatch):
        setup_admin(client)
        admin_code = invite(client, make_admin=True)
        r = device(client).post("/auth/register", json={"code": admin_code, "username": "pat", "password": PW})
        assert r.get_json()["user"]["is_admin"]

        code = invite(client)
        pending = client.get("/auth/users").get_json()["invites"]
        assert len(pending) == 1 and pending[0]["created_by"] == "jordan"
        client.delete(f"/auth/invites/{pending[0]['id']}")
        assert client.get("/auth/users").get_json()["invites"] == []
        assert auth.inspect_code(code) is None


        code = invite(client)
        later = datetime.now() + timedelta(days=auth.INVITE_DAYS, minutes=1)
        monkeypatch.setattr(auth, "datetime", type("D", (), {"now": staticmethod(lambda: later)}))
        assert auth.inspect_code(code) is None

    def test_admin_only(self, client):
        setup_admin(client)
        code = invite(client)
        member = device(client)
        member.post("/auth/register", json={"code": code, "username": "casey", "password": PW})
        for method, path in (("get", "/auth/users"), ("post", "/auth/invites"), ("delete", "/auth/invites/1"),
                             ("patch", "/auth/users/1"), ("delete", "/auth/users/1"),
                             ("post", "/auth/users/1/reset"), ("get", "/files/backup.db"),
                             ("post", "/files/restore")):
            r = getattr(member, method)(path, json={})
            assert r.status_code == 403, (method, path)
        assert member.get("/files/transactions.csv").status_code == 200  # everyday files are fine
        assert device(client).get("/auth/users").status_code == 401


class TestUserAdmin:

    def _two_users(self, client):
        setup_admin(client)
        member = device(client)
        member.post("/auth/register", json={"code": invite(client), "username": "casey", "password": PW})
        ids = {u["username"]: u["id"] for u in client.get("/auth/users").get_json()["users"]}
        return member, ids

    def test_promote_demote_and_last_admin(self, client):
        member, ids = self._two_users(client)
        assert client.patch(f"/auth/users/{ids['jordan']}", json={"is_admin": False}).status_code == 400
        assert client.patch(f"/auth/users/{ids['casey']}", json={"is_admin": True}).status_code == 200
        assert member.get("/auth/users").status_code == 200  # takes effect on the next request
        assert client.patch(f"/auth/users/{ids['jordan']}", json={"is_admin": False}).status_code == 200
        assert client.get("/auth/users").status_code == 403

    def test_delete_user(self, client):
        member, ids = self._two_users(client)
        assert client.delete(f"/auth/users/{ids['jordan']}").status_code == 400  # not yourself
        assert client.delete(f"/auth/users/{ids['casey']}").status_code == 200
        assert gql(member, "{ allBanks { name } }").status_code == 401
        assert [u["username"] for u in client.get("/auth/users").get_json()["users"]] == ["jordan"]

    def test_reset_code(self, client):
        member, ids = self._two_users(client)
        code = client.post(f"/auth/users/{ids['casey']}/reset").get_json()["code"]
        assert gql(member, "{ allBanks { name } }").status_code == 401  # signed out
        stranger = device(client)
        assert stranger.get(f"/auth/code/{code}").get_json() == {"success": True, "kind": "reset",
                                                                 "username": "casey"}
        assert stranger.post("/auth/register", json={"code": code, "username": "x1x", "password": PW}
                             ).status_code == 400  # not an invite
        assert stranger.post("/auth/reset", json={"code": code, "password": "short"}).status_code == 400
        r = stranger.post("/auth/reset", json={"code": code, "password": "brandnew9"})
        assert r.status_code == 200 and r.get_json()["user"]["username"] == "casey"
        assert login(device(client), "casey", "brandnew9").status_code == 200
        assert login(device(client), "casey").status_code == 401
        assert stranger.post("/auth/reset", json={"code": code, "password": "again1234"}).status_code == 400


class TestLegacyPassword:

    def test_old_password_becomes_admin_account(self, temp_db):  # noqa: F811
        update_settings({"password_hash": auth.hash_password("oldpassword")})
        session = db.get_session()
        session.add(db.AuthSessionModel(token_hash="x" * 64, expires_at=datetime(2099, 1, 1)))
        session.commit()
        session.close()
        from api_server import create_app
        c = create_app().test_client()
        assert get_setting("password_hash") == ""
        assert auth.session_user("anything") is None
        r = login(c, auth.LEGACY_USERNAME, "oldpassword")
        assert r.status_code == 200 and r.get_json()["user"]["is_admin"]

    def test_graphql_cannot_set_password_hash(self, client):
        r = gql(client, 'mutation { updateSettings(changes: "{\\"password_hash\\": \\"x\\"}") { success } }')
        assert r.get_json()["data"]["updateSettings"]["success"] is False
        settings = gql(client, "{ settings }").get_json()["data"]["settings"]
        assert "password_hash" not in settings and "smtp_password\"" not in settings


class TestCommandLine:

    def test_set_password_for(self, temp_db):  # noqa: F811
        auth.create_user("jordan", PW, is_admin=True)
        token = auth.create_session(auth.authenticate("jordan", PW)["id"])
        with pytest.raises(ValueError, match="No user"):
            auth.set_password_for("nobody", "whatever99")
        auth.set_password_for("Jordan", "recovered1")
        assert auth.authenticate("jordan", "recovered1") and auth.session_user(token) is None
