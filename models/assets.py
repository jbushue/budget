"""
Assets: things you own that aren't bank accounts — cars, investment and
retirement accounts, property, valuables. Each has a value you update now
and then (with history) and, optionally, the loan against it (a card/loan
account, mortgage or HELOC) so its equity can be shown.

Net worth = cash in bank accounts + assets + loan collateral (a mortgage's
home value or an auto loan's vehicle value, after depreciation, unless an
asset is linked to that loan) − debts.
"""

from __future__ import annotations

from datetime import date

from models import database as db

KINDS = {
    "vehicle": "Vehicle",
    "investment": "Investments",
    "retirement": "Retirement",
    "property": "Property",
    "cash": "Cash & other savings",
    "valuables": "Valuables",
    "other": "Other",
}


def _session():
    return db.get_session()


def _loan_balance(manager, bank_name, account_name) -> tuple[float | None, str | None]:
    """(balance owed, kind) of the account linked to an asset, if it still exists."""
    if not (manager and bank_name and account_name):
        return None, None
    bank = next((b for b in manager.banks if b.name == bank_name), None)
    if not bank:
        return None, None
    if account_name in bank.credit_accounts:
        return bank.credit_accounts[account_name].balance, "credit"
    if account_name in bank.mortgage_accounts:
        return bank.mortgage_accounts[account_name].current_principal, "mortgage"
    if account_name in bank.heloc_accounts:
        return bank.heloc_accounts[account_name].balance, "heloc"
    return None, None


def _to_dict(a: db.AssetModel, manager=None) -> dict:
    owed, kind = _loan_balance(manager, a.linked_bank, a.linked_account)
    return {
        "id": a.id, "name": a.name, "kind": a.kind, "kind_label": KINDS.get(a.kind, "Other"),
        "value": round(a.value, 2), "notes": a.notes or "",
        "linked_bank": a.linked_bank or "", "linked_account": a.linked_account or "",
        "loan_balance": round(owed, 2) if owed is not None else None, "loan_kind": kind,
        "equity": round(a.value - owed, 2) if owed is not None else round(a.value, 2),
        "updated": db.local_date(a.updated_at).isoformat() if a.updated_at else None,
    }


def list_assets(manager=None) -> list[dict]:
    session = _session()
    try:
        rows = session.query(db.AssetModel).order_by(db.AssetModel.kind, db.AssetModel.name).all()
        return [_to_dict(a, manager) for a in rows]
    finally:
        session.close()


