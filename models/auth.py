"""
User accounts for the web UI.

Everyone signs in with their own username and password; all users share the
same household budget. When the server starts with no accounts it creates the
admin account "admin" with a random password, printed once and saved to
~/.budget_app/initial-admin-password.txt until it's changed (so a headless
server can be set up from the command line). Started some other way, the first
account is created in the browser on the computer that runs the app. After that, people join only with a one-time
invite code that an admin creates (Settings → Users). Admins can also make a
one-time password-reset code for someone who forgot theirs.

Passwords are stored as PBKDF2-SHA256 hashes. Session tokens and invite codes
are random; only their SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta

from models import database as db

ITERATIONS = 260_000
SESSION_DAYS = 30
MIN_LENGTH = 8
INVITE_DAYS = 7
RESET_DAYS = 2
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

# Failed sign-in / code attempts allowed per client within the window
MAX_FAILURES = 10
FAILURE_WINDOW = 15 * 60


# ── Hashing ────────────────────────────────────────────────────────────

def hash_password(password: str, salt: str | None = None, iterations: int = ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt, int(iterations)).split("$")[3]
    return hmac.compare_digest(candidate, digest)


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ── Throttling ─────────────────────────────────────────────────────────

_failures: dict[str, list[float]] = {}
_failures_lock = threading.Lock()


def throttled(key: str) -> bool:
    """True when ``key`` (a client address) has failed too often recently."""
    cutoff = time.monotonic() - FAILURE_WINDOW
    with _failures_lock:
        recent = [t for t in _failures.get(key, []) if t > cutoff]
        _failures[key] = recent
        return len(recent) >= MAX_FAILURES


def record_failure(key: str) -> None:
    with _failures_lock:
        _failures.setdefault(key, []).append(time.monotonic())


def clear_failures(key: str) -> None:
    with _failures_lock:
        _failures.pop(key, None)


# ── Users ──────────────────────────────────────────────────────────────

def _user_dict(u: db.UserModel) -> dict:
    return {"id": u.id, "username": u.username, "is_admin": bool(u.is_admin),
            "must_change_password": bool(u.must_change_password),
            "created_at": db.to_local(u.created_at).isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None}


def normalize_username(username: str | None) -> str:
    return (username or "").strip().lower()


def _check_new_credentials(session, username: str, password: str) -> None:
    if not USERNAME_RE.match(username):
        raise ValueError("Usernames are 3-32 letters, numbers, dots, dashes or underscores")
    if len(password or "") < MIN_LENGTH:
        raise ValueError(f"Use at least {MIN_LENGTH} characters for the password")
    if session.query(db.UserModel).filter_by(username=username).first():
        raise ValueError("That username is taken")


def has_users() -> bool:
    session = db.get_session()
    try:
        return session.query(db.UserModel.id).first() is not None
    finally:
        session.close()


def create_user(username: str, password: str, is_admin: bool = False) -> dict:
    username = normalize_username(username)
    session = db.get_session()
    try:
        _check_new_credentials(session, username, password)
        user = db.UserModel(username=username, password_hash=hash_password(password), is_admin=is_admin)
        session.add(user)
        session.commit()
        return _user_dict(user)
    finally:
        session.close()


def create_first_admin(username: str, password: str) -> dict:
    if has_users():
        raise ValueError("The first account already exists — sign in instead")
    return create_user(username, password, is_admin=True)


def authenticate(username: str, password: str) -> dict | None:
    """The user, if the username and password match."""
    session = db.get_session()
    try:
        user = session.query(db.UserModel).filter_by(username=normalize_username(username)).first()
        if user is None:
            verify_password(password or "", _DUMMY_HASH)  # same work either way
            return None
        if not verify_password(password or "", user.password_hash):
            return None
        user.last_login = datetime.now()
        session.commit()
        return _user_dict(user)
    finally:
        session.close()


def get_user(user_id: int) -> dict | None:
    session = db.get_session()
    try:
        user = session.get(db.UserModel, user_id)
        return _user_dict(user) if user else None
    finally:
        session.close()


def list_users() -> list[dict]:
    session = db.get_session()
    try:
        return [_user_dict(u) for u in session.query(db.UserModel).order_by(db.UserModel.username)]
    finally:
        session.close()


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    session = db.get_session()
    try:
        user = session.get(db.UserModel, user_id)
        if user is None or not verify_password(current_password or "", user.password_hash):
            raise ValueError("Current password is wrong")
        if len(new_password or "") < MIN_LENGTH:
            raise ValueError(f"Use at least {MIN_LENGTH} characters for the password")
        user.password_hash = hash_password(new_password)
        _password_replaced(user)
        session.commit()
    finally:
        session.close()


def _admin_count(session) -> int:
    return session.query(db.UserModel).filter_by(is_admin=True).count()


def set_admin(user_id: int, is_admin: bool) -> None:
    session = db.get_session()
    try:
        user = session.get(db.UserModel, user_id)
        if user is None:
            raise ValueError("No such user")
        if user.is_admin and not is_admin and _admin_count(session) <= 1:
            raise ValueError("There has to be at least one admin")
        user.is_admin = is_admin
        session.commit()
    finally:
        session.close()


def delete_user(user_id: int) -> None:
    session = db.get_session()
    try:
        user = session.get(db.UserModel, user_id)
        if user is None:
            raise ValueError("No such user")
        if user.is_admin and _admin_count(session) <= 1:
            raise ValueError("There has to be at least one admin")
        # SQLite doesn't enforce the foreign keys, so tidy up by hand
        session.query(db.AuthSessionModel).filter_by(user_id=user_id).delete()
        session.query(db.AuthInviteModel).filter_by(kind="reset", user_id=user_id).delete()
        session.delete(user)
        session.commit()
    finally:
        session.close()


# ── Invites and reset codes ────────────────────────────────────────────

def _invite_dict(i: db.AuthInviteModel, names: dict[int, str]) -> dict:
    return {"id": i.id, "kind": i.kind, "make_admin": bool(i.make_admin),
            "username": names.get(i.user_id), "created_by": names.get(i.created_by),
            "expires_at": i.expires_at.isoformat(),
            "created_at": db.to_local(i.created_at).isoformat() if i.created_at else None}


def _new_code(session, **fields) -> str:
    code = secrets.token_urlsafe(16)
    session.add(db.AuthInviteModel(code_hash=_sha(code), **fields))
    session.commit()
    return code


def create_invite(created_by: int | None, make_admin: bool = False, days: int = INVITE_DAYS) -> str:
    days = max(1, min(int(days or INVITE_DAYS), 30))
    session = db.get_session()
    try:
        return _new_code(session, kind="invite", make_admin=make_admin, created_by=created_by,
                         expires_at=datetime.now() + timedelta(days=days))
    finally:
        session.close()


def create_reset(user_id: int, created_by: int | None) -> str:
    session = db.get_session()
    try:
        if session.get(db.UserModel, user_id) is None:
            raise ValueError("No such user")
        # Only the newest reset code for a user works
        session.query(db.AuthInviteModel).filter_by(kind="reset", user_id=user_id, used_at=None).delete()
        return _new_code(session, kind="reset", user_id=user_id, created_by=created_by,
                         expires_at=datetime.now() + timedelta(days=RESET_DAYS))
    finally:
        session.close()


def pending_invites() -> list[dict]:
    session = db.get_session()
    try:
        names = {u.id: u.username for u in session.query(db.UserModel)}
        rows = (session.query(db.AuthInviteModel)
                .filter(db.AuthInviteModel.used_at.is_(None), db.AuthInviteModel.expires_at > datetime.now())
                .order_by(db.AuthInviteModel.created_at.desc()))
        return [_invite_dict(i, names) for i in rows]
    finally:
        session.close()


def revoke_invite(invite_id: int) -> None:
    session = db.get_session()
    try:
        session.query(db.AuthInviteModel).filter_by(id=invite_id, used_at=None).delete()
        session.commit()
    finally:
        session.close()


def _live_code(session, code: str | None) -> db.AuthInviteModel | None:
    if not code:
        return None
    row = session.query(db.AuthInviteModel).filter_by(code_hash=_sha(code.strip())).first()
    if row is None or row.used_at is not None or row.expires_at <= datetime.now():
        return None
    return row


def inspect_code(code: str | None) -> dict | None:
    """What a code is for (so the sign-up page can show the right form), or None if it's no good."""
    session = db.get_session()
    try:
        row = _live_code(session, code)
        if row is None:
            return None
        info = {"kind": row.kind}
        if row.kind == "reset":
            user = session.get(db.UserModel, row.user_id)
            if user is None:
                return None
            info["username"] = user.username
        return info
    finally:
        session.close()


