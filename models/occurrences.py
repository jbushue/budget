"""
Paid status per due date.

Every payment records the due date it pays (``due``) and what that due date
owed when it was first paid (``owed``), so each due date of a bill is
concretely paid, partly paid, skipped or still owed. The simulator, dashboard,
alerts, bill matching and the Bills month view all read the status from here.

Works for every kind of bill: plain, floating, account-linked (card, mortgage,
HELOC) and group-linked (whose payments live on the group).
"""

from __future__ import annotations

from datetime import date, timedelta

from .types import BillFrequency

# Statuses that mean nothing more is owed for that due date
SETTLED = ("paid", "skipped", "none")
# Furthest a payment can be recorded ahead (matches the longest plan)
AHEAD_DAYS = 365
# Frequencies whose due dates are identified by the exact date, not the month
_EXACT = frozenset((BillFrequency.WEEKLY, BillFrequency.BIWEEKLY, BillFrequency.ONCE))


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def paid_on(entry: dict) -> date | None:
    return _as_date(entry.get("date"))


def due_of(entry: dict) -> date | None:
    return _as_date(entry.get("due"))


def _amount(entry: dict) -> float:
    value = entry.get("amount_paid", entry.get("amount"))
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def history(bill) -> list[dict]:
    return getattr(bill, "payment_history", None) or []


def skipped(bill) -> set:
    return getattr(bill, "skipped", None) or set()


def period(bill, day: date):
    """
    What identifies a due date: the month for monthly-or-longer bills (so
    moving the due day keeps the month paid), the exact date for weekly,
    biweekly and one-time bills.
    """
    if getattr(bill, "frequency", None) in _EXACT:
        return day
    return (day.year, day.month)


def is_skipped(bill, due: date) -> bool:
    days = skipped(bill)
    if not days:
        return False
    key = period(bill, due)
    return any(period(bill, d) == key for d in days)


def actual_for(bill, due: date) -> float | None:
    """A floating bill's actual amount for the due date, if entered."""
    key = period(bill, due)
    for d, amount in (getattr(bill, "actual_amounts", None) or {}).items():
        if period(bill, d) == key:
            return float(amount)
    return None


def floor(bill) -> date:
    """The first due date that can count as overdue: nothing is owed from
    before the bill existed, started, or was tracked by due date."""
    days = [d for d in (getattr(bill, "created_on", None), getattr(bill, "start_date", None),
                        getattr(bill, "tracked_from", None)) if isinstance(d, date)]
    return max(days) if days else date.today()


def due_dates(bill, start: date, end: date) -> list[date]:
    """Every due date of ``bill`` from ``start`` through ``end``."""
    out = []
    d = start - timedelta(days=1)
    for _ in range(2000):
        try:
            nd = bill.get_next_due_date(d)
        except Exception:
            break
        if nd is None or nd > end or nd == date.max:
            break
        out.append(nd)
        d = nd
    return out


def previous_due(bill, before: date, within_days: int = 400) -> date | None:
    """The latest due date strictly before ``before``."""
    dates = due_dates(bill, before - timedelta(days=within_days), before - timedelta(days=1))
    return dates[-1] if dates else None


def next_due(bill, on_or_after: date) -> date | None:
    try:
        nd = bill.get_next_due_date(on_or_after - timedelta(days=1))
    except Exception:
        return None
    return None if nd == date.max else nd


# Payment history grouped by period, per history list. A plan asks about the
# same few histories hundreds of thousands of times, so the grouping is kept:
# new payments appended to the list are added to it, anything else (removed
# or replaced entries) rebuilds it. The cache holds the list itself, so its
# id can't be reused while cached.
_by_period_cache: dict[int, tuple] = {}


def _add_entries(index: dict, entries, exact: bool) -> None:
    for e in entries:
        d = due_of(e)
        if d:
            index.setdefault(d if exact else (d.year, d.month), []).append(e)


def _by_period(bill) -> dict:
    hist = history(bill)
    if not hist:
        return {}
    exact = getattr(bill, "frequency", None) in _EXACT
    size = len(hist)
    hit = _by_period_cache.get(id(hist))
    if hit is not None and hit[0] is hist and hit[2] == exact:
        seen, index = hit[1], hit[4]
        if seen == size and hit[3] is hist[-1]:
            return index
        if seen < size and hist[seen - 1] is hit[3]:  # only appended to
            _add_entries(index, hist[seen:], exact)
            _by_period_cache[id(hist)] = (hist, size, exact, hist[-1], index)
            return index
    index: dict = {}
    _add_entries(index, hist, exact)
    if len(_by_period_cache) > 512:
        _by_period_cache.clear()
    _by_period_cache[id(hist)] = (hist, size, exact, hist[-1], index)
    return index


def payments_for(bill, due: date) -> list[dict]:
    return list(_by_period(bill).get(period(bill, due), ()))


def paid_amount(bill, due: date) -> float:
    return round(sum(_amount(e) for e in payments_for(bill, due)), 2)


def scheduled_amount(bill, due: date) -> float:
    """What the due date owes before anything is paid (a floating bill's
    actual amount for that due date, else its usual amount)."""
    actual = actual_for(bill, due)
    if actual is not None:
        return actual
    try:
        return float(bill.amount_on(due))
    except Exception:
        return float(getattr(bill, "amount", 0.0) or 0.0)


