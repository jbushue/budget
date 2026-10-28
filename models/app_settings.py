"""
App-wide settings stored in the ``app_settings`` table.

Every setting has a default here; the database only stores values the user
changed. Values are validated and coerced to the default's type so the rest
of the app can rely on them.
"""

from __future__ import annotations

import json

from models import database as db

DEFAULTS: dict = {
    # ── Planning ──────────────────────────────────────────────────────
    # Money to always keep in checking; "safe to spend" never dips into it
    "cushion": 200.0,
    # Everyday spending (groceries, gas, eating out...) not entered as bills.
    # "manual" uses everyday_weekly; "learned" uses the transaction history.
    "spending_mode": "manual",
    "everyday_weekly": 0.0,
    # "Bank:Account" the everyday spending comes out of ("" = main checking)
    "spending_account": "",
    # ── Fees ──────────────────────────────────────────────────────────
    "card_late_fee": 30.0,      # credit card / HELOC payment made late
    "default_late_fee": 0.0,    # other bills without their own late fee
    "overdraft_fee": 35.0,      # each time checking goes below $0
    # ── Transactions / bills ──────────────────────────────────────────
    # Mark a bill paid automatically when a matching transaction shows up
    "auto_match_bills": True,
    "dismissed_recurring": [],  # recurring-charge suggestions the user dismissed
    # ── Alerts ────────────────────────────────────────────────────────
    "alert_days_before_due": 3,
    "alert_low_balance": True,
    "browser_notifications": False,
    # Optional daily email digest (needs SMTP server settings)
    "email_enabled": False,
    "email_to": "",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_use_tls": True,
    "last_digest_date": "",
    # ── Security ──────────────────────────────────────────────────────
    "password_hash": "",
}

SPENDING_MODES = ("manual", "learned")
# Settings never sent to the browser
SECRET_KEYS = {"password_hash", "smtp_password"}


def _coerce(key: str, value):
    default = DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if isinstance(default, int):
        return int(float(value))
    if isinstance(default, float):
        return float(value)
    if isinstance(default, list):
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        return value
    return "" if value is None else str(value)


def _validate(key: str, value):
    if key in ("cushion", "everyday_weekly", "card_late_fee", "default_late_fee", "overdraft_fee") and value < 0:
        raise ValueError(f"{key.replace('_', ' ')} can't be negative")
    if key == "spending_mode" and value not in SPENDING_MODES:
        raise ValueError(f"spending_mode must be one of {', '.join(SPENDING_MODES)}")
    if key == "alert_days_before_due" and not 0 <= value <= 30:
        raise ValueError("alert days before due must be between 0 and 30")
    if key == "spending_account" and value and ":" not in value:
        raise ValueError("spending account must look like 'Bank:Account'")


def get_settings() -> dict:
    """All settings (defaults overlaid with stored values)."""
    out = dict(DEFAULTS)
    session = db.get_session()
    try:
        for row in session.query(db.AppSettingModel).all():
            if row.key in DEFAULTS:
                try:
                    out[row.key] = _coerce(row.key, json.loads(row.value))
                except (ValueError, TypeError):
                    pass  # keep the default for a corrupt value
    finally:
        session.close()
    return out


def get_setting(key: str):
    return get_settings()[key]


def update_settings(changes: dict) -> dict:
    """Validate and store ``changes``; returns the full settings."""
    clean = {}
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"Unknown setting '{key}'")
        try:
            v = _coerce(key, value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for {key}: {value!r}")
        _validate(key, v)
        clean[key] = v

    session = db.get_session()
    try:
        for key, v in clean.items():
            row = session.get(db.AppSettingModel, key)
            if row is None:
                session.add(db.AppSettingModel(key=key, value=json.dumps(v)))
            else:
                row.value = json.dumps(v)
        session.commit()
    finally:
        session.close()
    return get_settings()


def public_settings(settings: dict | None = None) -> dict:
    """Settings safe to send to the web UI (secrets replaced by flags)."""
    s = dict(settings or get_settings())
    s["password_set"] = bool(s.get("password_hash"))
    s["smtp_password_set"] = bool(s.get("smtp_password"))
    for key in SECRET_KEYS:
        s.pop(key, None)
    return s
