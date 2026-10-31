"""
Planning and review reports built from the accounts, bills, income and the
transaction ledger:

* ``monthly_plan``     – expected monthly income vs. bills, budgets and goal
                         saving: what's left to budget.
* ``health_check``     – a financial health score from savings rate,
                         emergency fund, debt-to-income, card utilization,
                         high-interest debt, budgets and net worth trend,
                         each with a plain-language tip.
* ``subscriptions``    – every recurring charge (from transactions and
                         bills) with its monthly and yearly cost, flagging
                         price increases.
* ``year_review``      – a year's income, spending, savings rate, top
                         categories and payees, and month-by-month totals.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from models import ledger
from models.fixed_bill import AccountLinkedBill, GroupLinkedBill

INCOME_PER_MONTH = {"once": 0.0, "weekly": 52 / 12, "biweekly": 26 / 12, "semimonthly": 2.0, "monthly": 1.0,
                    "bimonthly": 0.5, "quarterly": 1 / 3, "yearly": 1 / 12}
BILL_PER_MONTH = {"once": 0.0, "weekly": 52 / 12, "biweekly": 26 / 12, "monthly": 1.0, "quarterly": 1 / 3,
                  "semi_annual": 1 / 6, "yearly": 1 / 12}
RECURRENCE = [("weekly", 7, 2), ("biweekly", 14, 3), ("monthly", 30.4, 5), ("quarterly", 91, 10),
              ("yearly", 365, 20)]


def _r(v: float) -> float:
    return round(v + 0.0, 2)


def _freq(obj) -> str:
    f = getattr(obj, "frequency", None)
    return getattr(f, "value", f) or "monthly"


def monthly_income(manager) -> float:
    return sum(i.amount * INCOME_PER_MONTH.get(_freq(i), 1.0) for i in manager.income_sources)


def _grouped_keys(manager) -> set:
    return manager.get_grouped_account_keys() if hasattr(manager, "get_grouped_account_keys") else set()


def monthly_bills(manager) -> dict:
    """Monthly equivalent of every bill, split into debt payments and other bills."""
    debt = other = 0.0
    grouped = _grouped_keys(manager)
    for b in manager.bills:
        if isinstance(b, AccountLinkedBill) and b.linked_account_type == "credit" and \
                (b.linked_bank_name, b.linked_account.account_name) in grouped:
            continue  # paid through its loan group
        amount = b.effective_amount * BILL_PER_MONTH.get(_freq(b), 1.0)
        if isinstance(b, (AccountLinkedBill, GroupLinkedBill)):
            debt += amount
        else:
            other += amount
    return {"debt": debt, "other": other, "total": debt + other}


def monthly_plan(manager) -> dict:
    """Expected income for a typical month and where it's planned to go."""
    from models import goals
    income = monthly_income(manager)
    bills = monthly_bills(manager)
    budgets = sum(c["monthly_budget"] or 0 for c in ledger.list_categories() if c["kind"] == "expense")
    saving = sum(g["monthly_needed"] or 0 for g in goals.list_goals(manager) if not g["complete"])
    left = income - bills["total"] - budgets - saving
    return {
        "income": _r(income), "bills": _r(bills["total"]), "debt_payments": _r(bills["debt"]),
        "budgets": _r(budgets), "goal_saving": _r(saving), "left_to_budget": _r(left),
        "status": "over" if left < -0.5 else "unassigned" if left > 0.5 else "balanced",
    }


# ─────────────────────────────────────────────────────────────────────────
#  Financial health check
# ─────────────────────────────────────────────────────────────────────────

def _scale(value: float, worst: float, best: float) -> int:
    """0 at ``worst``, 100 at ``best`` (either direction), clamped."""
    if best == worst:
        return 100
    return int(round(max(0.0, min(1.0, (value - worst) / (best - worst))) * 100))


def _full_months(today: date, n: int) -> tuple[date, date, list[str]]:
    first_this = date(today.year, today.month, 1)
    keys = ledger._month_keys_before(first_this, n)
    return date.fromisoformat(keys[0] + "-01"), first_this, keys


def _ledger_totals(start: date, end: date) -> tuple[float, float, set]:
    """Income, spending (transfers excluded) and the months with data in [start, end)."""
    cats = {c["name"]: c for c in ledger.list_categories()}
    income = spending = 0.0
    months = set()
    for t, cat, amount in ledger.category_lines(
            [t for t in ledger.all_transactions(start) if t["date"] < end.isoformat()]):
        months.add(t["date"][:7])
        c = cats.get(cat) if cat else None
        kind = c["kind"] if c else ("income" if amount > 0 else "expense")
        if kind == "income":
            income += amount
        elif kind == "expense":
            spending -= amount
    return income, spending, months


