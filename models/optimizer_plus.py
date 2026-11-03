"""
Deeper optimizer tools, each answered by running the same day-by-day
simulation as the rest of the app (so the answers respect every bill,
paycheck, refill, everyday spending, fees and your cushion):

* ``debt_boost``       – the most you can safely put toward debt each month
                         (searched, not guessed: every amount is simulated and
                         must never leave you riskier than paying minimums),
                         where it goes (avalanche or snowball), and what it saves.
* ``due_date_moves``   – bills whose due date is badly placed against your
                         paydays, and the day to ask the company to move it to.
* ``purchase_planner`` – the earliest day a purchase fits, and how much you
                         could spend on each day ahead without dipping below
                         your cushion.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta

from models.fixed_bill import AccountLinkedBill, Bill, FloatingBill, GroupLinkedBill
from models.payment_optimizer import score_simulation
from models.timeline_simulator import TimelineEvent, TimelineSimulator
from models.types import BillFrequency

DEFERRED_SUFFIXES = ("_DEFERRED",)
STRATEGIES = {"avalanche": "Highest interest first", "snowball": "Smallest balance first"}


def _r(v: float) -> float:
    return round(v + 0.0, 2)


class _Runner:
    """Runs simulations of the manager's current state from ``start`` to ``end``."""

    def __init__(self, manager, days: int, start: date | None = None):
        self.manager = manager
        self.start = start or date.today()
        self.end = self.start + timedelta(days=days)
        self.days = days
        self.checking = {f"{b.name}:{n}" for b in manager.banks for n, a in b.accounts.items()
                         if a.account_type.value == "checking"}
        self.cushion = getattr(manager, "cushion", 0.0) or 0.0

    def run(self, injected: dict | None = None, tweak=None) -> dict:
        state = deepcopy((self.manager.banks, self.manager.income_sources, self.manager.bills,
                          self.manager.bill_groups))
        if tweak:
            tweak(*state)
        banks, income, bills, groups = state
        sim = TimelineSimulator(banks, income, bills, groups, **self.manager.sim_options())
        result = sim.project_balances(self.start, self.end, injected_events=injected or {})
        result["_banks"] = banks
        return result

    def checking_series(self, result: dict) -> list[tuple[date, float]]:
        return [(s["date"], sum(v for k, v in s["balances"].items() if k in self.checking))
                for s in result["snapshots"]]

    def evaluate(self, result: dict, skip_days: int = 0) -> dict:
        series = self.checking_series(result)
        if skip_days and len(series) > skip_days:
            series = series[skip_days:]
        low_day, low = min(series, key=lambda x: x[1]) if series else (self.start, 0.0)
        late = [cf for cf in result["cash_flow"] if cf.get("type", "").endswith(DEFERRED_SUFFIXES)]
        fees = sum(-cf["amount"] for cf in result["cash_flow"] if cf.get("type") == "FEE")
        charged = sum(cf["amount"] for cf in result["cash_flow"]
                      if cf.get("type") == "INTEREST" and cf.get("account_kind") in ("credit", "heloc"))
        debt = (sum(result["credit_final_balances"].values()) + sum(result["mortgage_final_balances"].values())
                + sum(result["heloc_final_balances"].values()))
        return {"score": score_simulation(result), "lowest": low, "lowest_date": low_day, "late": len(late),
                "fees": fees, "interest": charged, "debt": debt, "result": result}

    def main_checking(self) -> tuple[str, str] | None:
        best = None
        for b in self.manager.banks:
            for n, a in b.accounts.items():
                if a.account_type.value == "checking" and (best is None or a.balance > best[2]):
                    best = (b.name, n, a.balance)
        return (best[0], best[1]) if best else None

    def paydays(self) -> list[date]:
        days = set()
        for inc in self.manager.income_sources:
            try:
                if inc.amount > 0:
                    days.update(d for d in inc.get_pay_dates_in_range(self.start - timedelta(days=1), self.end)
                                if self.start <= d <= self.end)
            except Exception:
                pass
        return sorted(days)


