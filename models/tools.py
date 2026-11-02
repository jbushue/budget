"""
Money-moving tools and calculators that used to be CLI-only: transfers,
promo purchases and payments, extra mortgage principal, the amortization
schedule and early-payoff math, one-pass balance updates, resetting a
floating bill to its estimate, payment-strategy comparison, and database
info. GraphQL wrappers live in models/gql_tools.py.

Every function raises ToolError with a message fit to show the user.
"""

from __future__ import annotations

import os
from datetime import date, timedelta


class ToolError(Exception):
    pass


STRATEGIES = {
    "maximize_discretionary": "Keep the most cash on hand",
    "minimize_interest": "Pay the least interest",
    "payoff_credit_account": "Pay off one card faster",
}


# ── lookups ──────────────────────────────────────────────────────────────

def _bank(manager, name: str):
    bank = next((b for b in manager.banks if b.name == name), None)
    if bank is None:
        raise ToolError(f"Bank '{name}' not found")
    return bank


def _cash_account(manager, bank_name: str, account_name: str):
    bank = _bank(manager, bank_name)
    acc = bank.accounts.get(account_name)
    if acc is None:
        raise ToolError(f"'{account_name}' isn't a checking or savings account at {bank_name}")
    return bank, acc


def _credit(manager, bank_name: str, account_name: str):
    bank = _bank(manager, bank_name)
    acc = bank.credit_accounts.get(account_name)
    if acc is None:
        raise ToolError(f"Card '{account_name}' not found at {bank_name}")
    return bank, acc


def _mortgage(manager, bank_name: str, account_name: str):
    bank = _bank(manager, bank_name)
    acc = bank.mortgage_accounts.get(account_name)
    if acc is None:
        raise ToolError(f"Mortgage '{account_name}' not found at {bank_name}")
    return bank, acc


def _positive(amount: float, what: str = "Amount") -> float:
    if amount is None or amount <= 0:
        raise ToolError(f"{what} must be more than $0")
    return round(float(amount), 2)


def _history(bank: str, account: str, kind: str, new: float, prev: float, note: str) -> None:
    from models.simplefin import _record_balance_history
    _record_balance_history(bank, account, kind, new, prev, note)


def _withdraw(bank, acc, account_name: str, amount: float, description: str) -> float:
    if acc.balance < amount:
        raise ToolError(f"{bank.name} {account_name} only has ${acc.balance:,.2f}")
    prev = acc.balance
    acc.withdraw(amount, description=description)
    _history(bank.name, account_name, "bank", acc.balance, prev, description)
    return prev


# ── transfers ────────────────────────────────────────────────────────────

def transfer(manager, from_bank: str, from_account: str, to_bank: str, to_account: str,
             amount: float, note: str = "") -> str:
    """Move money between two checking/savings accounts (any banks)."""
    amount = _positive(amount)
    if (from_bank, from_account) == (to_bank, to_account):
        raise ToolError("Pick two different accounts")
    src_bank, src = _cash_account(manager, from_bank, from_account)
    dst_bank, dst = _cash_account(manager, to_bank, to_account)
    label = note.strip() or f"Transfer {from_account} → {to_account}"
    _withdraw(src_bank, src, from_account, amount, label)
    prev = dst.balance
    dst.deposit(amount, description=label)
    _history(dst_bank.name, to_account, "bank", dst.balance, prev, label)
    return f"Moved ${amount:,.2f} from {from_account} to {to_account}"


# ── promotional offers ───────────────────────────────────────────────────

def _promo(card, promo_name: str):
    promo = next((p for p in card.active_promos if p.promo_name == promo_name), None)
    if promo is None:
        raise ToolError(f"Promo '{promo_name}' not found on {card.account_name}")
    return promo


def promo_purchase(manager, bank_name: str, account_name: str, promo_name: str, amount: float,
                   description: str = "") -> str:
    """Charge a purchase to a card and put it on a promo balance (if the promo allows it)."""
    amount = _positive(amount)
    bank, card = _credit(manager, bank_name, account_name)
    promo = _promo(card, promo_name)
    if amount > card.available_credit:
        raise ToolError(f"Only ${card.available_credit:,.2f} of credit is available on {account_name}")
    on_promo = promo.is_valid_for_purchase(amount)
    prev = card.balance
    card.make_purchase(amount, description=description.strip() or f"Purchase on {promo_name}",
                       promo_name=promo_name)
    _history(bank.name, account_name, "credit", card.balance, prev, f"Purchase ${amount:,.2f} ({promo_name})")
    if on_promo:
        return f"Added ${amount:,.2f} to {promo_name}"
    return (f"Charged ${amount:,.2f} to {account_name}, but the promo has ended or is over its limit, "
            "so it's on the regular balance")


