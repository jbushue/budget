"""
Optional password login for the web UI.

With no password set, the app only answers requests from this computer
(localhost). Setting a password lets you open it from your phone or another
device on your network: you sign in once and get a session cookie that
lasts 30 days.

Passwords are stored as PBKDF2-SHA256 hashes; session tokens are random and
only their SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from models import database as db

ITERATIONS = 260_000
SESSION_DAYS = 30
MIN_LENGTH = 8


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


def password_set() -> bool:
    from models.app_settings import get_setting
    return bool(get_setting("password_hash"))


def check_password(password: str) -> bool:
    from models.app_settings import get_setting
    stored = get_setting("password_hash")
    return bool(stored) and verify_password(password or "", stored)


def set_password(new_password: str | None, current_password: str | None = None) -> None:
    """Set, change, or (new_password empty) remove the password."""
    from models.app_settings import update_settings
    if password_set() and not check_password(current_password or ""):
        raise ValueError("Current password is wrong")
    if new_password:
        if len(new_password) < MIN_LENGTH:
            raise ValueError(f"Use at least {MIN_LENGTH} characters")
        update_settings({"password_hash": hash_password(new_password)})
    else:
        update_settings({"password_hash": ""})
    logout_all()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    session = db.get_session()
    try:
        now = datetime.now()
        session.query(db.AuthSessionModel).filter(db.AuthSessionModel.expires_at < now).delete()
        session.add(db.AuthSessionModel(token_hash=_token_hash(token), expires_at=now + timedelta(days=SESSION_DAYS)))
        session.commit()
    finally:
        session.close()
    return token


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    session = db.get_session()
    try:
        row = session.query(db.AuthSessionModel).filter_by(token_hash=_token_hash(token)).first()
        return row is not None and row.expires_at > datetime.now()
    finally:
        session.close()


def logout(token: str | None) -> None:
    if not token:
        return
    session = db.get_session()
    try:
        session.query(db.AuthSessionModel).filter_by(token_hash=_token_hash(token)).delete()
        session.commit()
    finally:
        session.close()


def logout_all() -> None:
    session = db.get_session()
    try:
        session.query(db.AuthSessionModel).delete()
        session.commit()
    finally:
        session.close()
