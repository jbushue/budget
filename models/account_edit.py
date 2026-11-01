"""
Editing banks and accounts after they're created: every setting, plus
renaming an account or moving it to another bank.

Bank and account names are stored as plain strings in many places (bill
payment sources, linked "[Auto] … Payment" bills, bill groups, income
splits, transactions, goals, SimpleFIN mappings, balance history, the
everyday-spending setting). Saving finds database rows by name, so a rename
that only touched the in-memory object would look like "delete the old
account, add a new one" and lose its history. Renames therefore update the
database rows and every reference first, then the objects in memory, so the
normal save that follows updates rows in place.
"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import text

from models import database as db
from models.fixed_bill import AccountLinkedBill
from models.mortgage_account import EscrowBreakdown
from models.types import AccountType, BANK_ACCOUNT_KINDS, CreditAccountStatus

# kind -> (Bank attribute holding these accounts, database table)
KINDS = {
    **{k: ("accounts", "bank_accounts") for k in BANK_ACCOUNT_KINDS if k != "mortgage"},
    "credit": ("credit_accounts", "credit_accounts"),
    "mortgage": ("mortgage_accounts", "mortgage_accounts"),
    "heloc": ("heloc_accounts", "heloc_accounts"),
}
BANK_KINDS = tuple(k for k in BANK_ACCOUNT_KINDS if k != "mortgage")
BANK_TYPES = ("traditional", "credit_issuer", "mortgage_lender")


class EditError(ValueError):
    """A change that can't be made; the message is shown to the user."""


def _bank(manager, name):
    return next((b for b in manager.banks if b.name == name), None)


def find_account(manager, bank_name: str, account_name: str, kind: str):
    """(bank, account) or raise EditError."""
    if kind not in KINDS:
        raise EditError(f"Unknown account type '{kind}'")
    bank = _bank(manager, bank_name)
    if not bank:
        raise EditError(f"Bank '{bank_name}' not found")
    account = getattr(bank, KINDS[kind][0]).get(account_name)
    if account is None:
        raise EditError(f"Account '{account_name}' not found in {bank_name}")
    return bank, account


def _linked_bill(manager, account):
    return next((b for b in manager.bills if isinstance(b, AccountLinkedBill) and b.linked_account is account), None)


def _tables(session) -> set[str]:
    return set(session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())


def _kind_clause(kind: str) -> str:
    """SQL condition matching an account_type column to this kind of account."""
    if kind in BANK_KINDS:
        return "{col} NOT IN ('credit', 'mortgage', 'heloc')"
    return f"{{col}} = '{kind}'"


# ─────────────────────────────────────────────────────────────────────────
#  Renaming
# ─────────────────────────────────────────────────────────────────────────

def rename_bank(manager, old: str, new: str) -> None:
    """Rename a bank everywhere it's referenced."""
    new = (new or "").strip()
    if not new:
        raise EditError("Bank name can't be empty")
    if new == old:
        return
    if _bank(manager, new):
        raise EditError(f"A bank named '{new}' already exists")
    bank = _bank(manager, old)
    if not bank:
        raise EditError(f"Bank '{old}' not found")

    session = db.get_session()
    try:
        p = {"old": old, "new": new}
        session.execute(text("UPDATE banks SET name = :new WHERE name = :old"), p)
        for table, col in (("bills", "linked_bank_name"), ("bills", "preferred_source_bank"),
                           ("bill_payments", "source_bank"), ("mortgage_accounts", "preferred_source_bank"),
                           ("heloc_accounts", "preferred_source_bank"), ("bill_groups", "preferred_source_bank"),
                           ("bill_group_members", "bank_name"), ("ledger_transactions", "bank_name"),
                           ("savings_goals", "bank_name")):
            session.execute(text(f"UPDATE {table} SET {col} = :new WHERE {col} = :old"), p)
        tables = _tables(session)
        if "balance_history" in tables:
            session.execute(text("UPDATE balance_history SET bank_name = :new WHERE bank_name = :old"), p)
        if "simplefin_account_mappings" in tables:
            session.execute(text("UPDATE simplefin_account_mappings SET local_bank_name = :new "
                                 "WHERE local_bank_name = :old"), p)
        _rename_spending_account(session, old, None, new, None)
        session.commit()
    finally:
        session.close()

    bank.name = new
    for bill in manager.bills:
        if isinstance(bill, AccountLinkedBill) and bill.linked_bank_name == old:
            bill.linked_bank_name = new
            bill.account_link_key = f"{bill.linked_account_type}:{new}:{bill.linked_account.account_name}"
        if bill.preferred_source_bank == old:
            bill.preferred_source_bank = new
    for b in manager.banks:
        for acc in list(b.mortgage_accounts.values()) + list(b.heloc_accounts.values()):
            if acc.preferred_source_bank == old:
                acc.preferred_source_bank = new
    for group in manager.bill_groups:
        if group.preferred_source_bank == old:
            group.preferred_source_bank = new
        for member in group.members:
            if member.bank_name == old:
                member.bank_name = new
    _reload_spending(manager)