def _safe(ev: dict, base: dict, floor: float) -> bool:
    """Never riskier than the baseline: no more late payments or fees, checking never below the floor."""
    return ev["late"] <= base["late"] and ev["fees"] <= base["fees"] + 0.01 and ev["lowest"] >= floor - 0.01


# ─────────────────────────────────────────────────────────────────────────
#  Debt boost
# ─────────────────────────────────────────────────────────────────────────

def _debt_list(manager) -> list[dict]:
    out = []
    for b in manager.banks:
        for n, c in b.credit_accounts.items():
            if c.balance > 0.005:
                out.append({"bank": b.name, "account": n, "kind": "credit", "balance": _r(c.balance),
                            "rate": c.interest_rate})
        for n, h in b.heloc_accounts.items():
            if h.balance > 0.005:
                out.append({"bank": b.name, "account": n, "kind": "heloc", "balance": _r(h.balance),
                            "rate": h.interest_rate})
        for n, m in b.mortgage_accounts.items():
            if m.current_principal > 0.005:
                out.append({"bank": b.name, "account": n, "kind": "mortgage", "balance": _r(m.current_principal),
                            "rate": m.interest_rate})
    return out


def _boost_events(runner: _Runner, monthly: float, strategy: str, source) -> dict:
    """Extra payments: each month's amount split across that month's paydays (or the 1st)."""
    if monthly <= 0 or not source:
        return {}
    by_month = defaultdict(list)
    for d in runner.paydays():
        by_month[(d.year, d.month)].append(d)
    d = runner.start
    while d <= runner.end:
        if (d.year, d.month) not in by_month and (d.day == 1 or d == runner.start):
            by_month[(d.year, d.month)].append(d)
        d += timedelta(days=1)
    events = defaultdict(list)
    for days in by_month.values():
        share = round(monthly / len(days), 2)
        for day in days:
            events[day].append(TimelineEvent(
                event_date=day, event_type="EXTRA_DEBT_PAYMENT", amount=share,
                description=f"Extra toward debt ({strategy})", from_bank=source[0], from_account=source[1],
                to_account=f"({strategy})"))
    return dict(events)


def _payoffs(result: dict, debts: list[dict]) -> dict:
    """{"bank:account": first date its balance reached $0} within the window."""
    out = {}
    for s in result["snapshots"]:
        for key_name in ("credit_balances", "heloc_balances", "mortgage_balances"):
            for key, bal in s[key_name].items():
                if bal <= 0.005 and key not in out:
                    out[key] = s["date"]
    start = {f"{d['bank']}:{d['account']}" for d in debts}
    return {k: v for k, v in out.items() if k in start}


