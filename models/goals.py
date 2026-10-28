"""
Savings goals and sinking funds.

A goal is money you're setting aside: a target amount, an optional target
date, and the account the money sits in. "Saved so far" is tracked here
(not by moving money), so a goal can live in your checking account.

Money set aside in a CHECKING account is reserved: the Dashboard subtracts
it from Safe to spend so you don't spend it by accident. Goals in savings
accounts are already out of the way.

A sinking fund is a goal linked to a bill that isn't paid monthly (car
insurance every 6 months, an annual subscription, ...). Its target is the
bill amount and its date the bill's next due date; once that bill has been
paid the fund rolls forward to the next due date.
"""

from __future__ import annotations

from datetime import date, timedelta

from models import database as db
from models.types import BillFrequency

NON_MONTHLY = (BillFrequency.QUARTERLY, BillFrequency.SEMI_ANNUAL, BillFrequency.YEARLY)


def _session():
    return db.get_session()


def _account_type(manager, bank_name: str | None, account_name: str | None) -> str | None:
    if not bank_name or not account_name or manager is None:
        return None
    bank = next((b for b in manager.banks if b.name == bank_name), None)
    if bank is None:
        return None
    acct = bank.accounts.get(account_name)
    return acct.account_type.value if acct is not None and hasattr(acct.account_type, "value") else (
        str(acct.account_type) if acct is not None else None)


def _is_checking(manager, bank_name, account_name) -> bool:
    """Blank account = main checking (that's where unassigned set-asides live)."""
    if not bank_name or not account_name:
        return True
    return _account_type(manager, bank_name, account_name) == "checking"


def _months_between(start: date, end: date) -> float:
    return max(0.0, (end - start).days / 30.44)


def _find_bill(manager, name: str | None):
    if not name or manager is None:
        return None
    return next((b for b in manager.bills if b.bill_name == name), None)


def _goal_dict(manager, g: db.SavingsGoalModel, today: date) -> dict:
    remaining = max(0.0, g.target_amount - g.saved_amount)
    monthly = None
    per_paycheck = None
    months_left = None
    on_track = None
    if g.target_date:
        months_left = _months_between(today, g.target_date)
        if remaining > 0:
            monthly = remaining if months_left < 1 else remaining / months_left
            paydays = _paydays_until(manager, today, g.target_date)
            per_paycheck = remaining / paydays if paydays else remaining
        # On track = saved at least the share of the target that time elapsed implies
        created = db.local_date(g.created_at) if g.created_at else today
        total_days = max(1, (g.target_date - created).days)
        expected = g.target_amount * min(1.0, max(0.0, (today - created).days / total_days))
        on_track = g.saved_amount + 0.005 >= expected
    return {
        "id": g.id,
        "name": g.name,
        "target_amount": round(g.target_amount, 2),
        "saved_amount": round(g.saved_amount, 2),
        "remaining": round(remaining, 2),
        "progress": round(min(100.0, g.saved_amount / g.target_amount * 100) if g.target_amount else 100.0, 1),
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "months_left": round(months_left, 1) if months_left is not None else None,
        "monthly_needed": round(monthly, 2) if monthly is not None else None,
        "per_paycheck_needed": round(per_paycheck, 2) if per_paycheck is not None else None,
        "on_track": on_track,
        "bank_name": g.bank_name or "",
        "account_name": g.account_name or "",
        "in_checking": _is_checking(manager, g.bank_name, g.account_name),
        "linked_bill": g.linked_bill,
        "complete": remaining <= 0.005,
    }


def _paydays_until(manager, start: date, end: date) -> int:
    if manager is None:
        return 0
    dates = set()
    for income in manager.income_sources:
        try:
            dates.update(d for d in income.get_pay_dates_in_range(start, end) if start < d <= end)
        except Exception:
            pass
    return len(dates)


# ─────────────────────────────────────────────────────────────────────────
#  CRUD
# ─────────────────────────────────────────────────────────────────────────

def list_goals(manager=None, today: date | None = None) -> list[dict]:
    today = today or date.today()
    roll_sinking_funds(manager, today)
    session = _session()
    try:
        rows = session.query(db.SavingsGoalModel).order_by(db.SavingsGoalModel.target_date.is_(None),
                                                           db.SavingsGoalModel.target_date,
                                                           db.SavingsGoalModel.name).all()
        return [_goal_dict(manager, g, today) for g in rows]
    finally:
        session.close()


