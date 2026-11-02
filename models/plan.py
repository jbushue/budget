"""
One plan for the whole app.

Every forward-looking number (Dashboard, Timeline, Optimizer, What-if, the
optimizer tools, alerts, the digest, reports) is read from the SAME year-long
simulation of the plan you chose, so two pages never disagree about a day
they both show:

* ``plan_runs(manager)`` runs the plan once for ``PLAN_DAYS`` and caches it
  until anything changes (balances, bills, income, settings, the date).
  It holds both runs the app talks about: the *plan* (optimized, following
  your goal) and *paying on due dates* (no moves), for comparison.
* ``slice_result(result, end)`` cuts a run down to the days a page shows.
  A 30-day view is the first 30 days of the same plan, not a different plan.

The optimizer judges a plan by where it leaves you at the end of its window,
so running it over different windows used to give different plans for the
same days. One fixed window removes that.
"""

from __future__ import annotations

import hashlib
import pickle
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta

PLAN_DAYS = 365
_KEEP = 4  # cached runs kept (the plan, plus a few goals for "Compare goals")


@dataclass
class PlanRuns:
    start: date
    end: date
    goal: str
    target: str | None
    baseline: dict    # paying every bill on its due date, no moves
    optimized: dict   # the plan
    plan: object      # PaymentPlan summary of the optimized run


def _fingerprint(manager, goal: str, target: str | None, start: date, days: int) -> str:
    state = (manager.banks, manager.income_sources, manager.bills, manager.bill_groups)
    try:
        blob = pickle.dumps(state, protocol=4)
    except Exception:  # unpicklable state: never reuse a cached run
        blob = repr(id(state)).encode() + repr(date.today()).encode() + repr(id(object())).encode()
    extra = repr((manager.sim_options(), manager.cushion, manager.min_hold_days, goal, target,
                  start, days)).encode()
    return hashlib.sha1(blob + extra).hexdigest()


def floor(manager) -> float:
    """The least the plan keeps in checking: your cushion."""
    return max(0.0, float(getattr(manager, "cushion", 0.0) or 0.0))


def plan_runs(manager, goal: str | None = None, target: str | None = None,
              start: date | None = None, days: int = PLAN_DAYS) -> PlanRuns:
    """
    Both runs for ``goal`` (default: the plan the app follows), cached.
    Callers must treat the results as read-only.
    """
    from models.payment_optimizer import PaymentOptimizer
    from models.timeline_simulator import TimelineSimulator

    if goal is None:
        goal, target = manager.plan_goal()
    if goal != "payoff_credit_account":
        target = None
    start = start or date.today()
    days = max(PLAN_DAYS, int(days))
    key = _fingerprint(manager, goal, target, start, days)
    cache = manager.__dict__.setdefault("_plan_runs", {})
    if key in cache:
        cache[key] = cache.pop(key)  # most recently used last
        return cache[key]

    end = start + timedelta(days=days)
    banks, income, bills, groups = deepcopy((manager.banks, manager.income_sources, manager.bills,
                                             manager.bill_groups))
    baseline = TimelineSimulator(banks, income, bills, groups, **manager.sim_options()).project_balances(start, end)
    banks, income, bills, groups = deepcopy((manager.banks, manager.income_sources, manager.bills,
                                             manager.bill_groups))
    optimizer = PaymentOptimizer(banks, income, bills, groups, **manager.sim_options())
    optimized, summary = optimizer.run_optimized_simulation(
        start, end, goal, target, discretionary_buffer=floor(manager),
        min_hold_days=getattr(manager, "min_hold_days", 7))
    runs = PlanRuns(start, end, goal, target, baseline, optimized, summary)
    cache[key] = runs
    while len(cache) > _KEEP:
        cache.pop(next(iter(cache)))
    return runs


def invalidate(manager) -> None:
    manager.__dict__.pop("_plan_runs", None)


def slice_result(result: dict, end: date, banks=None) -> dict:
    """
    The first part of a run, through ``end``, shaped like a full run (final
    balances are the balances on ``end``). ``banks`` (the live banks) are
    used to rebuild what's left on 0% promos at ``end``.
    """
    if end >= result["end_date"]:
        return result
    snaps = [s for s in result["snapshots"] if s["date"] <= end]
    last = snaps[-1] if snaps else None
    out = dict(result)
    out["end_date"] = end
    out["snapshots"] = snaps
    out["cash_flow"] = [cf for cf in result["cash_flow"] if cf["date"] <= end]
    out["events"] = [e for e in result.get("events", []) if e.event_date <= end]
    out["final_balances"] = dict(last["balances"]) if last else dict(result["final_balances"])
    out["credit_final_balances"] = dict(last["credit_balances"]) if last else {}
    out["mortgage_final_balances"] = dict(last["mortgage_balances"]) if last else {}
    out["heloc_final_balances"] = dict(last["heloc_balances"]) if last else {}
    out["promo_final"] = _promo_final(last, end, banks, result) if last and banks is not None else {}
    return out


def _promo_final(snap: dict, end: date, banks, full: dict) -> dict:
    """
    Same shape as TimelineSimulator's promo_final, for promos still running
    on ``end`` — leaving out the ones the rest of the plan pays off before
    they expire (the money is already planned for them).
    """
    by_date = {s["date"]: s for s in full["snapshots"]}
    from models.date_utils import is_clamped_day
    out = {}
    for bank in banks:
        for credit in bank.get_all_credit_accounts():
            next_payment = None
            if credit.payment_due_date:
                next_payment = end + timedelta(days=1)
                while not is_clamped_day(next_payment, credit.payment_due_date):
                    next_payment += timedelta(days=1)
            rate = credit.interest_rate / 12 / 100
            for promo in credit.active_promos:
                key = f"{bank.name}:{credit.account_name}:{promo.promo_name}"
                remaining = snap.get("promo_balances", {}).get(key, 0.0)
                if remaining > 0.005 and not promo.interest_charged and promo.end_date > end:
                    later = by_date.get(promo.end_date - timedelta(days=1))
                    if later is not None and later.get("promo_balances", {}).get(key, 0.0) <= 0.005:
                        continue
                    out[key] = {"remaining": remaining, "end_date": promo.end_date, "next_payment": next_payment,
                                "deferred_interest": remaining * ((1 + rate) ** promo.months_interest_free - 1)}
    return out


def runs_for(manager, days: int, goal: str | None = None, target: str | None = None,
             start: date | None = None) -> tuple[PlanRuns, dict, dict]:
    """(runs, baseline through day ``days``, plan through day ``days``)."""
    runs = plan_runs(manager, goal, target, start, days)
    end = runs.start + timedelta(days=days)
    return (runs, slice_result(runs.baseline, end, manager.banks),
            slice_result(runs.optimized, end, manager.banks))


# ── one definition of "checking" and "spendable" money ─────────────────────

def checking_keys(banks) -> set[str]:
    """Snapshot keys ("Bank:Account") of checking accounts: the money bills and everyday spending come out of."""
    return {f"{b.name}:{a.account_name}" for b in banks for a in b.get_all_accounts()
            if a.account_type.value == "checking"}


def checking_series(result: dict, keys: set[str]) -> list[tuple[date, float]]:
    """Total in checking at the end of each day."""
    return [(s["date"], sum(v for k, v in s["balances"].items() if k in keys)) for s in result["snapshots"]]