def rename_account(manager, kind: str, bank_name: str, old: str, new_name: str | None = None,
                   new_bank_name: str | None = None) -> None:
    """Rename an account and/or move it to another bank, everywhere it's referenced."""
    bank, account = find_account(manager, bank_name, old, kind)
    if not _check_rename(manager, kind, bank_name, old, new_name, new_bank_name):
        return
    new = (new_name if new_name is not None else old).strip()
    target_name = new_bank_name or bank_name
    target = _bank(manager, target_name)
    attr, table = KINDS[kind]

    session = db.get_session()
    try:
        old_bank_id = session.execute(text("SELECT id FROM banks WHERE name = :n"), {"n": bank_name}).scalar()
        new_bank_id = session.execute(text("SELECT id FROM banks WHERE name = :n"), {"n": target_name}).scalar()
        p = {"ob": bank_name, "nb": target_name, "oa": old, "na": new,
             "obid": old_bank_id, "nbid": new_bank_id, "kind": kind,
             "obill": f"[Auto] {old} Payment", "nbill": f"[Auto] {new} Payment"}
        if old_bank_id is not None and new_bank_id is not None:
            session.execute(text(f"UPDATE {table} SET account_name = :na, bank_id = :nbid "
                                 "WHERE account_name = :oa AND bank_id = :obid"), p)
        if kind in ("credit", "mortgage", "heloc"):
            session.execute(text("UPDATE bills SET linked_bank_name = :nb, linked_account_name = :na, "
                                 "bill_name = :nbill WHERE linked_account_type = :kind "
                                 "AND linked_bank_name = :ob AND linked_account_name = :oa"), p)
            session.execute(text("UPDATE ledger_transactions SET matched_bill = :nbill WHERE matched_bill = :obill"), p)
            session.execute(text("UPDATE savings_goals SET linked_bill = :nbill WHERE linked_bill = :obill"), p)
        if kind == "credit":
            session.execute(text("UPDATE bill_group_members SET bank_name = :nb, account_name = :na "
                                 "WHERE bank_name = :ob AND account_name = :oa"), p)
        if kind in BANK_KINDS:
            # Places that pay from (or save into) a bank account
            for t, b, a in (("bills", "preferred_source_bank", "preferred_source_account"),
                            ("bill_payments", "source_bank", "source_account"),
                            ("mortgage_accounts", "preferred_source_bank", "preferred_source_account"),
                            ("heloc_accounts", "preferred_source_bank", "preferred_source_account"),
                            ("bill_groups", "preferred_source_bank", "preferred_source_account")):
                session.execute(text(f"UPDATE {t} SET {b} = :nb, {a} = :na WHERE {b} = :ob AND {a} = :oa"), p)
        for t in ("ledger_transactions", "savings_goals"):
            session.execute(text(f"UPDATE {t} SET bank_name = :nb, account_name = :na "
                                 "WHERE bank_name = :ob AND account_name = :oa"), p)
        tables = _tables(session)
        if "balance_history" in tables:
            session.execute(text("UPDATE balance_history SET bank_name = :nb, account_name = :na "
                                 "WHERE bank_name = :ob AND account_name = :oa AND "
                                 + _kind_clause(kind).format(col="account_type")), p)
        if "simplefin_account_mappings" in tables:
            session.execute(text("UPDATE simplefin_account_mappings SET local_bank_name = :nb, "
                                 "local_account_name = :na WHERE local_bank_name = :ob AND local_account_name = :oa "
                                 "AND " + _kind_clause(kind).format(col="local_account_type")), p)
        if kind in BANK_KINDS:
            _rename_spending_account(session, bank_name, old, target_name, new)
        session.commit()
    finally:
        session.close()

    # In memory
    del getattr(bank, attr)[old]
    account.account_name = new
    getattr(target, attr)[new] = account
    linked = _linked_bill(manager, account)
    if linked:
        linked.bill_name = f"[Auto] {new} Payment"
        linked.linked_bank_name = target_name
        linked.account_link_key = f"{kind}:{target_name}:{new}"
    if kind == "credit":
        for group in manager.bill_groups:
            for member in group.members:
                if member.bank_name == bank_name and member.account_name == old:
                    member.bank_name, member.account_name = target_name, new
        if manager.target_credit_account == old:
            manager.target_credit_account = new
    if kind in BANK_KINDS:
        sources = list(manager.bills) + list(manager.bill_groups) + [
            a for b in manager.banks for a in list(b.mortgage_accounts.values()) + list(b.heloc_accounts.values())]
        for obj in sources:
            if obj.preferred_source_bank == bank_name and obj.preferred_source_account == old:
                obj.preferred_source_bank, obj.preferred_source_account = target_name, new
        # Income splits name the account only (not its bank)
        if not any(old in b.accounts for b in manager.banks):
            for income in manager.income_sources:
                for entry in getattr(income.distribution, "distribution", None) or []:
                    if entry.account_name == old:
                        entry.account_name = new
        _reload_spending(manager)


