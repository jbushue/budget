"""
Dashboard summary: "can my bills be paid?" and "how much can I spend?"

Everything comes from ONE run of the payment insights analyzer (which uses
the same simulation as the Optimizer page), so the numbers on the dashboard
always agree with the rest of the app.

Safe to spend
-------------
Spending a dollar today lowers your checking balance on every later day, so
the amount you can safely spend is set by your *lowest* projected checking
balance — not by a total:

    safe to spend = lowest projected checking balance (through your second
                    upcoming payday, paying bills on their due dates and
                    including your everyday spending allowance)
                  − your cushion
                  − overdue bills not yet marked paid
                  − money set aside in checking for goals

The projection already subtracts your usual everyday spending, so this is
what you can spend *on top of* it.
"""

from __future__ import annotations

from datetime import date, timedelta

from .fixed_bill import AccountLinkedBill, GroupLinkedBill
from .payment_insights import PaymentInsightsAnalyzer, checking_keys, _r, _money, _day

# Look at least this far ahead for the bills status
MIN_DAYS = 31


def _pay_dates(manager, start: date, days: int) -> list[date]:
    dates = set()
    for income in manager.income_sources:
        try:
            dates.update(d for d in income.get_pay_dates_in_range(start - timedelta(days=1), start + timedelta(days=days))
                         if d > start and income.amount > 0)
        except Exception:
            pass
    return sorted(dates)


PARKING = {"SAVINGS_SWEEP": 1, "HELOC_PARK": 1, "SAVINGS_RECALL": -1, "HELOC_RECALL": -1}
# Early debt payments the optimizer makes with spare cash. Under "most cash"
# they're optional (spend the money and the plan simply skips them); under
# the debt-first goals they're the point of the plan.
OPTIONAL_PAYDOWN = {"EXTRA_CREDIT_PAYMENT": 1, "PROMO_PAYOFF": 1, "EXTRA_DEBT_PAYMENT": 1}


def _parked_by_day(cash_flow: list[dict], goal: str = "maximize_discretionary") -> dict:
    """{date: money the plan moved out of checking that day but that's still yours to use (negative = brought back)}."""
    kinds = dict(PARKING, **(OPTIONAL_PAYDOWN if goal == "maximize_discretionary" else {}))
    out: dict = {}
    for cf in cash_flow:
        sign = kinds.get(cf.get("type"))
        if sign:
            out[cf["date"]] = out.get(cf["date"], 0.0) + sign * abs(cf["amount"])
    return out


def _big_outflows(cash_flow: list[dict], until: date, after: date, limit: int = 3,
                  goal: str = "maximize_discretionary") -> list[dict]:
    """The largest payments between ``after`` and ``until`` (what the money is being kept for)."""
    skip = {"EVERYDAY_SPENDING", "ACCOUNT_SPENDING", *PARKING}
    if goal == "maximize_discretionary":
        skip |= set(OPTIONAL_PAYDOWN)
    pays = [cf for cf in cash_flow
            if after < cf["date"] <= until and cf.get("amount", 0) < 0
            and cf.get("type") not in skip
            and not cf.get("type", "").endswith("ALREADY_PAID")]
    pays.sort(key=lambda cf: cf["amount"])
    return [{"name": cf["description"].replace(" (insufficient funds)", ""), "date": cf["date"].isoformat(),
             "amount": _r(-cf["amount"])} for cf in pays[:limit]]


def _next_refill(day: int, today: date) -> date:
    from models.date_utils import is_clamped_day
    d = today
    while not is_clamped_day(d, day):
        d += timedelta(days=1)
    return d