def promo_payment(manager, bank_name: str, account_name: str, promo_name: str, amount: float,
                  source_bank: str, source_account: str) -> str:
    """Pay down a promo balance from a checking/savings account."""
    amount = _positive(amount)
    bank, card = _credit(manager, bank_name, account_name)
    _promo(card, promo_name)
    owed = card.promo_balance.get(promo_name, 0.0)
    if owed <= 0:
        raise ToolError(f"{promo_name} has no balance to pay")
    amount = min(amount, round(owed, 2), round(card.balance, 2))
    src_bank, src = _cash_account(manager, source_bank, source_account)
    if src.balance < amount:
        raise ToolError(f"{source_bank} {source_account} only has ${src.balance:,.2f}")
    prev_src, prev_card = src.balance, card.balance
    card.make_payment(amount, source_account=source_account, source_bank=src_bank,
                      description=f"Payment to {promo_name}", promo_name=promo_name)
    _history(src_bank.name, source_account, "bank", src.balance, prev_src, f"Payment to {account_name} ({promo_name})")
    _history(bank.name, account_name, "credit", card.balance, prev_card, f"Promo payment ({promo_name})")
    left = card.promo_balance.get(promo_name, 0.0)
    return f"Paid ${amount:,.2f} to {promo_name}" + (" — paid off!" if left <= 0.005 else f"; ${left:,.2f} left")


# ── mortgages ────────────────────────────────────────────────────────────

def extra_principal(manager, bank_name: str, account_name: str, amount: float,
                    source_bank: str = "", source_account: str = "") -> str:
    """Pay extra toward a mortgage's principal, optionally taking it from a cash account."""
    amount = _positive(amount)
    bank, loan = _mortgage(manager, bank_name, account_name)
    if loan.current_principal <= 0:
        raise ToolError(f"{account_name} is already paid off")
    amount = min(amount, round(loan.current_principal, 2))
    if source_bank and source_account:
        src_bank, src = _cash_account(manager, source_bank, source_account)
        _withdraw(src_bank, src, source_account, amount, f"Extra principal to {account_name}")
    prev = loan.current_principal
    loan.make_extra_principal_payment(amount, source_bank or None, source_account or None)
    _history(bank.name, account_name, "mortgage", loan.current_principal, prev, f"Extra principal ${amount:,.2f}")
    return f"Paid ${amount:,.2f} extra principal; ${loan.current_principal:,.2f} left"


def mortgage_details(manager, bank_name: str, account_name: str, extra_monthly: float = 0.0) -> dict:
    """Where a mortgage stands, its amortization schedule, and what extra monthly principal would save."""
    _, loan = _mortgage(manager, bank_name, account_name)
    extra_monthly = max(0.0, float(extra_monthly or 0.0))
    schedule = loan.get_amortization_schedule()
    years: dict[int, dict] = {}
    for row in schedule:
        y = years.setdefault(row["date"].year, {"year": row["date"].year, "principal": 0.0, "interest": 0.0,
                                                "escrow": 0.0, "end_balance": 0.0})
        y["principal"] += row["principal"]
        y["interest"] += row["interest"]
        y["escrow"] += row["escrow"]
        y["end_balance"] = row["principal_remaining"]
    payoff = loan.calculate_payoff_with_extra(extra_monthly)
    return {
        "balance": loan.current_principal,
        "rate": loan.interest_rate,
        "monthly_payment": loan.total_monthly_payment,
        "principal_and_interest": loan.base_monthly_payment,
        "escrow": loan.escrow.total_monthly,
        "next_interest": loan.current_monthly_interest,
        "next_principal": loan.current_monthly_principal,
        "remaining_months": loan.remaining_months,
        "payoff_date": loan.payoff_date.isoformat() if loan.payoff_date else None,
        "interest_remaining": loan.total_interest_remaining,
        "equity": loan.equity,
        "ltv": loan.loan_to_value_ratio,
        "market_value": loan.market_value,
        "extra_monthly": extra_monthly,
        "months_saved": payoff["months_saved"],
        "interest_saved": round(payoff["interest_saved"], 2),
        "new_payoff_date": payoff["new_payoff_date"].isoformat(),
        "schedule": [dict(r, date=r["date"].isoformat()) for r in schedule[:12]],
        "years": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in y.items()} for y in years.values()],
    }


# ── balances ─────────────────────────────────────────────────────────────