def amount_due(bill, due: date) -> float:
    """What the due date owes: fixed when it was first paid, so later balance
    changes (a card's minimum dropping after the payment) don't reopen it."""
    for e in payments_for(bill, due):
        if e.get("owed") is not None:
            return float(e["owed"])
    return scheduled_amount(bill, due)


def remaining(bill, due: date) -> float:
    if is_skipped(bill, due):
        return 0.0
    entries = payments_for(bill, due)
    if entries and any(e.get("owed") is None for e in entries):
        return 0.0  # recorded before amounts were kept: counts as paid in full
    return max(0.0, round(amount_due(bill, due) - paid_amount(bill, due), 2))


def status(bill, due: date, today: date | None = None) -> str:
    """paid | partial | skipped | none (nothing owed) | overdue | unpaid | untracked."""
    today = today or date.today()
    if is_skipped(bill, due):
        return "skipped"
    if payments_for(bill, due):
        return "paid" if remaining(bill, due) <= 0.005 else "partial"
    if scheduled_amount(bill, due) <= 0.005:
        return "none"
    if due < today:
        return "overdue" if due >= floor(bill) else "untracked"
    return "unpaid"


def is_settled(bill, due: date) -> bool:
    return status(bill, due) in SETTLED


def overdue(bill, today: date | None = None) -> list[tuple[date, float]]:
    """(due date, amount still owed) for every due date before ``today`` that
    isn't fully paid, oldest first."""
    today = today or date.today()
    start = floor(bill)
    if start >= today:
        return []
    out = []
    for due in due_dates(bill, start, today - timedelta(days=1)):
        st = status(bill, due, today)
        if st in ("overdue", "partial"):
            left = remaining(bill, due)
            if left > 0.005:
                out.append((due, left))
    return out


def default_due(bill, today: date | None = None) -> date | None:
    """The due date a payment goes to when none is given: the oldest one still
    owed, else the next one not yet paid."""
    today = today or date.today()
    late = overdue(bill, today)
    if late:
        return late[0][0]
    for due in due_dates(bill, today, today + timedelta(days=AHEAD_DAYS)):
        if not is_settled(bill, due):
            return due
    return next_due(bill, today)


def latest_paid_due(bill) -> date | None:
    """The latest due date with a payment recorded (what "undo" undoes by default)."""
    dues = [d for d in (due_of(e) for e in history(bill)) if d]
    return max(dues) if dues else None


def is_paid_now(bill, today: date | None = None) -> bool:
    """Nothing overdue and the next due date is already taken care of."""
    today = today or date.today()
    if overdue(bill, today):
        return False
    nd = next_due(bill, today)
    return nd is not None and status(bill, nd, today) in ("paid", "skipped")


def new_entry(bill, due: date, amount_paid: float | None, payment_date: date | None,
              source_bank: str | None, source_account: str | None, moved_money: bool = True) -> dict:
    """A payment for ``due``; defaults to whatever is left on it."""
    owed = amount_due(bill, due)
    if amount_paid is None:
        amount_paid = remaining(bill, due) if payments_for(bill, due) else owed
    return {
        "date": payment_date or date.today(),
        "source_bank": source_bank,
        "source_account": source_account,
        "amount_paid": amount_paid,
        "due": due,
        "owed": round(owed, 2),
        "moved_money": bool(moved_money),
    }


def assign_legacy(bill) -> bool:
    """
    Payments recorded before due dates were kept get one now: a payment pays
    the latest due date in the month before it if that one hadn't been paid
    (a late payment), else the first due date on or after it. Returns True if
    anything changed.
    """
    entries = history(bill)
    if all(due_of(e) for e in entries):
        return False
    taken = {due_of(e) for e in entries if due_of(e)}
    created = getattr(bill, "created_on", None)
    for e in sorted((e for e in entries if not due_of(e)), key=lambda e: paid_on(e) or date.min):
        day = paid_on(e) or date.today()
        late = previous_due(bill, day, within_days=31)
        if late and late not in taken and (created is None or created <= late):
            e["due"] = late
        else:
            e["due"] = next_due(bill, day) or day
        taken.add(e["due"])
    _by_period_cache.pop(id(entries), None)
    return True


def pin_anchor(bill) -> bool:
    """
    Fix the cycle of a bill whose due dates would otherwise depend on the
    first date the app happened to ask about (weekly/biweekly/one-time bills
    without a start date, quarterly/yearly ones without a due month), so its
    due dates are the same every time. Returns True if it changed.
    """
    from .date_utils import add_months, clamped_date
    if getattr(bill, "start_date", None) is not None or getattr(bill, "linked_group", None) is not None:
        return False
    freq = getattr(bill, "frequency", None)
    created = getattr(bill, "created_on", None) or date.today()
    if freq in (BillFrequency.WEEKLY, BillFrequency.BIWEEKLY, BillFrequency.ONCE):
        first = clamped_date(created.year, created.month, bill.due_date)
        if first < created:
            y, m = add_months(created.year, created.month, 1)
            first = clamped_date(y, m, bill.due_date)
        bill.start_date = first
        bill.__dict__.pop("_implicit_anchor", None)
        return True
    if freq in (BillFrequency.QUARTERLY, BillFrequency.SEMI_ANNUAL, BillFrequency.YEARLY) \
            and getattr(bill, "due_month", None) is None:
        phase = getattr(bill, "_implicit_phase_month", None)
        bill.due_month = phase[1] if phase else created.month
        bill.__dict__.pop("_implicit_phase_month", None)
        return True
    return False