def other_money(manager, snapshots: list[dict], today: date) -> list[dict]:
    """
    Money outside checking, grouped: benefits (EBT, HSA, FSA), other cash
    (cash, payment apps, prepaid), savings and investments. Benefits that
    are spent each week say when they run out before the next refill.
    """
    from models.types import account_kind, PURPOSE_LABELS
    out = []
    for bank in manager.banks:
        for acc in bank.get_all_accounts():
            kind = account_kind(acc)
            if acc.account_type.value == "checking":
                continue
            key = f"{bank.name}:{acc.account_name}"
            refill_on = _next_refill(acc.refill_day, today + timedelta(days=1))                 if getattr(acc, "refill_day", None) and acc.refill_amount > 0 else None
            runs_out = None
            if getattr(acc, "weekly_spending", 0) > 0:
                for snap in snapshots:
                    if refill_on and snap["date"] >= refill_on:
                        break
                    if snap["balances"].get(key, 0.0) <= 0.005:
                        runs_out = snap["date"].isoformat()
                        break
            out.append({
                "bank": bank.name, "account": acc.account_name, "type": acc.account_type.value,
                "label": kind["label"], "group": kind["group"], "balance": _r(acc.balance),
                "purpose": PURPOSE_LABELS.get(kind.get("purpose"), ""),
                "refill_amount": _r(getattr(acc, "refill_amount", 0.0)),
                "next_refill": refill_on.isoformat() if refill_on else None,
                "weekly_spending": _r(getattr(acc, "weekly_spending", 0.0)),
                "runs_out": runs_out,
            })
    order = {"benefits": 0, "cash": 1, "savings": 2, "invested": 3, "other": 4}
    return sorted(out, key=lambda a: (order.get(a["group"], 9), -a["balance"]))


def _bill_label(bill) -> str:
    if isinstance(bill, GroupLinkedBill):
        return bill.linked_group.group_name
    return bill.bill_name


def _bill_kind(bill) -> str:
    if isinstance(bill, GroupLinkedBill):
        return "group"
    if isinstance(bill, AccountLinkedBill):
        return bill.linked_account_type
    return "bill"


def _skip_bill(bill, grouped_keys) -> bool:
    """Linked card bills that are covered by a group, or have nothing owed."""
    if isinstance(bill, AccountLinkedBill):
        if (bill.linked_bank_name, bill.linked_account.account_name) in grouped_keys:
            return True
        if bill.linked_account_balance <= 0:
            return True
    return False


def _history(bill) -> list[dict]:
    if isinstance(bill, GroupLinkedBill):
        return bill.linked_group.payment_history or bill.payment_history
    return bill.payment_history


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def overdue_due_date(bill, today: date) -> date | None:
    """
    The bill's most recent due date (within the last 31 days) if it passed
    without a payment, else None. A payment counts for that due date if it
    was made after the previous due date (early or late).
    """
    try:
        prev_due = last_due = None
        d = bill.get_next_due_date(today - timedelta(days=32))
        while d < today:
            prev_due, last_due = last_due, d
            d = bill.get_next_due_date(d)
        if last_due is None:
            return None
        if prev_due is None:
            prev_due = last_due - timedelta(days=31)
            back = bill.get_next_due_date(last_due - timedelta(days=400))
            while back < last_due:
                prev_due = back
                back = bill.get_next_due_date(back)
    except Exception:
        return None
    # Only call it overdue if the bill was being tracked by then: it existed
    # before that due date, or has been paid before. (A bill you just added
    # isn't "overdue" for last month.)
    anchor = getattr(bill, "start_date", None)
    if anchor and last_due < anchor:
        return None
    history = _history(bill)
    created = getattr(bill.linked_group if isinstance(bill, GroupLinkedBill) else bill, "created_on", None)
    if not history:
        if bill.is_paid_this_period or created is None or created > last_due:
            return None
        return last_due
    if any((_as_date(h.get("date")) or date.min) > prev_due for h in history):
        return None
    return last_due


def settle_paid_flag(bill, was_overdue: bool) -> None:
    """
    After paying an OVERDUE bill, the payment was for the missed due date —
    the next one is still owed, so don't flag the upcoming occurrence as paid
    (otherwise the projection would skip it).
    """
    if not was_overdue:
        return
    bill.is_paid_this_period = False
    if isinstance(bill, GroupLinkedBill):
        bill.linked_group.is_paid_this_period = False


def overdue_bills(manager, today: date) -> list[dict]:
    """
    Bills whose most recent due date (within the last 31 days) has passed
    without being paid. The projection starts today, so these are not in
    it — the money for them is still sitting in checking.
    """
    grouped = manager.get_grouped_account_keys()
    out = []
    for bill in manager.bills:
        if _skip_bill(bill, grouped):
            continue
        last_due = overdue_due_date(bill, today)
        if last_due is None:
            continue
        amount = bill.effective_amount if not isinstance(bill, AccountLinkedBill) else min(
            bill.effective_amount, bill.linked_account_balance)
        if amount <= 0:
            continue
        out.append({
            "name": _bill_label(bill),
            "bill_name": bill.bill_name,
            "kind": _bill_kind(bill),
            "due_date": last_due.isoformat(),
            "amount": _r(amount),
            "days_overdue": (today - last_due).days,
            "source_account": bill.preferred_source_account or "",
        })
    return sorted(out, key=lambda r: r["due_date"])