def register(code: str, username: str, password: str) -> dict:
    """Create an account with an invite code (the code is used up)."""
    username = normalize_username(username)
    session = db.get_session()
    try:
        invite = _live_code(session, code)
        if invite is None or invite.kind != "invite":
            raise ValueError("That invite code isn't valid — it may have expired or already been used")
        _check_new_credentials(session, username, password)
        user = db.UserModel(username=username, password_hash=hash_password(password),
                            is_admin=bool(invite.make_admin))
        session.add(user)
        session.flush()
        invite.used_at, invite.used_by = datetime.now(), user.id
        session.commit()
        return _user_dict(user)
    finally:
        session.close()


def reset_password(code: str, password: str) -> dict:
    """Set a new password with a reset code; signs that user out everywhere."""
    session = db.get_session()
    try:
        row = _live_code(session, code)
        if row is None or row.kind != "reset":
            raise ValueError("That reset code isn't valid — ask an admin for a new one")
        if len(password or "") < MIN_LENGTH:
            raise ValueError(f"Use at least {MIN_LENGTH} characters for the password")
        user = session.get(db.UserModel, row.user_id)
        if user is None:
            raise ValueError("That account no longer exists")
        user.password_hash = hash_password(password)
        _password_replaced(user)
        row.used_at, row.used_by = datetime.now(), user.id
        session.query(db.AuthSessionModel).filter_by(user_id=user.id).delete()
        session.commit()
        return _user_dict(user)
    finally:
        session.close()