def update_balances(manager, updates: list[dict]) -> int:
    """Set several balances at once. Each update: {bank, account, kind, balance}; kind is
    bank | credit | mortgage | heloc. Unchanged balances are skipped. Returns how many changed."""
    changed = 0
    for u in updates:
        bank = _bank(manager, str(u.get("bank", "")))
        name, kind = str(u.get("account", "")), str(u.get("kind", "bank"))
        try:
            new = round(float(u.get("balance")), 2)
        except (TypeError, ValueError):
            raise ToolError(f"Enter a number for {name}")
        if kind == "credit":
            acc = bank.credit_accounts.get(name)
            prev = acc.balance if acc else None
            if acc and abs(prev - new) >= 0.005:
                bank.update_credit_balance(name, new)
        elif kind == "mortgage":
            acc = bank.mortgage_accounts.get(name)
            prev = acc.current_principal if acc else None
            if acc and abs(prev - new) >= 0.005:
                acc.current_principal = new
        elif kind == "heloc":
            acc = bank.heloc_accounts.get(name)
            prev = acc.balance if acc else None
            if acc and abs(prev - new) >= 0.005:
                acc.balance = new
        else:
            acc = bank.accounts.get(name)
            prev = acc.balance if acc else None
            if acc and abs(prev - new) >= 0.005:
                bank.update_account_balance(name, new)
        if acc is None:
            raise ToolError(f"'{name}' not found at {bank.name}")
        if abs(prev - new) >= 0.005:
            _history(bank.name, name, kind, new, prev, "Balance check-in")
            changed += 1
    return changed


# ── bills ────────────────────────────────────────────────────────────────

def reset_bill_to_estimate(manager, bill_name: str, due_date: str | None = None) -> str:
    bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
    if bill is None:
        raise ToolError(f"Bill '{bill_name}' not found")
    if not hasattr(bill, "reset_to_estimate"):
        raise ToolError(f"{bill_name} has a fixed amount")
    from models.gql_bills import resolve_due
    try:
        due = resolve_due(bill, due_date)
    except ValueError as e:
        raise ToolError(str(e))
    bill.reset_to_estimate(due)
    return f"{bill_name} due {due:%b} {due.day} is back to its ${bill.amount:,.2f} estimate"


# ── payment strategies ───────────────────────────────────────────────────

def credit_targets(manager) -> list[str]:
    return [name for b in manager.banks for name, acc in b.credit_accounts.items() if acc.balance > 0]


def compare_strategies(manager, days: int = 90, target_account: str = "") -> list[dict]:
    """
    Each goal's year-long plan (the same runs the app uses, see models/plan.py)
    over the first ``days``, measured the same way as the Optimizer page.
    """
    from models.plan import runs_for
    from models.payment_insights import summarize_simulation
    days = max(14, min(int(days or 90), 365))
    goals = ["maximize_discretionary", "minimize_interest"]
    if target_account:
        if target_account not in credit_targets(manager):
            raise ToolError(f"'{target_account}' isn't a card with a balance")
        goals.append("payoff_credit_account")
    out = []
    for goal in goals:
        runs, _, opt = runs_for(manager, days, goal,
                                target_account if goal == "payoff_credit_account" else None)
        s = summarize_simulation(opt, manager.banks)
        extra = [{"date": cf["date"].isoformat(), "account": cf.get("to_account") or cf.get("account", ""),
                  "amount": round(-cf["amount"], 2)}
                 for cf in opt["cash_flow"] if cf.get("type") in ("EXTRA_CREDIT_PAYMENT", "PROMO_PAYOFF")]
        out.append({
            "goal": goal,
            "label": STRATEGIES[goal],
            "final_cash": s["ending_cash"],
            "ending_debt": s["ending_debt"],
            "outcome": s["outcome"],
            "lowest_checking": s["lowest_checking"],
            "late": len(s["late_payments"]),
            "interest_paid": s["interest_charged"],
            "interest_earned": s["interest_earned"],
            "fees": s["fees"],
            "problems": len([v for v in runs.plan.violations if not v.startswith("INFO")]),
            "extra_payments": extra,
            "extra_total": round(sum(p["amount"] for p in extra), 2),
        })
    return out


# ── database info ────────────────────────────────────────────────────────

TABLE_LABELS = {
    "banks": "Banks", "bank_accounts": "Checking & savings", "credit_accounts": "Cards & loans",
    "mortgage_accounts": "Mortgages", "heloc_accounts": "Home equity lines", "bills": "Bills",
    "income_sources": "Income sources", "bill_groups": "Loan groups", "ledger_transactions": "Transactions",
    "categories": "Categories", "category_rules": "Category rules", "savings_goals": "Goals",
    "promo_offers": "Promo offers", "assets": "Assets", "balance_history": "Balance updates", "bill_payments": "Bill payments",
    "net_worth_snapshots": "Net worth history", "activity_log": "Activity entries", "users": "Users",
}


def database_info() -> dict:
    from sqlalchemy import text
    from models.database import get_session
    session = get_session()
    try:
        path = session.bind.url.database or ""
        names = [r[0] for r in session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))]
        counts = []
        for name in sorted(names):
            if name not in TABLE_LABELS:
                continue
            n = session.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() or 0
            counts.append({"table": name, "label": TABLE_LABELS[name], "rows": int(n)})
    finally:
        session.close()
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    return {"path": path, "size_bytes": size, "tables": counts}