def _net_worth_change(days: int = 90) -> tuple[float, float] | None:
    """(net worth then, now) from the recorded history, if it reaches back far enough."""
    from sqlalchemy import text
    from models import database as db
    session = db.get_session()
    try:
        tables = set(session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
        if "net_worth_snapshots" not in tables:
            return None
        rows = session.execute(text("SELECT snapshot_date, net_worth FROM net_worth_snapshots "
                                    "ORDER BY snapshot_date")).fetchall()
    finally:
        session.close()
    if len(rows) < 2:
        return None
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    older = [r for r in rows if r[0] <= cutoff] or rows[:1]
    if (date.fromisoformat(rows[-1][0][:10]) - date.fromisoformat(older[-1][0][:10])).days < 28:
        return None
    return older[-1][1], rows[-1][1]


def health_check(manager, today: date | None = None) -> dict:
    """A 0-100 score with one line per factor (score, value, status, tip)."""
    today = today or date.today()
    factors = []

    def add(key, label, score, value, detail, tip, weight):
        status = "good" if score >= 75 else "fair" if score >= 45 else "poor"
        factors.append({"key": key, "label": label, "score": score, "value": value, "detail": detail,
                        "tip": tip if status != "good" else "", "status": status, "weight": weight})

    income_m = monthly_income(manager)
    bills = monthly_bills(manager)
    everyday_m = ((manager.everyday_spending or {}).get("amount", 0.0) * 30.4) if manager.everyday_spending else 0.0

    # 1. Savings rate: from the last 3 full months of transactions, else from the plan
    start, end, _ = _full_months(today, 3)
    inc, spent, months = _ledger_totals(start, end)
    if len(months) >= 2 and inc > 0:
        rate, source = (inc - spent) / inc * 100, f"last {len(months)} months of transactions"
    elif income_m > 0:
        rate, source = (income_m - bills["total"] - everyday_m) / income_m * 100, "your planned income and bills"
    else:
        rate = None
    if rate is not None:
        add("savings_rate", "Savings rate", _scale(rate, 0, 20), f"{rate:.0f}%",
            f"Share of income left after spending ({source}). 20% or more is a strong target.",
            "Trim a budget category or automate a transfer to savings on payday — even 5% more adds up.", 2)

    # 2. Emergency fund: liquid cash vs. a month of essentials
    liquid = sum(a.balance for b in manager.banks for a in b.accounts.values())
    essentials = bills["total"] + everyday_m
    if essentials > 0:
        months_cov = liquid / essentials
        add("emergency_fund", "Emergency fund", _scale(months_cov, 0, 6), f"{months_cov:.1f} months",
            f"Checking + savings (${liquid:,.0f}) covers {months_cov:.1f} months of bills and everyday spending.",
            "Aim for 3–6 months. A savings goal for it (Goals page) sets a per-paycheck amount.", 2)

    # 3. Debt-to-income
    if income_m > 0:
        dti = bills["debt"] / income_m * 100
        add("debt_to_income", "Debt-to-income", _scale(dti, 50, 15), f"{dti:.0f}%",
            f"Debt payments (${bills['debt']:,.0f}/mo) as a share of income (${income_m:,.0f}/mo). Under 15% is great; "
            "lenders start worrying above 36%.",
            "The Debt Payoff page shows how extra payments (avalanche or snowball) shrink this fastest.", 2)

    # 4. Card utilization (loan-group members such as student loans aren't cards)
    grouped = _grouped_keys(manager)
    cards = [(b.name, c) for b in manager.banks for n, c in b.credit_accounts.items()
             if (b.name, n) not in grouped and c.credit_limit > 0]
    limit = sum(c.credit_limit for _, c in cards)
    if limit > 0:
        util = sum(c.balance for _, c in cards) / limit * 100
        add("utilization", "Credit card utilization", _scale(util, 75, 10), f"{util:.0f}%",
            "Card balances as a share of their limits. Under 30% helps your credit score; under 10% is best.",
            "Pay cards down before the statement date — the optimizer suggests when spare cash allows.", 1)

    # 5. High-interest debt
    costly = sum(c.balance for _, c in cards if c.interest_rate >= 15 and c.balance > 0)
    if cards:
        ratio = costly / income_m if income_m > 0 else (1.0 if costly else 0.0)
        add("high_interest", "High-interest debt", _scale(ratio, 1, 0), f"${costly:,.0f}",
            "Card balances at 15% APR or more.",
            "Pay the highest-APR card first, or look at a 0% balance transfer (track it as a promo).", 1)

    # 6. Budgets kept last month
    last_month = ledger._month_keys_before(date(today.year, today.month, 1), 1)[0]
    status = ledger.budget_status(last_month, today)
    budgeted = [line for line in status["lines"] if line["budget"]]
    if budgeted:
        kept = sum(1 for line in budgeted if line["status"] != "over")
        add("budgets", "Budgets kept", _scale(kept / len(budgeted), 0.5, 1.0), f"{kept} of {len(budgeted)}",
            f"Budget categories that stayed within budget in {date.fromisoformat(last_month + '-01'):%B %Y}.",
            "Look at the categories that went over — raise the budget if it was unrealistic, or set a rule to watch it.", 1)

    # 7. Net worth trend
    change = _net_worth_change()
    if change:
        then, now = change
        pct = (now - then) / abs(then) * 100 if then else (100.0 if now > then else 0.0)
        add("net_worth", "Net worth trend", 100 if now > then + 1 else 60 if abs(now - then) <= 1 else 20,
            f"{'+' if now >= then else '−'}${abs(now - then):,.0f}",
            f"Change over about 3 months ({pct:+.1f}%).",
            "Net worth is falling — check Reports for where spending grew.", 1)

    total_weight = sum(f["weight"] for f in factors)
    score = round(sum(f["score"] * f["weight"] for f in factors) / total_weight) if total_weight else None
    grade = (None if score is None else "A" if score >= 85 else "B" if score >= 70 else
             "C" if score >= 55 else "D" if score >= 40 else "F")
    worst = sorted((f for f in factors if f["tip"]), key=lambda f: (f["score"], -f["weight"]))
    return {"score": score, "grade": grade, "factors": factors,
            "top_tips": [f"{f['label']}: {f['tip']}" for f in worst[:3]]}


# ─────────────────────────────────────────────────────────────────────────
#  Subscriptions & recurring charges
# ─────────────────────────────────────────────────────────────────────────

def subscriptions(manager, today: date | None = None, days: int = 400) -> dict:
    """
    Recurring charges found in transactions (grouped by the bill they paid,
    or by payee), plus regular bills with no transactions yet. Each has its
    monthly and yearly cost; a latest charge more than 5% above the usual
    amount is flagged as a price increase.
    """
    today = today or date.today()
    cats = {c["name"]: c for c in ledger.list_categories()}
    groups: dict = {}
    for t in ledger.all_transactions(today - timedelta(days=days)):
        if t["amount"] >= 0:
            continue
        c = cats.get(t["category"]) if t["category"] else None
        if c and c["kind"] != "expense":
            continue
        key = ("bill", t["matched_bill"]) if t["matched_bill"] else ("payee", ledger.normalize_payee(t["description"]))
        if key[1] and len(key[1]) >= 3:
            groups.setdefault(key, []).append(t)

    items = []
    seen_bills = set()
    for (source, key), txns in groups.items():
        dates = sorted({date.fromisoformat(t["date"]) for t in txns})
        if len(dates) < 2 or (source == "payee" and len(dates) < 3):
            continue
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        pattern = next((p for p in RECURRENCE
                        if sum(abs(g - p[1]) <= p[2] for g in gaps) >= 0.75 * len(gaps)), None)
        if pattern is None or (today - dates[-1]).days > pattern[1] * 2 + pattern[2]:
            continue
        txns = sorted(txns, key=lambda t: t["date"])
        amounts = [-t["amount"] for t in txns]
        usual = median(amounts[:-1]) if len(amounts) > 1 else amounts[-1]
        latest = amounts[-1]
        # A payee is only a subscription if it charges about the same each time
        if source == "payee" and (any(abs(a - usual) > usual * 0.15 for a in amounts[:-1])
                                  or latest > usual * 1.5 or latest < usual * 0.5):
            continue
        monthly = median(amounts) * 30.4 / pattern[1]
        if source == "bill":
            seen_bills.add(key)
        items.append({
            "name": key if source == "bill" else key.title(), "source": source,
            "frequency": pattern[0], "amount": _r(latest), "usual_amount": _r(usual),
            "monthly_cost": _r(monthly), "yearly_cost": _r(monthly * 12),
            "last_date": dates[-1].isoformat(),
            "next_expected": (dates[-1] + timedelta(days=round(pattern[1]))).isoformat(),
            "category": txns[-1]["category"], "count": len(txns),
            "price_increase": _r(latest - usual) if usual and latest > usual * 1.05 else 0.0,
        })

    for b in manager.bills:
        if isinstance(b, (AccountLinkedBill, GroupLinkedBill)) or b.bill_name in seen_bills:
            continue
        per_month = BILL_PER_MONTH.get(_freq(b), 1.0)
        if not per_month:
            continue
        monthly = b.effective_amount * per_month
        items.append({
            "name": b.bill_name, "source": "scheduled", "frequency": _freq(b), "amount": _r(b.effective_amount),
            "usual_amount": _r(b.effective_amount), "monthly_cost": _r(monthly), "yearly_cost": _r(monthly * 12),
            "last_date": None, "next_expected": None, "category": None, "count": 0, "price_increase": 0.0,
        })
    items.sort(key=lambda i: -i["monthly_cost"])
    return {"items": items,
            "monthly_total": _r(sum(i["monthly_cost"] for i in items)),
            "yearly_total": _r(sum(i["yearly_cost"] for i in items)),
            "price_increases": [i["name"] for i in items if i["price_increase"]]}


# ─────────────────────────────────────────────────────────────────────────
#  Year in review
# ─────────────────────────────────────────────────────────────────────────

def year_review(year: int | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    year = year or today.year
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    cats = {c["name"]: c for c in ledger.list_categories()}
    txns = [t for t in ledger.all_transactions(start) if t["date"] < end.isoformat()]
    months = {f"{year}-{m:02d}": {"month": f"{year}-{m:02d}", "income": 0.0, "spending": 0.0} for m in range(1, 13)}
    by_cat: dict = {}
    payees: dict = {}
    biggest = []
    tags: dict = {}
    for t, cat, amount in ledger.category_lines(txns):
        c = cats.get(cat) if cat else None
        kind = c["kind"] if c else ("income" if amount > 0 else "expense")
        if kind == "transfer":
            continue
        m = months[t["date"][:7]]
        if kind == "income":
            m["income"] += amount
            continue
        m["spending"] -= amount
        name = cat or "Uncategorized"
        by_cat[name] = by_cat.get(name, 0.0) - amount
        payee = ledger.normalize_payee(t["description"]).title() or t["description"][:30]
        payees[payee] = payees.get(payee, 0.0) - amount
        for tag in t["tags"]:
            tags[tag] = tags.get(tag, 0.0) - amount
    for t in txns:
        if t["amount"] < 0:
            biggest.append(t)
    biggest = sorted(biggest, key=lambda t: t["amount"])[:5]
    income = sum(m["income"] for m in months.values())
    spending = sum(m["spending"] for m in months.values())
    active = [m for m in months.values() if m["income"] or m["spending"]]
    top = max(active, key=lambda m: m["spending"]) if active else None
    return {
        "year": year,
        "has_data": bool(txns),
        "income": _r(income), "spending": _r(spending), "saved": _r(income - spending),
        "savings_rate": round((income - spending) / income * 100, 1) if income > 0 else None,
        "months": [{**m, "income": _r(m["income"]), "spending": _r(m["spending"]),
                    "net": _r(m["income"] - m["spending"])} for m in months.values()],
        "average_monthly_spending": _r(spending / len(active)) if active else 0.0,
        "biggest_month": top["month"] if top else None,
        "top_categories": [{"name": k, "amount": _r(v), "color": (cats.get(k) or {}).get("color") or "#cbd5e1",
                            "share": round(v / spending * 100, 1) if spending else 0.0}
                           for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])[:8] if v > 0],
        "top_payees": [{"name": k, "amount": _r(v)} for k, v in sorted(payees.items(), key=lambda kv: -kv[1])[:10] if v > 0],
        "largest_purchases": [{"date": t["date"], "description": t["description"], "amount": _r(-t["amount"]),
                               "category": t["category"] or ("Split" if t["splits"] else None)} for t in biggest],
        "by_tag": [{"tag": k, "amount": _r(v)} for k, v in sorted(tags.items(), key=lambda kv: -kv[1]) if v > 0],
        "transaction_count": len(txns),
    }