def save_goal(name: str, target_amount: float, target_date: date | None = None, bank_name: str = "",
              account_name: str = "", saved_amount: float | None = None, linked_bill: str | None = None,
              goal_id: int | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Goal name is required")
    if target_amount is None or target_amount <= 0:
        raise ValueError("Target amount must be more than $0")
    if saved_amount is not None and saved_amount < 0:
        raise ValueError("Saved amount can't be negative")
    session = _session()
    try:
        clash = session.query(db.SavingsGoalModel).filter_by(name=name).first()
        if goal_id is not None:
            g = session.get(db.SavingsGoalModel, goal_id)
            if g is None:
                raise ValueError("Goal not found")
            if clash and clash.id != goal_id:
                raise ValueError(f"A goal named '{name}' already exists")
        else:
            if clash:
                raise ValueError(f"A goal named '{name}' already exists")
            g = db.SavingsGoalModel(name=name, saved_amount=0.0)
            session.add(g)
        g.name = name
        g.target_amount = round(float(target_amount), 2)
        g.target_date = target_date
        g.bank_name = bank_name or None
        g.account_name = account_name or None
        if saved_amount is not None:
            g.saved_amount = round(float(saved_amount), 2)
        if linked_bill is not None:
            g.linked_bill = linked_bill or None
        session.commit()
        return {"id": g.id, "name": g.name}
    finally:
        session.close()


def contribute(goal_id: int, amount: float) -> dict:
    """Add (or with a negative amount, take out) money set aside for a goal."""
    session = _session()
    try:
        g = session.get(db.SavingsGoalModel, goal_id)
        if g is None:
            raise ValueError("Goal not found")
        new = round(g.saved_amount + amount, 2)
        if new < -0.005:
            raise ValueError(f"Only ${g.saved_amount:,.2f} is set aside for {g.name}")
        g.saved_amount = max(0.0, new)
        session.commit()
        return {"id": g.id, "name": g.name, "saved_amount": g.saved_amount}
    finally:
        session.close()


def delete_goal(goal_id: int) -> None:
    session = _session()
    try:
        n = session.query(db.SavingsGoalModel).filter_by(id=goal_id).delete()
        session.commit()
        if not n:
            raise ValueError("Goal not found")
    finally:
        session.close()


def reserved_in_checking(manager) -> float:
    """Money set aside for goals that's sitting in checking (reduces Safe to spend)."""
    session = _session()
    try:
        total = 0.0
        for g in session.query(db.SavingsGoalModel).all():
            if g.saved_amount > 0 and _is_checking(manager, g.bank_name, g.account_name):
                total += min(g.saved_amount, g.target_amount)
        return round(total, 2)
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────
#  Sinking funds
# ─────────────────────────────────────────────────────────────────────────

def sinking_fund_suggestions(manager, today: date | None = None) -> list[dict]:
    """Non-monthly bills without a sinking fund, with what to set aside per month."""
    today = today or date.today()
    session = _session()
    try:
        linked = {g.linked_bill for g in session.query(db.SavingsGoalModel).all() if g.linked_bill}
    finally:
        session.close()
    out = []
    for bill in manager.bills if manager else []:
        if getattr(bill, "frequency", None) not in NON_MONTHLY or bill.bill_name in linked:
            continue
        if getattr(bill, "linked_account", None) is not None:
            continue
        try:
            due = bill.get_next_due_date(today - timedelta(days=1))
        except Exception:
            continue
        if due == date.max:
            continue
        months = _months_between(today, due)
        amount = bill.effective_amount
        out.append({
            "bill_name": bill.bill_name,
            "amount": round(amount, 2),
            "frequency": bill.frequency.value,
            "next_due": due.isoformat(),
            "monthly": round(amount / max(1.0, months), 2),
        })
    return sorted(out, key=lambda s: s["next_due"])


def create_sinking_fund(manager, bill_name: str, bank_name: str = "", account_name: str = "",
                        saved_amount: float = 0.0, today: date | None = None) -> dict:
    today = today or date.today()
    bill = _find_bill(manager, bill_name)
    if bill is None:
        raise ValueError(f"Bill '{bill_name}' not found")
    due = bill.get_next_due_date(today - timedelta(days=1))
    return save_goal(f"{bill_name} fund", bill.effective_amount, due if due != date.max else None,
                     bank_name, account_name, saved_amount, linked_bill=bill_name)


def roll_sinking_funds(manager, today: date | None = None) -> int:
    """
    When a sinking fund's bill has been paid (its next due date moved past the
    fund's date), use up the fund and aim it at the next due date.
    """
    if manager is None:
        return 0
    today = today or date.today()
    session = _session()
    rolled = 0
    try:
        for g in session.query(db.SavingsGoalModel).filter(db.SavingsGoalModel.linked_bill.isnot(None)).all():
            bill = _find_bill(manager, g.linked_bill)
            if bill is None or not g.target_date:
                continue
            paid_on = [h.get("date") for h in bill.payment_history]
            paid_on = [d if isinstance(d, date) else date.fromisoformat(str(d)[:10]) for d in paid_on if d]
            # Paid within a month before the fund's date (or any time after it)
            # (A missed due date with no payment recorded is left for the user to sort out)
            if not any(d >= g.target_date - timedelta(days=31) for d in paid_on):
                continue
            nxt = bill.get_next_due_date(max(today, g.target_date))
            if nxt == date.max or nxt <= g.target_date:
                continue
            g.saved_amount = round(max(0.0, g.saved_amount - g.target_amount), 2)
            g.target_amount = round(bill.effective_amount, 2)
            g.target_date = nxt
            rolled += 1
        if rolled:
            session.commit()
    finally:
        session.close()
    return rolled