def _check_rename(manager, kind, bank_name, old, new_name, new_bank_name) -> bool:
    """Raise EditError if the rename/move can't be done; False if it changes nothing."""
    new = (new_name if new_name is not None else old).strip()
    target_name = new_bank_name or bank_name
    if not new:
        raise EditError("Account name can't be empty")
    if new == old and target_name == bank_name:
        return False
    target = _bank(manager, target_name)
    if not target:
        raise EditError(f"Bank '{target_name}' not found")
    if new in getattr(target, KINDS[kind][0]):
        raise EditError(f"{target_name} already has an account named '{new}'")
    return True


def _rename_spending_account(session, old_bank, old_account, new_bank, new_account) -> None:
    """Keep the everyday-spending setting ("Bank:Account") pointing at the renamed bank/account."""
    row = session.execute(text("SELECT value FROM app_settings WHERE key = 'spending_account'")).scalar()
    if not row:
        return
    try:
        value = json.loads(row)
    except (TypeError, ValueError):
        value = row
    if not isinstance(value, str) or ":" not in value:
        return
    bank, account = value.split(":", 1)
    if bank != old_bank or (old_account is not None and account != old_account):
        return
    updated = f"{new_bank}:{new_account if new_account is not None else account}"
    session.execute(text("UPDATE app_settings SET value = :v WHERE key = 'spending_account'"),
                    {"v": json.dumps(updated)})


def _reload_spending(manager) -> None:
    try:
        from models.app_settings import get_settings
        manager.apply_settings(get_settings())
    except Exception:  # noqa: BLE001 - settings are optional for library use
        pass


# ─────────────────────────────────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────────────────────────────────

def _day(value, label, allow_clear=False):
    """A day of month 1-31; 0 clears it when allowed."""
    if value is None:
        return None
    value = int(value)
    if allow_clear and value == 0:
        return 0
    if not 1 <= value <= 31:
        raise EditError(f"{label} must be between 1 and 31")
    return value


def _non_negative(value, label):
    if value is not None and value < 0:
        raise EditError(f"{label} can't be negative")
    return value


