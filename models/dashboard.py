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


def overdue_bills(manager, today: date) -> list[dict]:
    """
    Bills whose most recent due date (within the last 31 days) has passed
    without being marked paid. The projection starts today, so these are
    not in it — the money for them is still sitting in checking.
    """
    grouped = manager.get_grouped_account_keys()
    out = []
    for bill in manager.bills:
        if bill.is_paid_this_period or _skip_bill(bill, grouped):
            continue
        try:
            last_due = None
            d = bill.get_next_due_date(today - timedelta(days=32))
            while d < today:
                last_due = d
                d = bill.get_next_due_date(d)
        except Exception:
            continue
        if last_due is None:
            continue
        # Only call it overdue if the bill was being tracked by then: it existed
        # before that due date, or has been paid before. (A bill you just added
        # isn't "overdue" for last month.)
        anchor = getattr(bill, "start_date", None)
        if anchor and last_due < anchor:
            continue
        if isinstance(bill, GroupLinkedBill):
            created = getattr(bill.linked_group, "created_on", None)
            history = bill.linked_group.payment_history or bill.payment_history
        else:
            created = getattr(bill, "created_on", None)
            history = bill.payment_history
        if not history and (created is None or created > last_due):
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


def build_dashboard(manager, today: date | None = None) -> dict:
    today = today or date.today()
    paydays = _pay_dates(manager, today, 70)
    next_payday = paydays[0] if paydays else None
    second_payday = paydays[1] if len(paydays) > 1 else None
    horizon = second_payday or (next_payday + timedelta(days=14) if next_payday else today + timedelta(days=28))
    days = max(MIN_DAYS, (horizon - today).days + 1)

    analyzer = PaymentInsightsAnalyzer(manager, start_date=today, days=days)
    insights = analyzer.analyze()
    base = insights["comparison"]["on_due_date"]
    opt = insights["comparison"]["optimized"]

    # ── Safe to spend: lowest checking balance through the horizon ──
    keys = checking_keys(manager.banks)
    lowest, lowest_date = None, None
    for snap in analyzer.baseline["snapshots"]:
        if snap["date"] > horizon:
            break
        total = sum(bal for key, bal in snap["balances"].items() if key in keys)
        if lowest is None or total < lowest:
            lowest, lowest_date = total, snap["date"]
    checking_now = sum(acc.balance for b in manager.banks for acc in b.get_all_accounts()
                       if acc.account_type.value == "checking")
    if lowest is None:
        lowest, lowest_date = checking_now, today

    overdue = overdue_bills(manager, today)
    overdue_total = sum(o["amount"] for o in overdue)
    # Bills that can't be paid on their due date leave their money sitting in
    # checking in the projection — that money is owed, not spendable.
    short_total = sum(p["amount"] for p in base["late_payments"]
                      if date.fromisoformat(p["date"]) <= horizon)
    reserves = _goal_reserves(manager)
    cushion = manager.cushion
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
        detail = "Your everyday spending would overdraw checking before the next paycheck."
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
        "status": status,
        "status_title": title,
        "status_detail": detail,
        "safe_to_spend": _r(safe),
        "safe_per_day": _r(per_day),
        "lowest_balance": _r(lowest),
        "lowest_date": lowest_date.isoformat() if lowest_date else None,
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
        "headline": insights["headline"],
    }