# ── Sessions ───────────────────────────────────────────────────────────

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    session = db.get_session()
    try:
        now = datetime.now()
        session.query(db.AuthSessionModel).filter(db.AuthSessionModel.expires_at < now).delete()
        session.add(db.AuthSessionModel(token_hash=_sha(token), user_id=user_id,
                                        expires_at=now + timedelta(days=SESSION_DAYS)))
        session.commit()
    finally:
        session.close()
    return token


def session_user(token: str | None) -> dict | None:
    """The signed-in user for a session token, or None."""
    if not token:
        return None
    session = db.get_session()
    try:
        row = session.query(db.AuthSessionModel).filter_by(token_hash=_sha(token)).first()
        if row is None or row.user_id is None or row.expires_at <= datetime.now():
            return None
        user = session.get(db.UserModel, row.user_id)
        return _user_dict(user) if user else None
    finally:
        session.close()


def logout(token: str | None) -> None:
    if not token:
        return
    session = db.get_session()
    try:
        session.query(db.AuthSessionModel).filter_by(token_hash=_sha(token)).delete()
        session.commit()
    finally:
        session.close()


def logout_user(user_id: int, keep_token: str | None = None) -> None:
    """End a user's sessions (except ``keep_token``, the one making the request)."""
    session = db.get_session()
    try:
        q = session.query(db.AuthSessionModel).filter_by(user_id=user_id)
        if keep_token:
            q = q.filter(db.AuthSessionModel.token_hash != _sha(keep_token))
        q.delete()
        session.commit()
    finally:
        session.close()


# ── Default admin with a generated password ────────────────────────────

DEFAULT_ADMIN = "admin"


def initial_password_file() -> str:
    return os.path.join(os.path.dirname(db.DB_PATH), "initial-admin-password.txt")


def ensure_default_admin() -> str | None:
    """With no accounts, create "admin" with a random password and return it (else None).

    The password is also written to initial_password_file() (readable only by
    this user where the OS supports it) until it's changed.
    """
    if has_users():
        return None
    password = secrets.token_urlsafe(12)
    session = db.get_session()
    try:
        session.add(db.UserModel(username=DEFAULT_ADMIN, password_hash=hash_password(password),
                                 is_admin=True, must_change_password=True))
        session.commit()
    finally:
        session.close()
    path = initial_password_file()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"username: {DEFAULT_ADMIN}\npassword: {password}\n"
                "This file is deleted when the password is changed.\n")
    return password


def _password_replaced(user: db.UserModel) -> None:
    """A chosen password replaced a generated one: drop the flag and the saved copy."""
    if user.must_change_password:
        user.must_change_password = False
        try:
            os.remove(initial_password_file())
        except OSError:
            pass


# ── Upgrade from the single shared password ────────────────────────────

LEGACY_USERNAME = "admin"


def migrate_legacy_password() -> bool:
    """An older single password becomes the admin account "admin" with the same password."""
    from models.app_settings import get_setting, update_settings
    stored = get_setting("password_hash")
    if not stored:
        return False
    session = db.get_session()
    try:
        if session.query(db.UserModel.id).first() is None:
            session.add(db.UserModel(username=LEGACY_USERNAME, password_hash=stored, is_admin=True))
        session.query(db.AuthSessionModel).filter(db.AuthSessionModel.user_id.is_(None)).delete()
        session.commit()
    finally:
        session.close()
    update_settings({"password_hash": ""})
    return True


def set_password_for(username: str, new_password: str) -> dict:
    """Set someone's password directly (the command-line way back in) and sign them out everywhere."""
    session = db.get_session()
    try:
        user = session.query(db.UserModel).filter_by(username=normalize_username(username)).first()
        if user is None:
            raise ValueError(f"No user named {username!r}")
        if len(new_password or "") < MIN_LENGTH:
            raise ValueError(f"Use at least {MIN_LENGTH} characters for the password")
        user.password_hash = hash_password(new_password)
        _password_replaced(user)
        session.query(db.AuthSessionModel).filter_by(user_id=user.id).delete()
        session.commit()
        return _user_dict(user)
    finally:
        session.close()


def _main(argv: list[str]) -> int:
    """python -m models.auth users | reset-password <username>   (run on the computer with the data)"""
    import getpass
    db.init_db()
    if argv[:1] == ["users"]:
        for u in list_users():
            print(f"{u['username']}{'  (admin)' if u['is_admin'] else ''}")
        return 0
    if argv[:1] == ["reset-password"] and len(argv) == 2:
        new = getpass.getpass(f"New password for {argv[1]}: ")
        if new != getpass.getpass("Again: "):
            print("Passwords don't match")
            return 1
        try:
            set_password_for(argv[1], new)
        except ValueError as e:
            print(e)
            return 1
        print("Password changed")
        return 0
    print(_main.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
