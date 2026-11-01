"""
The activity history: who changed what in the shared budget.

Every successful GraphQL mutation is recorded automatically (see
``record_mutations``), plus account and file actions from the web routes.
Anything that looks secret (passwords, tokens, access URLs) is never stored.
Entries older than a year are pruned by the daily upkeep job.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from models import database as db

KEEP_DAYS = 365
SECRET_RE = re.compile(r"password|token|secret|access_?url|setup_?token", re.I)
# Arguments worth showing, in this order, with the label each gets ("" = just the value)
NOTABLE = {"billName": "", "name": "", "groupName": "", "sourceName": "", "bankName": "", "accountName": "",
           "description": "", "category": "category ", "amount": "", "balance": "balance ",
           "newBalance": "new balance ", "date": "", "paidDate": "paid ", "key": "", "days": "days: "}
MONEY = {"amount", "balance", "newBalance"}
# Mutations that are housekeeping rather than changes worth listing
QUIET = {"dismissAlert"}


def log(action: str, detail: str = "", user: dict | None = None, at: datetime | None = None) -> None:
    session = db.get_session()
    try:
        session.add(db.ActivityModel(at=at or datetime.now(), user_id=(user or {}).get("id"),
                                     username=(user or {}).get("username") or "", action=action[:80],
                                     detail=(detail or "")[:400]))
        session.commit()
    finally:
        session.close()


def recent(limit: int = 50, before_id: int | None = None, username: str | None = None) -> list[dict]:
    session = db.get_session()
    try:
        q = session.query(db.ActivityModel)
        if before_id:
            q = q.filter(db.ActivityModel.id < before_id)
        if username:
            q = q.filter(db.ActivityModel.username == username)
        rows = q.order_by(db.ActivityModel.id.desc()).limit(max(1, min(limit, 200))).all()
        return [{"id": r.id, "at": r.at.isoformat(timespec="seconds"), "username": r.username,
                 "action": r.action, "detail": r.detail} for r in rows]
    finally:
        session.close()


def prune(now: datetime | None = None, days: int = KEEP_DAYS) -> int:
    cutoff = (now or datetime.now()) - timedelta(days=days)
    session = db.get_session()
    try:
        n = session.query(db.ActivityModel).filter(db.ActivityModel.at < cutoff).delete()
        session.commit()
        return n
    finally:
        session.close()


# ── Describing GraphQL mutations ───────────────────────────────────────

def humanize(field: str) -> str:
    """createBill → "Create bill", markBillPaid → "Mark bill paid"."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", field).lower()
    return words[:1].upper() + words[1:]


def _short(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _redact(value):
    if isinstance(value, dict):
        return {k: ("•••" if SECRET_RE.search(k) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def describe(args: dict) -> str:
    """A short "Rent · $1,200.00" summary of a mutation's arguments."""
    import json
    args = _redact(args)
    def show(k, v):
        if k in MONEY and isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"${float(v):,.2f}" if v >= 0 else f"-${-float(v):,.2f}"
        return _short(v)

    parts = [f"{label}{show(k, args[k])}" for k, label in NOTABLE.items() if args.get(k) not in (None, "")]
    if "changes" in args:  # updateSettings: list which settings changed
        changes = args["changes"]
        if isinstance(changes, str):
            try:
                changes = json.loads(changes)
            except ValueError:
                changes = {}
        if isinstance(changes, dict):
            keys = [k.replace("_", " ") for k in changes if not SECRET_RE.search(k)]
            secret = [k for k in changes if SECRET_RE.search(k)]
            parts.append(", ".join(keys + ([f"{len(secret)} secret value(s)"] if secret else [])))
    if not parts:
        extra = [f"{k}: {_short(v)}" for k, v in args.items() if not isinstance(v, (dict, list))][:3]
        parts = extra
    return " · ".join(p for p in parts if p)[:400]


def record_mutations(query: str, variables: dict | None, operation_name: str | None, data: dict | None,
                     user: dict | None) -> int:
    """Log each top-level field of a successful mutation. Returns how many were logged."""
    from graphql import OperationDefinitionNode, OperationType, parse
    from graphql import Undefined
    from graphql.utilities import value_from_ast_untyped
    if not data:
        return 0
    try:
        doc = parse(query)
    except Exception:  # noqa: BLE001 — a bad query already failed; nothing to record
        return 0
    ops = [d for d in doc.definitions if isinstance(d, OperationDefinitionNode)]
    if operation_name:
        ops = [o for o in ops if o.name and o.name.value == operation_name]
    op = ops[0] if len(ops) == 1 else None
    if op is None or op.operation != OperationType.MUTATION:
        return 0
    logged = 0
    for sel in op.selection_set.selections:
        name = getattr(getattr(sel, "name", None), "value", None)
        if not name or name in QUIET:
            continue
        key = sel.alias.value if getattr(sel, "alias", None) else name
        payload = data.get(key)
        if payload is None or (isinstance(payload, dict) and payload.get("success") is False):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("result"), dict) \
                and payload["result"].get("success") is False:
            continue
        args = {a.name.value: value_from_ast_untyped(a.value, variables or {}) for a in (sel.arguments or [])}
        args = {k: v for k, v in args.items() if v is not Undefined}  # variables the client didn't send
        log(humanize(name), describe(args), user)
        logged += 1
    return logged