def _goal_reserves(manager) -> float:
    """Money set aside in checking accounts for goals/sinking funds (phase 3)."""
    try:
        from .goals import reserved_in_checking
        return reserved_in_checking(manager)
    except Exception:
        return 0.0


def safe_window(manager, today: date) -> tuple[int, date, list[date]]:
    """(days Safe to spend looks ahead, end of the next pay period pair, upcoming paydays)."""
    paydays = _pay_dates(manager, today, 70)
    next_payday = paydays[0] if paydays else None
    second_payday = paydays[1] if len(paydays) > 1 else None
    horizon = second_payday or (next_payday + timedelta(days=14) if next_payday else today + timedelta(days=28))
    # Look well past the next paycheck: money in checking today may be
    # needed for a bill (or a promo deadline) weeks away
    lookahead = int(getattr(manager, "lookahead_days", 90) or 90)
    return min(365, max(MIN_DAYS, (horizon - today).days + 1, lookahead)), horizon, paydays


def spendable_series(manager, optimized: dict, goal: str) -> list[tuple[date, float]]:
    """
    Checking at the end of each day of the plan, plus money the plan only
    parks (savings sweeps, HELOC parking, and early debt payments under
    "most cash") — that money is still yours to spend.
    """
    keys = checking_keys(manager.banks)
    parked_by_day = _parked_by_day(optimized["cash_flow"], goal)
    series, parked = [], 0.0
    for snap in optimized["snapshots"]:
        parked += parked_by_day.get(snap["date"], 0.0)
        series.append((snap["date"], sum(bal for key, bal in snap["balances"].items() if key in keys) + parked))
    return series


def held_back(manager, late_payments: list[dict], today: date) -> dict:
    """What comes off the lowest point before money counts as safe to spend."""
    overdue = overdue_bills(manager, today)
    return {"overdue": overdue, "overdue_total": sum(o["amount"] for o in overdue),
            # Bills the plan can't pay on time leave their money sitting in
            # checking in the projection — that money is owed, not spendable
            "short_total": sum(p["amount"] for p in late_payments),
            "reserves": _goal_reserves(manager), "cushion": manager.cushion}