def save_asset(name: str, kind: str = "other", value: float = 0.0, notes: str = "",
               linked_bank: str = "", linked_account: str = "", asset_id: int | None = None,
               manager=None, today: date | None = None) -> dict:
    """Create (no ``asset_id``) or edit an asset. A new value is added to its history."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Asset name is required")
    if kind not in KINDS:
        raise ValueError("Unknown asset type")
    if value is None or value < 0:
        raise ValueError("Value can't be negative")
    if bool(linked_bank) != bool(linked_account):
        raise ValueError("Pick both the bank and the loan account, or neither")
    if linked_bank and manager is not None and _loan_balance(manager, linked_bank, linked_account)[0] is None:
        raise ValueError(f"Loan account '{linked_bank} / {linked_account}' not found")
    today = today or date.today()
    session = _session()
    try:
        dup = session.query(db.AssetModel).filter(db.AssetModel.name == name)
        if asset_id:
            dup = dup.filter(db.AssetModel.id != asset_id)
        if dup.first():
            raise ValueError(f"An asset named '{name}' already exists")
        if asset_id:
            a = session.get(db.AssetModel, asset_id)
            if a is None:
                raise ValueError("Asset not found")
        else:
            a = db.AssetModel(name=name, value=0.0)
            session.add(a)
        changed = a.id is None or abs((a.value or 0.0) - value) > 0.004
        a.name, a.kind, a.value = name, kind, round(float(value), 2)
        a.notes = (notes or "").strip()[:300] or None
        a.linked_bank, a.linked_account = linked_bank or None, linked_account or None
        session.flush()
        if changed:
            existing = session.query(db.AssetValueModel).filter_by(asset_id=a.id, recorded_on=today).first()
            if existing:
                existing.value = a.value
            else:
                session.add(db.AssetValueModel(asset_id=a.id, value=a.value, recorded_on=today))
        session.commit()
        return _to_dict(a, manager)
    finally:
        session.close()


def delete_asset(asset_id: int) -> None:
    session = _session()
    try:
        session.query(db.AssetValueModel).filter_by(asset_id=asset_id).delete()
        if not session.query(db.AssetModel).filter_by(id=asset_id).delete():
            raise ValueError("Asset not found")
        session.commit()
    finally:
        session.close()


def asset_history(asset_id: int) -> list[dict]:
    session = _session()
    try:
        rows = (session.query(db.AssetValueModel).filter_by(asset_id=asset_id)
                .order_by(db.AssetValueModel.recorded_on).all())
        return [{"date": r.recorded_on.isoformat(), "value": round(r.value, 2)} for r in rows]
    finally:
        session.close()


def _covered(assets: list[dict]) -> set:
    """Loans whose home or vehicle is already entered as a linked asset (so not counted twice)."""
    return {(a["linked_bank"], a["linked_account"]) for a in assets
            if a["kind"] in ("property", "vehicle") and a["linked_account"]}


def _collateral(manager, covered: set, day: date = None) -> list[dict]:
    out = []
    for bank in manager.banks:
        for name, m in bank.mortgage_accounts.items():
            value = m.value_on(day) if hasattr(m, "value_on") else m.market_value
            if value and (bank.name, name) not in covered:
                is_home = getattr(m, "kind", "mortgage") == "mortgage"
                out.append({"name": name, "bank": bank.name, "value": round(value, 2),
                            "owed": round(m.current_principal, 2),
                            "kind": "Property" if is_home else "Vehicle",
                            "loan_kind": getattr(m, "kind", "mortgage")})
    return out


def home_values(manager, day: date = None) -> list[dict]:
    """
    Loan collateral that counts as an asset: a mortgage's home value, an auto
    loan's vehicle value (depreciated to ``day``), unless an asset linked to
    that loan already covers it.
    """
    return _collateral(manager, _covered(list_assets()), day)


loan_collateral = home_values


def other_assets_on(manager):
    """
    A function day -> assets + loan collateral on that day (vehicles keep
    depreciating), for projected net worth. Reads the database once.
    """
    try:
        assets = list_assets()
    except Exception:  # noqa: BLE001 - no database (plain library use)
        assets = []
    fixed = sum(a["value"] for a in assets)
    covered = _covered(assets)
    return lambda day=None: round(fixed + sum(c["value"] for c in _collateral(manager, covered, day)), 2)


def other_assets_total(manager, day: date = None) -> float:
    """Assets and loan collateral, i.e. everything net worth counts besides cash in bank accounts."""
    return other_assets_on(manager)(day)


def net_worth_breakdown(manager) -> dict:
    """Everything that makes up net worth, grouped for display."""
    cash = sum(b.total_balance() for b in manager.banks)
    assets = list_assets(manager)
    homes = home_values(manager)
    by_kind: dict = {}
    for a in assets:
        by_kind[a["kind_label"]] = by_kind.get(a["kind_label"], 0.0) + a["value"]
    for h in homes:
        by_kind[h["kind"]] = by_kind.get(h["kind"], 0.0) + h["value"]
    debts = {"Credit cards": sum(c.balance for b in manager.banks for c in b.credit_accounts.values())}
    loan_groups = {"mortgage": "Mortgages", "auto": "Auto loans", "student": "Student loans"}
    for kind in ("Mortgages", "Auto loans", "Student loans", "Other loans"):
        debts[kind] = 0.0
    for b in manager.banks:
        for m in b.mortgage_accounts.values():
            group = loan_groups.get(getattr(m, "kind", "mortgage"), "Other loans")
            debts[group] += m.current_principal
    debts["HELOCs"] = sum(h.balance for b in manager.banks for h in b.heloc_accounts.values())
    total_assets = cash + sum(by_kind.values())
    total_debt = sum(debts.values())
    return {
        "cash": round(cash, 2),
        "assets_by_kind": [{"kind": k, "value": round(v, 2)} for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])],
        "debts": [{"kind": k, "value": round(v, 2)} for k, v in debts.items() if v > 0.005],
        "total_assets": round(total_assets, 2),
        "total_debt": round(total_debt, 2),
        "net_worth": round(total_assets - total_debt, 2),
        "assets": assets,
        "homes": homes,
    }