def debt_boost(manager, days: int = 180, strategy: str = "avalanche", monthly: float | None = None) -> dict:
    """
    How much extra can go to debt each month without ever leaving checking
    lower (or bills later) than just paying minimums — found by simulating
    amounts (binary search to the nearest $10). With ``monthly`` given, just
    evaluates that amount.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Strategy must be one of: {', '.join(STRATEGIES)}")
    debts = _debt_list(manager)
    runner = _Runner(manager, days)
    source = runner.main_checking()
    base_res = runner.run()
    base = runner.evaluate(base_res)
    floor = min(runner.cushion, base["lowest"])
    out = {"strategy": strategy, "strategy_label": STRATEGIES[strategy], "days": days,
           "debts": sorted(debts, key=lambda d: (-d["rate"], d["balance"]) if strategy == "avalanche"
                           else (d["balance"], -d["rate"])),
           "floor": _r(floor), "source": f"{source[0]} · {source[1]}" if source else None}
    if not debts or not source:
        out.update(safe_monthly=0.0, monthly=0.0, available=False,
                   reason="No debt to pay down" if not debts else "Add a checking account first")
        return out

    def trial(x):
        ev = runner.evaluate(runner.run(_boost_events(runner, x, strategy, source)))
        return ev, _safe(ev, base, floor)

    # Search: grow until unsafe, then bisect
    lo, lo_ev, hi = 0.0, base, None
    step = 100.0
    x = step
    from models.planning import monthly_income
    ceiling = max(500.0, monthly_income(manager) * 1.2)
    while x <= ceiling:
        ev, ok = trial(x)
        if not ok:
            hi = x
            break
        lo, lo_ev = x, ev
        x *= 2
    if hi is None and lo < ceiling:
        # Every doubling was safe: try the ceiling itself, then narrow in below it
        ev, ok = trial(ceiling)
        if ok:
            lo, lo_ev = ceiling, ev  # everything up to the ceiling is safe (or debt is all paid off)
        else:
            hi = ceiling
    while hi is not None and hi - lo > 10:
        mid = round((lo + hi) / 2 / 10) * 10
        if mid in (lo, hi):
            break
        ev, ok = trial(mid)
        if ok:
            lo, lo_ev = mid, ev
        else:
            hi = mid
    safe = lo

    chosen = monthly if monthly is not None else safe
    if monthly is not None:
        chosen_ev, chosen_ok = trial(monthly) if monthly > 0 else (base, True)
    else:
        chosen_ev, chosen_ok = lo_ev, True
    paid_extra = -sum(cf["amount"] for cf in chosen_ev["result"]["cash_flow"] if cf.get("type") == "EXTRA_DEBT_PAYMENT")
    per_debt = defaultdict(float)
    for cf in chosen_ev["result"]["cash_flow"]:
        if cf.get("type") == "EXTRA_DEBT_PAYMENT":
            per_debt[f"{cf['to_bank']}:{cf['to_account']}"] += -cf["amount"]
    base_payoffs = _payoffs(base_res, debts)
    plan_payoffs = _payoffs(chosen_ev["result"], debts)
    for d in out["debts"]:
        key = f"{d['bank']}:{d['account']}"
        d["extra_paid"] = _r(per_debt.get(key, 0.0))
        d["paid_off_base"] = base_payoffs[key].isoformat() if key in base_payoffs else None
        d["paid_off_plan"] = plan_payoffs[key].isoformat() if key in plan_payoffs else None

    # The other strategy at the same amount, for comparison
    other = "snowball" if strategy == "avalanche" else "avalanche"
    other_ev = runner.evaluate(runner.run(_boost_events(runner, chosen, other, source))) if chosen > 0 else base

    out.update(
        available=True, safe_monthly=_r(safe), monthly=_r(chosen), monthly_is_safe=chosen_ok,
        capped=hi is None, extra_paid=_r(paid_extra),
        base={"debt": _r(base["debt"]), "interest": _r(base["interest"]), "lowest": _r(base["lowest"]),
              "lowest_date": base["lowest_date"].isoformat(), "late": base["late"], "score": _r(base["score"])},
        plan={"debt": _r(chosen_ev["debt"]), "interest": _r(chosen_ev["interest"]),
              "lowest": _r(chosen_ev["lowest"]), "lowest_date": chosen_ev["lowest_date"].isoformat(),
              "late": chosen_ev["late"], "score": _r(chosen_ev["score"])},
        saved=_r(chosen_ev["score"] - base["score"]),
        other_strategy={"strategy": other, "label": STRATEGIES[other], "saved": _r(other_ev["score"] - base["score"]),
                        "debt": _r(other_ev["debt"])},
    )
    return out


# ─────────────────────────────────────────────────────────────────────────
#  Due date moves
# ─────────────────────────────────────────────────────────────────────────

def _movable(bill) -> bool:
    if isinstance(bill, (AccountLinkedBill, GroupLinkedBill)):
        return False
    freq = getattr(bill.frequency, "value", bill.frequency)
    return freq == BillFrequency.MONTHLY.value and bill.amount > 0 and 1 <= int(bill.due_date or 0) <= 31


def due_date_moves(manager, days: int = 100, min_gain: float = 25.0) -> dict:
    """
    For each monthly bill, try due days just after your paydays and report
    the ones where moving the due date would fix a late payment or raise
    your lowest checking balance noticeably. (Most companies will move a
    due date if you ask.) The lowest balance is measured after the first
    month, once the new date has settled in (moving a due date later skips
    a payment inside the first month, which isn't a real gain).
    """
    days = max(days, 62)
    runner = _Runner(manager, days)
    skip = 31
    base = runner.evaluate(runner.run(), skip)
    paydays = runner.paydays()
    candidates = sorted({min(28, d.day + k) for d in paydays[:6] for k in (0, 1, 2)})
    suggestions, checked = [], 0
    for bill in manager.bills:
        if not _movable(bill):
            continue
        name, current = bill.bill_name, int(bill.due_date)
        best = None
        for day in candidates:
            if day == current:
                continue

            def tweak(banks, income, bills, groups, _name=name, _day=day):
                for b in bills:
                    if b.bill_name == _name and not isinstance(b, (AccountLinkedBill, GroupLinkedBill)):
                        b.due_date = _day

            ev = runner.evaluate(runner.run(tweak=tweak), skip)
            checked += 1
            gain = ev["lowest"] - base["lowest"]
            fixes = base["late"] - ev["late"]
            if ev["fees"] > base["fees"] + 0.01 or fixes < 0:
                continue
            key = (fixes, gain)
            if best is None or key > best[0]:
                best = (key, day, ev)
        if best is None:
            continue
        (fixes, gain), day, ev = best
        if fixes > 0 or gain >= max(min_gain, 0.05 * bill.amount):
            suggestions.append({
                "bill": name, "amount": _r(bill.amount), "current_day": current, "suggested_day": day,
                "lowest_before": _r(base["lowest"]), "lowest_after": _r(ev["lowest"]), "gain": _r(gain),
                "fixes_late": fixes,
                "why": (f"Fixes {fixes} late payment{'s' if fixes != 1 else ''}" if fixes > 0 else
                        f"Your lowest checking balance goes up by ${gain:,.0f}"),
            })
    suggestions.sort(key=lambda s: (-s["fixes_late"], -s["gain"]))
    return {"days": days, "suggestions": suggestions, "checked": checked,
            "payday_days": sorted({d.day for d in paydays}), "lowest": _r(base["lowest"]),
            "cushion": _r(runner.cushion)}


# ─────────────────────────────────────────────────────────────────────────
#  Purchase planner
# ─────────────────────────────────────────────────────────────────────────

def purchase_planner(manager, amount: float = 0.0, days: int = 60) -> dict:
    """
    How much you could spend on each day ahead, and the earliest day
    ``amount`` fits. Read from the app's plan exactly like Safe to spend:
    for each day, the lowest point the plan reaches over the look-ahead
    from that day, minus your cushion and what's already spoken for.
    Today's figure is the dashboard's Safe to spend.
    """
    from models.dashboard import held_back, safe_window, spendable_series
    from models.plan import plan_runs

    if amount < 0:
        raise ValueError("Amount can't be negative")
    today = date.today()
    window, _, _ = safe_window(manager, today)
    runs = plan_runs(manager)
    series = spendable_series(manager, runs.optimized, runs.goal)
    # Overdue and late bills are already out of the series (paid, or owed)
    held = held_back(manager, [], today)
    off = held["cushion"] + held["reserves"]
    values = [v for _, v in series]
    can_spend = []
    for i, (d, _) in enumerate(series[:days + 1]):
        low = min(values[i:i + window + 1])
        can_spend.append({"date": d.isoformat(), "amount": _r(max(0.0, low - off))})
    out = {"days": days, "amount": _r(amount), "cushion": _r(held["cushion"]), "can_spend": can_spend,
           "today": can_spend[0]["amount"] if can_spend else 0.0, "look_ahead": window,
           "best": max(can_spend, key=lambda c: c["amount"]) if can_spend else None,
           "earliest": None, "lowest_after": None}
    if amount > 0:
        for c in can_spend:
            if c["amount"] >= amount - 0.005:
                out.update(earliest=c["date"], lowest_after=_r(c["amount"] - amount + held["cushion"]))
                break
    return out