def build_dashboard(manager, today: date | None = None) -> dict:
    today = today or date.today()
    days, horizon, paydays = safe_window(manager, today)
    next_payday = paydays[0] if paydays else None

    # The plan the app follows (Settings / Optimizer "Aim for")
    analyzer = PaymentInsightsAnalyzer(manager, start_date=today, days=days)
    insights = analyzer.analyze()
    base = insights["comparison"]["on_due_date"]
    opt = insights["comparison"]["optimized"]

    # ── Safe to spend: lowest checking balance ahead, following the plan ──
    # Spending a dollar today lowers every later day's balance, so the limit
    # is the lowest point over the whole look-ahead, not just until payday.
    # Money the plan only parks (savings sweeps, HELOC parking) still counts
    # as yours, and so do early debt payments under "most cash"; under the
    # debt-first goals those payments are spoken for.
    series = spendable_series(manager, analyzer.optimized, analyzer.goal)
    checking_now = sum(acc.balance for b in manager.banks for acc in b.get_all_accounts()
                       if acc.account_type.value == "checking")
    if not series:
        series = [(today, checking_now)]
    lowest_date, lowest = min(series, key=lambda x: x[1])
    # Of the lowest point, how much is sitting in savings/HELOC/early payments rather than checking
    keys = checking_keys(manager.banks)
    in_checking = next((sum(b for k, b in sn["balances"].items() if k in keys)
                        for sn in analyzer.optimized["snapshots"] if sn["date"] == lowest_date), lowest)
    parked_at_lowest = max(0.0, lowest - in_checking)
    near = [v for d, v in series if d <= horizon] or [lowest]
    near_lowest = min(near)
    # How much of today's money is spoken for by bills after the next paycheck
    held_for_later = max(0.0, near_lowest - lowest)
    later_reasons = (_big_outflows(analyzer.optimized["cash_flow"], lowest_date, horizon, goal=analyzer.goal)
                     if held_for_later > 0.5 else [])

    held = held_back(manager, opt["late_payments"], today)
    overdue, overdue_total, short_total = held["overdue"], held["overdue_total"], held["short_total"]
    reserves, cushion = held["reserves"], held["cushion"]
    safe = max(0.0, lowest - cushion - overdue_total - short_total - reserves)
    days_to_payday = max(1, (next_payday - today).days) if next_payday else 14
    per_day = safe / days_to_payday

    # ── Bills status ──
    timing = insights["bill_timing"]
    status_window_end = today + timedelta(days=days)
    late_base = base["late_payments"]
    late_opt = opt["late_payments"]
    if late_opt:
        first = late_opt[0]
        status, title = "danger", f"{first['name']} can't be paid on {_day(date.fromisoformat(first['date']))}"
        detail = (f"{len(late_opt)} payment(s) in the next {days} days are short. "
                  "Open the plan for ways to cover them.")
    elif overdue:
        status = "warning"
        title = f"{len(overdue)} bill(s) past due and not marked paid"
        detail = ("If you've already paid them, mark them paid below. "
                  f"Until then, {_money(overdue_total)} is held back from safe-to-spend.")
    elif late_base:
        status = "warning"
        title = "Bills are covered — if you follow the plan"
        detail = (f"Paying everything on its due date leaves {late_base[0]['name']} short. "
                  "The optimized plan moves money so every bill is paid on time.")
    elif lowest < 0:
        status = "danger"
        title = f"Checking goes negative around {_day(lowest_date)}"
        detail = ("Bills and everyday spending would overdraw checking"
                  + (" before the next paycheck." if lowest_date <= horizon else
                     f" — money coming in before then is needed for bills due by {_day(lowest_date)}."))
    elif lowest < cushion:
        status = "warning"
        title = f"All bills covered, but checking gets tight around {_day(lowest_date)}"
        detail = f"It drops to {_money(lowest)}, below your {_money(cushion)} cushion."
    else:
        status = "ok"
        title = f"All bills through {_day(status_window_end)} are covered"
        detail = f"Your lowest point is {_money(lowest)} on {_day(lowest_date)}."

    # ── This pay period's checklist ──
    period_end = next_payday or today + timedelta(days=14)
    checklist = [dict(o, status="overdue", short_by=0.0) for o in overdue]
    for row in timing:
        due = date.fromisoformat(row["due_date"])
        if due >= period_end and not (row["status"] == "late" and due < horizon):
            continue
        if row["status"] == "already_paid":
            st = "paid"
        elif row["status"] == "late":
            st = "covered_by_plan" if row["plan_status"] == "paid" else "short"
        else:
            st = "covered"
        checklist.append({
            "name": row["name"],
            "bill_name": row.get("bill_name") or row["name"],
            "kind": row["kind"],
            "due_date": row["due_date"],
            "amount": row["amount"],
            "status": st,
            "short_by": row["shortfall"],
            "days_overdue": 0,
            "source_account": row["source_account"],
        })

    income = []
    for d in paydays[:3]:
        for inc in manager.income_sources:
            if d in inc.get_pay_dates_in_range(d - timedelta(days=1), d):
                income.append({"date": d.isoformat(), "name": inc.source_name, "amount": _r(inc.amount)})

    spend = manager.everyday_spending
    return {
        "other_money": other_money(manager, analyzer.baseline["snapshots"], today),
        "status": status,
        "status_title": title,
        "status_detail": detail,
        "safe_to_spend": _r(safe),
        "safe_per_day": _r(per_day),
        "lowest_balance": _r(lowest),
        "lowest_date": lowest_date.isoformat() if lowest_date else None,
        "near_lowest": _r(near_lowest),
        "parked_at_lowest": _r(parked_at_lowest),
        "held_for_later": _r(held_for_later),
        "held_for": later_reasons,
        "lookahead_days": days,
        "plan_goal": analyzer.goal,
        "plan_target": analyzer.target_account,
        "checking_now": _r(checking_now),
        "cushion": _r(cushion),
        "overdue_total": _r(overdue_total),
        "short_total": _r(short_total),
        "goal_reserves": _r(reserves),
        "everyday_weekly": spend["weekly"] if spend else 0.0,
        "spending_mode": spend["mode"] if spend else "manual",
        "next_payday": next_payday.isoformat() if next_payday else None,
        "horizon": horizon.isoformat(),
        "covered_through": status_window_end.isoformat(),
        "bills_this_period": checklist,
        "upcoming_income": income,
        "insights": insights["insights"][:3],
        "promos": insights["promos"],
        "headline": insights["headline"],
        # Checking each day (with parked money) for the dashboard chart: the same numbers as above
        "plan_series": [{"date": d.isoformat(), "amount": _r(v)} for d, v in series],
    }