def _source(manager, bank_name, account_name):
    """Validated (bank, account) pay-from pair; empty strings clear it."""
    if not bank_name and not account_name:
        return None, None
    bank = _bank(manager, bank_name)
    if not bank or account_name not in bank.accounts:
        raise EditError(f"Pay-from account '{bank_name} / {account_name}' not found")
    return bank_name, account_name


def update_account(manager, kind: str, bank_name: str, account_name: str, changes: dict) -> str:
    """
    Apply ``changes`` (only the keys present) to an account and return its
    (possibly new) name. Everything is validated before anything changes.

    Keys: name, bank_name, account_type (any bank-account kind), balance,
    refill_amount, refill_day (0 clears), weekly_spending, offsets_everyday,
    interest_rate, interest_accrual_date (0 clears), credit_limit,
    payment_due_date, statement_date (0 clears), status, original_principal,
    current_principal, loan_term_months, start_date (ISO), escrow_property_tax,
    escrow_insurance, escrow_pmi, escrow_hoa, escrow_other, market_value
    (0 clears), preferred_source_bank / preferred_source_account ("" clears),
    draw_period_months, total_term_months.
    """
    bank, acc = find_account(manager, bank_name, account_name, kind)
    c = {k: v for k, v in changes.items() if v is not None}
    renaming = "name" in c or "bank_name" in c
    if renaming:
        _check_rename(manager, kind, bank_name, account_name, c.get("name"), c.get("bank_name"))
    _non_negative(c.get("interest_rate"), "Interest rate")
    start = None
    if "start_date" in c:
        try:
            start = date.fromisoformat(c["start_date"])
        except ValueError:
            raise EditError("Start date must be YYYY-MM-DD") from None

    if kind in BANK_KINDS:
        new_type = c.get("account_type") or acc.account_type.value
        if new_type not in BANK_KINDS:
            raise EditError(f"Unknown account type '{new_type}'")
        day = _day(c.get("interest_accrual_date"), "Interest day", allow_clear=True)
        refill_day = _day(c.get("refill_day"), "Refill day", allow_clear=True)
        _non_negative(c.get("refill_amount"), "Refill amount")
        _non_negative(c.get("weekly_spending"), "Weekly spending")
        if "balance" in c:
            acc.balance = float(c["balance"])
        if "interest_rate" in c:
            acc.interest_rate = float(c["interest_rate"])
        if day is not None:
            acc.interest_accrual_date = day or None
        acc.account_type = AccountType(new_type)
        if "refill_amount" in c:
            acc.refill_amount = float(c["refill_amount"])
        if refill_day is not None:
            acc.refill_day = refill_day or None
        if "weekly_spending" in c:
            acc.weekly_spending = float(c["weekly_spending"])
        if "offsets_everyday" in c:
            acc.offsets_everyday = bool(c["offsets_everyday"])

    elif kind == "credit":
        limit = c.get("credit_limit", acc.credit_limit)
        if limit <= 0:
            raise EditError("Credit limit must be greater than 0")
        due = _day(c.get("payment_due_date"), "Payment due day")
        statement = _day(c.get("statement_date"), "Statement day", allow_clear=True)
        status = None
        if "status" in c:
            try:
                status = CreditAccountStatus[str(c["status"]).upper()]
            except KeyError:
                raise EditError("Status must be active, closed or frozen") from None
        promo_total = sum(acc.promo_balance.values())
        if "balance" in c:
            balance = float(c["balance"])
            if balance < promo_total - 0.005:
                raise EditError(f"Balance can't be less than the ${promo_total:,.2f} on promo offers")
            acc.balance = balance
            acc.regular_balance = round(balance - promo_total, 2)
        acc.credit_limit = float(limit)
        if "interest_rate" in c:
            acc.interest_rate = float(c["interest_rate"])
        if due is not None:
            acc.payment_due_date = due
        if statement is not None:
            acc.statement_date = statement or None
        if status is not None:
            acc.status = status

    elif kind == "mortgage":
        original = c.get("original_principal", acc.original_principal)
        current = c.get("current_principal", acc.current_principal)
        term = c.get("loan_term_months", acc.loan_term_months)
        if original <= 0:
            raise EditError("Original loan amount must be greater than 0")
        if current < 0 or current > original:
            raise EditError("Current principal must be between 0 and the original loan amount")
        if term <= 0:
            raise EditError("Loan term must be at least 1 month")
        due = _day(c.get("payment_due_date"), "Payment due day")
        escrow_keys = ("property_tax", "insurance", "pmi", "hoa", "other")
        for key in escrow_keys:
            _non_negative(c.get(f"escrow_{key}"), "Escrow amounts")
        _non_negative(c.get("market_value"), "Market value")
        src = _source(manager, c["preferred_source_bank"], c.get("preferred_source_account", "")) \
            if "preferred_source_bank" in c else None
        acc.original_principal, acc.current_principal, acc.loan_term_months = float(original), float(current), int(term)
        if "interest_rate" in c:
            acc.interest_rate = float(c["interest_rate"])
        if due is not None:
            acc.payment_due_date = due
        if start:
            acc.start_date = start
        if any(f"escrow_{k}" in c for k in escrow_keys):
            e = acc.escrow
            acc.escrow = EscrowBreakdown(
                property_tax_monthly=c.get("escrow_property_tax", e.property_tax_monthly),
                homeowners_insurance_monthly=c.get("escrow_insurance", e.homeowners_insurance_monthly),
                pmi_monthly=c.get("escrow_pmi", e.pmi_monthly), hoa_monthly=c.get("escrow_hoa", e.hoa_monthly),
                other_monthly=c.get("escrow_other", e.other_monthly))
        if "market_value" in c:
            acc.market_value = float(c["market_value"]) or None
        if src is not None:
            _set_source(manager, acc, *src)

    elif kind == "heloc":
        limit = c.get("credit_limit", acc.credit_limit)
        draw = c.get("draw_period_months", acc.draw_period_months)
        total = c.get("total_term_months", acc.total_term_months)
        balance = c.get("balance", acc.balance)
        if limit <= 0:
            raise EditError("Credit limit must be greater than 0")
        if draw <= 0 or total <= draw:
            raise EditError("The total term must be longer than the draw period")
        if balance < 0:
            raise EditError("Balance can't be negative")
        due = _day(c.get("payment_due_date"), "Payment due day")
        src = _source(manager, c["preferred_source_bank"], c.get("preferred_source_account", "")) \
            if "preferred_source_bank" in c else None
        acc.credit_limit, acc.draw_period_months, acc.total_term_months = float(limit), int(draw), int(total)
        acc.balance = float(balance)
        if "interest_rate" in c:
            acc.interest_rate = float(c["interest_rate"])
        if due is not None:
            acc.payment_due_date = due
        if start:
            acc.start_date = start
        if src is not None:
            _set_source(manager, acc, *src)

    name = account_name
    if renaming:
        rename_account(manager, kind, bank_name, account_name, c.get("name"), c.get("bank_name"))
        name = (c.get("name") or account_name).strip()
    manager.invalidate_plan_cache()
    return name


def _set_source(manager, account, bank_name, account_name) -> None:
    """Set a mortgage/HELOC's pay-from account, and its payment bill's (which is what's used)."""
    account.preferred_source_bank, account.preferred_source_account = bank_name, account_name
    linked = _linked_bill(manager, account)
    if linked:
        linked.preferred_source_bank, linked.preferred_source_account = bank_name, account_name


def update_bank(manager, name: str, new_name: str | None = None, bank_type: str | None = None) -> str:
    """Rename a bank and/or change its type; returns its (possibly new) name."""
    bank = _bank(manager, name)
    if not bank:
        raise EditError(f"Bank '{name}' not found")
    if bank_type is not None and bank_type not in BANK_TYPES:
        raise EditError("Bank type must be traditional, credit_issuer or mortgage_lender")
    if new_name is not None and new_name.strip() != name:
        rename_bank(manager, name, new_name)
        name = new_name.strip()
    if bank_type is not None:
        bank.bank_type = bank_type
    return name
