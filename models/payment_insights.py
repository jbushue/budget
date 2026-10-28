"""
Payment insights: plain-language analysis of the payment plan.

Compares two simulations of the same window:

* **On due date** – every bill is paid on its due date from its usual
  account and nothing else happens (the plain TimelineSimulator).
* **Optimized plan** – the PaymentOptimizer's routing plus its savings
  sweeps, HELOC parking and promo payoffs.

From those it builds the data the web UI shows on the Optimizer page:

* ``comparison`` – headline numbers for both runs (ending cash, net
  position, lowest checking balance, interest, late payments).
* ``bill_timing`` – for each upcoming payment: will it be paid on time,
  which paycheck funds it, what paying it early would save (or risk), and
  how to fix it if the money won't be there.
* ``groups`` – how each bill group's single payment is split, and what a
  different split or a little extra each month would change.
* ``promos`` – 0% promo deadlines and whether the plan clears them.
* ``insights`` – a short, ranked list of recommendations with dollar
  impacts, built from all of the above.

Money values are rounded to cents. Interest savings for paying early are
estimates (daily interest on the amount paid early); they assume you carry
a balance on that card/loan.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

from .fixed_bill import AccountLinkedBill, FloatingBill, GroupLinkedBill
from .payment_optimizer import PaymentOptimizer
from .timeline_simulator import TimelineSimulator
from .types import AccountType

# Cash-flow entry types produced by TimelineSimulator.project_balances
PAID_TYPES = {
    "BILL_PAYMENT": "bill",
    "CREDIT_PAYMENT": "credit",
    "MORTGAGE_PAYMENT": "mortgage",
    "HELOC_PAYMENT": "heloc",
    "BILL_GROUP_PAYMENT": "group",
}
DEFERRED_TYPES = {
    "BILL_DEFERRED": "bill",
    "CREDIT_PAYMENT_DEFERRED": "credit",
    "MORTGAGE_DEFERRED": "mortgage",
    "HELOC_PAYMENT_DEFERRED": "heloc",
    "BILL_GROUP_DEFERRED": "group",
}
ALREADY_PAID_TYPES = {"BILL_ALREADY_PAID": "bill", "BILL_GROUP_ALREADY_PAID": "group"}

# How far ahead the bill-timing table looks (late payments are always listed)
TIMING_DAYS = 45
# Below this, a checking balance is considered "tight"
LOW_CUSHION = 100.0
# Ignore early-payment savings smaller than this
MIN_SAVINGS = 0.50
# Extra monthly amount used for "what if you paid a little more" comparisons
EXTRA_MONTHLY = 50.0

SEVERITY_ORDER = {"urgent": 0, "warning": 1, "savings": 2, "tip": 3, "good": 4}


def _r(x: float) -> float:
    return round(float(x) + 0.0, 2)


def _money(x: float) -> str:
    return f"${abs(x):,.2f}"


def _day(d: date) -> str:
    return d.strftime("%b %d").replace(" 0", " ")


def _base_name(description: str) -> str:
    for suffix in (" (insufficient funds)", " (already paid)"):
        if description.endswith(suffix):
            return description[: -len(suffix)]
    return description


# ─────────────────────────────────────────────────────────────────────────
#  Simulation summaries (also used by the what-if scenario)
# ─────────────────────────────────────────────────────────────────────────

def checking_keys(banks) -> set[str]:
    """Snapshot keys ("Bank:Account") of all checking accounts."""
    return {
        f"{bank.name}:{acc.account_name}"
        for bank in banks
        for acc in bank.get_all_accounts()
        if acc.account_type == AccountType.CHECKING
    }


def net_position(banks) -> float:
    """Cash minus all debt for live account objects."""
    cash = sum(acc.balance for b in banks for acc in b.get_all_accounts())
    debt = sum(c.balance for b in banks for c in b.get_all_credit_accounts())
    debt += sum(m.current_principal for b in banks for m in b.get_all_mortgage_accounts())
    debt += sum(h.balance for b in banks for h in b.get_all_heloc_accounts())
    return cash - debt


def summarize_simulation(result: dict, banks) -> dict:
    """
    Headline numbers for one simulation result.

    ``banks`` are the live (pre-simulation) banks, used for the starting
    net position and to know which accounts are checking accounts.
    """
    cash = sum(result["final_balances"].values())
    debt = (sum(result["credit_final_balances"].values())
            + sum(result["mortgage_final_balances"].values())
            + sum(result["heloc_final_balances"].values()))

    keys = checking_keys(banks)
    lowest, lowest_date, lowest_account = None, None, None
    for snap in result["snapshots"]:
        for key, bal in snap["balances"].items():
            if key in keys and (lowest is None or bal < lowest):
                lowest, lowest_date, lowest_account = bal, snap["date"], key

    charged = earned = fees = spending = 0.0
    paid_count = 0
    late = []
    for cf in result["cash_flow"]:
        t = cf.get("type")
        if t == "INTEREST":
            if cf.get("account_kind") in ("credit", "heloc"):
                charged += cf["amount"]
            else:
                earned += cf["amount"]
        elif t == "FEE":
            fees += -cf["amount"]
        elif t == "EVERYDAY_SPENDING":
            spending += -cf["amount"]
        elif t in PAID_TYPES:
            paid_count += 1
        elif t in DEFERRED_TYPES:
            late.append({"date": cf["date"].isoformat(),
                         "name": _base_name(cf["description"]),
                         "amount": _r(abs(cf["amount"]))})

    pending = sum(p["deferred_interest"] for p in result.get("promo_final", {}).values())

    return {
        "ending_cash": _r(cash),
        "ending_debt": _r(debt),
        "net_position": _r(cash - debt),
        "net_change": _r((cash - debt) - net_position(banks)),
        "lowest_checking": _r(lowest) if lowest is not None else None,
        "lowest_checking_date": lowest_date.isoformat() if lowest_date else None,
        "lowest_checking_account": lowest_account.split(":", 1)[1] if lowest_account else None,
        "interest_charged": _r(charged),
        "interest_earned": _r(earned),
        "payments_on_time": paid_count,
        "late_payments": late,
        "pending_deferred_interest": _r(pending),
        "fees": _r(fees),
        "everyday_spending": _r(spending),
    }


def outcome_value(summary: dict) -> float:
    """
    The bottom line used to compare plans: cash minus debt at the end of the
    window. Deferred promo interest still pending is reported separately —
    regular payments after the window may still clear the promo in time.
    """
    return summary["net_position"]


def describe_outcome_change(base: dict, other: dict, base_label: str, other_label: str) -> list[str]:
    """Plain-language sentences describing how ``other`` differs from ``base``."""
    lines = []
    diff = outcome_value(other) - outcome_value(base)
    if abs(diff) >= 0.01:
        lines.append(f"{other_label} leaves you {_money(diff)} {'better' if diff > 0 else 'worse'} off "
                     f"than {base_label} (cash minus debts).")
    else:
        lines.append(f"{other_label} ends in the same place as {base_label}.")

    dp = base.get("pending_deferred_interest", 0.0) - other.get("pending_deferred_interest", 0.0)
    if dp >= 0.01:
        lines.append(f"It clears 0% promo balances sooner: {base_label} still has promo money owed at the end, "
                     f"which could trigger up to {_money(dp)} of deferred interest if it isn't paid before expiry.")
    elif dp <= -0.01:
        lines.append(f"It leaves more 0% promo money unpaid at the end — up to {_money(dp)} of deferred interest "
                     "if it isn't paid before the promo expires.")

    bl, ol = len(base["late_payments"]), len(other["late_payments"])
    if ol > bl:
        new = list(dict.fromkeys(p["name"] for p in other["late_payments"]
                                 if p not in base["late_payments"]))[:3]
        lines.append(f"{ol - bl} more payment(s) would be late or missed"
                     + (f" (e.g. {', '.join(new)})." if new else "."))
    elif ol < bl:
        lines.append(f"{bl - ol} fewer payment(s) would be late or missed.")
    elif ol:
        lines.append(f"{ol} payment(s) are late or missed either way.")

    if base["lowest_checking"] is not None and other["lowest_checking"] is not None:
        d = other["lowest_checking"] - base["lowest_checking"]
        if abs(d) >= 1:
            lines.append(f"Your lowest checking balance {'rises' if d > 0 else 'drops'} by {_money(d)} "
                         f"(to {_money(other['lowest_checking'])}"
                         f"{' overdrawn' if other['lowest_checking'] < 0 else ''} on "
                         f"{_day(date.fromisoformat(other['lowest_checking_date']))}).")

    di = other["interest_charged"] - base["interest_charged"]
    if abs(di) >= 0.01:
        lines.append(f"Interest charged on debt {'goes up' if di > 0 else 'goes down'} by {_money(di)}.")
    df = other.get("fees", 0.0) - base.get("fees", 0.0)
    if abs(df) >= 0.01:
        lines.append(f"Late and overdraft fees {'go up' if df > 0 else 'go down'} by {_money(df)}.")
    de = other["interest_earned"] - base["interest_earned"]
    if abs(de) >= 0.01:
        lines.append(f"Interest earned on savings {'goes up' if de > 0 else 'goes down'} by {_money(de)}.")
    return lines


# ─────────────────────────────────────────────────────────────────────────
#  Analyzer
# ─────────────────────────────────────────────────────────────────────────

class PaymentInsightsAnalyzer:
    """Builds the payment insights for a FinanceManager's current state."""

    def __init__(self, manager, start_date: date | None = None, days: int = 90):
        self.manager = manager
        self.start = start_date or date.today()
        self.days = max(7, int(days))
        self.end = self.start + timedelta(days=self.days)

    # ── public ────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        m = self.manager
        banks, income, bills, groups = deepcopy((m.banks, m.income_sources, m.bills, m.bill_groups))
        baseline = TimelineSimulator(banks, income, bills, groups, **m.sim_options()).project_balances(
            self.start, self.end)

        banks2, income2, bills2, groups2 = deepcopy((m.banks, m.income_sources, m.bills, m.bill_groups))
        optimizer = PaymentOptimizer(banks2, income2, bills2, groups2, **m.sim_options())
        optimized, plan = optimizer.run_optimized_simulation(self.start, self.end)

        base_sum = summarize_simulation(baseline, m.banks)
        opt_sum = summarize_simulation(optimized, m.banks)
        # Kept for callers that need the raw runs (e.g. the dashboard)
        self.baseline, self.optimized, self.plan = baseline, optimized, plan

        self._income_dates = sorted({cf["date"] for cf in baseline["cash_flow"] if cf["type"] == "INCOME"})
        self._snapshots = {s["date"]: s for s in baseline["snapshots"]}

        timing = self._bill_timing(baseline, optimized)
        group_info = [g for g in (self._group_outlook(grp) for grp in m.bill_groups) if g]
        promos = self._promos(plan)
        moves = self._optimizer_moves(optimized)

        insights = self._insights(base_sum, opt_sum, timing, group_info, promos, moves)
        return {
            "start_date": self.start.isoformat(),
            "end_date": self.end.isoformat(),
            "days": self.days,
            "headline": self._headline(base_sum, opt_sum, timing),
            "comparison": {
                "on_due_date": base_sum,
                "optimized": opt_sum,
                "net_benefit": _r(outcome_value(opt_sum) - outcome_value(base_sum)),
                "changes": describe_outcome_change(base_sum, opt_sum, "paying everything on its due date",
                                                   "Following the optimized plan"),
            },
            "optimizer_moves": moves,
            "bill_timing": timing,
            "groups": group_info,
            "promos": promos,
            "insights": insights,
        }

    # ── bill timing ───────────────────────────────────────────────────

    def _find_bill(self, name: str, kind: str):
        for bill in self.manager.bills:
            if kind == "group":
                if isinstance(bill, GroupLinkedBill) and bill.linked_group.group_name == name:
                    return bill
            elif bill.bill_name == name and not isinstance(bill, GroupLinkedBill):
                return bill
        return None

    def _bill_kind(self, bill) -> str:
        if isinstance(bill, GroupLinkedBill):
            return "group"
        if isinstance(bill, AccountLinkedBill):
            return bill.linked_account_type
        return "floating" if isinstance(bill, FloatingBill) else "bill"

    def _early_rate(self, bill) -> float:
        """APR (%) saved per year on money paid early to this bill (0 = no benefit)."""
        if isinstance(bill, AccountLinkedBill):
            acct = bill.linked_account
            if bill.linked_account_type == "credit":
                return acct.interest_rate if getattr(acct, "regular_balance", 0) > 0 else 0.0
            if bill.linked_account_type == "heloc":
                return acct.interest_rate if acct.balance > 0 else 0.0
            return 0.0  # mortgage: interest is computed monthly, timing in the month doesn't matter
        if isinstance(bill, GroupLinkedBill):
            members = [m for m in self._group_members(bill.linked_group) if m.balance > 0]
            total = sum(m.balance for m in members)
            return sum(m.balance * m.apr for m in members) / total if total > 0 else 0.0
        return 0.0

    def _payday_before(self, due: date) -> date | None:
        """Latest paycheck date on or before ``due`` (inside the window)."""
        best = None
        for d in self._income_dates:
            if d <= due:
                best = d
        return best

    def _payday_after(self, due: date) -> date | None:
        return next((d for d in self._income_dates if d > due), None)

    def _bill_timing(self, baseline: dict, optimized: dict) -> list[dict]:
        opt_status = {}
        for cf in optimized["cash_flow"]:
            t = cf["type"]
            name = _base_name(cf["description"])
            if t in PAID_TYPES or t in ALREADY_PAID_TYPES:
                opt_status[(cf["date"], name)] = "paid"
            elif t in DEFERRED_TYPES:
                opt_status.setdefault((cf["date"], name), "late")

        horizon = self.start + timedelta(days=TIMING_DAYS)
        rows = []
        for cf in baseline["cash_flow"]:
            t = cf["type"]
            if t in PAID_TYPES:
                status, kind = "on_time", PAID_TYPES[t]
            elif t in DEFERRED_TYPES:
                status, kind = "late", DEFERRED_TYPES[t]
            elif t in ALREADY_PAID_TYPES:
                status, kind = "already_paid", ALREADY_PAID_TYPES[t]
            else:
                continue
            due = cf["date"]
            if status != "late" and due > horizon:
                continue
            name = _base_name(cf["description"])
            bill = self._find_bill(name, kind)
            if bill is not None:
                kind = self._bill_kind(bill)
            rows.append(self._timing_row(cf, name, kind, bill, due, status,
                                         opt_status.get((due, name))))
        rows.sort(key=lambda r: (r["due_date"], r["name"]))
        return rows

    def _timing_row(self, cf, name, kind, bill, due, status, opt_status) -> dict:
        amount = abs(cf["amount"])
        bank, account = cf.get("bank") or "", cf.get("account") or ""
        if not account and bill is not None:
            bank, account = bill.preferred_source_bank or "", bill.preferred_source_account or ""
        if status == "already_paid" and bill is not None:
            amount = bill.amount_on(due) if not isinstance(bill, GroupLinkedBill) else bill.amount
        row = {
            "name": name,
            "kind": kind,
            "due_date": due.isoformat(),
            "amount": _r(amount),
            "estimated": kind == "floating",
            "source_bank": bank,
            "source_account": account,
            "status": status,
            "plan_status": opt_status or status,
            "funded_by": None,
            "pay_early_date": None,
            "days_early": 0,
            "early_savings": 0.0,
            "cushion_if_early": None,
            "shortfall": 0.0,
            "fixes": [],
            "advice": "",
            "late_fee": 0.0,
            "bill_name": bill.bill_name if bill is not None else name,
        }
        if status == "already_paid":
            row["advice"] = "Already paid for this period — nothing to do."
            return row

        payday = self._payday_before(due)
        row["funded_by"] = payday.isoformat() if payday else None

        if status == "late":
            self._late_advice(row, bill, due, amount, opt_status)
            return row

        # Paying early: on the paycheck before the due date
        rate = self._early_rate(bill) if bill is not None else 0.0
        early = payday if payday and payday < due else None
        if early is None and due > self.start and rate > 0:
            early = self.start  # no paycheck before it: "early" means today
        cushion = None
        if early is not None and account:
            key = f"{bank}:{account}"
            window = [self._snapshots[d]["balances"].get(key) for d in
                      (early + timedelta(days=i) for i in range((due - early).days))
                      if d in self._snapshots]
            window = [b for b in window if b is not None]
            if window:
                cushion = min(window) - amount
        days_early = (due - early).days if early else 0
        savings = amount * rate / 100 / 365 * days_early
        row.update(pay_early_date=early.isoformat() if early else None, days_early=days_early,
                   cushion_if_early=_r(cushion) if cushion is not None else None)
        safe = cushion is None or cushion >= 0

        if kind == "mortgage":
            row["advice"] = ("Pay on or before the due date. Paying earlier in the month doesn't lower "
                             "mortgage interest — only extra principal does.")
        elif savings >= MIN_SAVINGS and safe:
            row["early_savings"] = _r(savings)
            row["advice"] = (f"Pay {days_early} day(s) early on {_day(early)}"
                             f"{' (payday)' if early == payday else ''} to save about {_money(savings)} "
                             f"in interest" + (f"; {account} still keeps {_money(cushion)}." if cushion is not None
                                               else "."))
            if cushion is not None and cushion < LOW_CUSHION:
                row["advice"] += " That's a thin cushion — only do it if nothing unexpected is coming."
        elif savings >= MIN_SAVINGS and not safe:
            row["advice"] = (f"Paying early would save about {_money(savings)}, but {account} would run short "
                             f"by {_money(cushion)} before the due date. Pay on {_day(due)}.")
        elif rate > 0:
            row["advice"] = f"Pay by {_day(due)}. Paying early saves only pennies here."
        else:
            msg = f"Pay on the due date ({_day(due)}) — paying early doesn't save money"
            if early is not None and cushion is not None and cushion < LOW_CUSHION:
                msg += f" and would leave {account} at {_money(cushion)}{' overdrawn' if cushion < 0 else ''}"
            row["advice"] = msg + "."
        if payday and payday < due:
            row["advice"] += f" Covered by your {_day(payday)} paycheck."
        elif not payday:
            row["advice"] += " Comes out of your current balance (no paycheck before it)."
        return row

    def _late_fee(self, bill) -> float:
        if bill is None:
            return 0.0
        own = getattr(bill, "late_fee", None)
        if own is not None:
            return max(0.0, own)
        fees = self.manager.fees or {}
        if isinstance(bill, AccountLinkedBill) and bill.linked_account_type in ("credit", "heloc"):
            return fees.get("card_late_fee", 0.0)
        return fees.get("default_late_fee", 0.0)

    def _late_advice(self, row, bill, due, amount, opt_status):
        snap = self._snapshots.get(due)
        balances = []
        for b in self.manager.banks:
            for acc in b.get_all_accounts():
                key = f"{b.name}:{acc.account_name}"
                bal = snap["balances"].get(key, 0.0) if snap else acc.balance
                balances.append((bal, b.name, acc.account_name))
        balances.sort(reverse=True)
        best = balances[0] if balances else (0.0, "", "")
        short = max(0.0, amount - max(best[0], 0.0))
        row["shortfall"] = _r(short)
        fixes = []

        if opt_status == "paid":
            fixes.append("The optimized plan pays this on time by routing money differently — follow the plan.")
        total_cash = sum(max(b[0], 0.0) for b in balances)
        if len(balances) > 1 and total_cash >= amount and best[0] > 0:
            donor = next((b for b in balances[1:] if b[0] > 0), None)
            if donor:
                fixes.append(f"Move {_money(short)} from {donor[2]} into {best[2]} before {_day(due)}.")
        if row["kind"] in ("bill", "floating"):
            for b in self.manager.banks:
                for card in b.get_all_credit_accounts():
                    if card.credit_limit - card.balance >= amount:
                        fixes.append(f"Charge it to {card.account_name} (available credit "
                                     f"{_money(card.credit_limit - card.balance)}) and pay the card later.")
                        break
                else:
                    continue
                break
        for b in self.manager.banks:
            for h in b.get_all_heloc_accounts():
                if h.get_available_credit(due) >= short > 0:
                    fixes.append(f"Draw {_money(short)} from {h.account_name} (HELOC) to cover the gap.")
                    break
        nxt = self._payday_after(due)
        if nxt:
            fixes.append(f"Otherwise the earliest income to pay it from arrives {_day(nxt)} "
                         f"({(nxt - due).days} days late).")
        row["fixes"] = fixes
        where = f" in {best[2]}" if best[2] else ""
        fee = self._late_fee(bill)
        fee_text = f"Expect a late fee of about {_money(fee)}" if fee > 0 else "Late payments can bring late fees"
        row["late_fee"] = _r(fee)
        row["advice"] = (f"Not enough money{where} on {_day(due)} — short about {_money(short)}. "
                         f"{fee_text}, and loans/cards 30+ days late can hurt your credit.")

    # ── bill groups ───────────────────────────────────────────────────

    def _group_members(self, group) -> list[SimpleNamespace]:
        members = []
        for member in group.members:
            acc = group._resolve_account(member, self.manager.banks)
            if acc is None:
                continue
            members.append(SimpleNamespace(member=member, name=member.account_name,
                                           balance=acc.balance, apr=acc.interest_rate))
        return members

    @staticmethod
    def _simulate_group(members, payment: float, split, max_months: int = 600) -> dict:
        """Month-by-month payoff of a group's members using ``split`` to allocate."""
        bals = [m.balance for m in members]
        months, interest = 0, 0.0
        first_interest = sum(b * m.apr / 1200 for b, m in zip(bals, members))
        if payment <= first_interest + 0.005:
            return {"months": None, "interest": None, "pays_off": False}
        while sum(bals) > 0.01 and months < max_months:
            month_interest = [b * m.apr / 1200 for b, m in zip(bals, members)]
            bals = [b + i for b, i in zip(bals, month_interest)]
            interest += sum(month_interest)
            amounts = split(bals, month_interest, payment)
            bals = [max(0.0, b - a) for b, a in zip(bals, amounts)]
            months += 1
        return {"months": months, "interest": _r(interest), "pays_off": sum(bals) <= 0.01}

    def _group_outlook(self, group) -> dict | None:
        members = self._group_members(group)
        owing = [m for m in members if m.balance > 0]
        if not owing:
            return None
        payment = group.total_payment

        def current_split(bals, _interest, pay):
            resolved = [(m.member, SimpleNamespace(balance=b)) for m, b in zip(members, bals) if b > 0]
            planned = iter(group.plan_amounts(resolved, pay))
            return [next(planned) if b > 0 else 0.0 for b in bals]

        def highest_rate_split(bals, interest, pay):
            # Cover each member's interest first, then send the rest to the highest APR
            amounts = [min(b, i) for b, i in zip(bals, interest)]
            left = max(0.0, pay - sum(amounts))
            for idx in sorted(range(len(bals)), key=lambda k: -members[k].apr):
                take = min(left, bals[idx] - amounts[idx])
                amounts[idx] += take
                left -= take
            return amounts

        next_split = current_split([m.balance for m in members], None, payment)
        current = self._simulate_group(members, payment, current_split)
        best = self._simulate_group(members, payment, highest_rate_split)
        extra = self._simulate_group(members, payment + EXTRA_MONTHLY, current_split)
        monthly_interest = sum(m.balance * m.apr / 1200 for m in members)

        rates = {m.apr for m in owing}
        savings = 0.0
        suggested = None
        top = max(owing, key=lambda m: m.apr)
        if len(rates) > 1 and current["pays_off"] and best["pays_off"]:
            savings = current["interest"] - best["interest"]
            others_interest = sum(m.balance * m.apr / 1200 for m in owing if m is not top)
            suggested = max(0.0, min(top.balance, payment - others_interest))

        return {
            "group_name": group.group_name,
            "payment": _r(payment),
            "total_balance": _r(sum(m.balance for m in members)),
            "monthly_interest": _r(monthly_interest),
            "members": [
                {"account_name": m.name, "balance": _r(m.balance), "apr": m.apr,
                 "allocation_method": m.member.allocation_method.value,
                 "next_payment_share": _r(share),
                 "monthly_interest": _r(m.balance * m.apr / 1200)}
                for m, share in zip(members, next_split)
            ],
            "current": current,
            "highest_rate_first": best,
            "with_extra": {**extra, "extra_monthly": EXTRA_MONTHLY},
            "reallocation_savings": _r(max(0.0, savings)),
            "highest_rate_member": top.name,
            "suggested_fixed_amount": _r(suggested) if suggested is not None else None,
        }

    # ── promos ────────────────────────────────────────────────────────

    def _promos(self, plan) -> list[dict]:
        out = []
        for p in plan.promo_priorities:
            scheduled = sum(s["amount"] for s in plan.promo_payoff_schedule
                            if s["promo_name"] == p.promo_name and s["credit_account"] == p.credit_account_name)
            in_window = p.end_date <= self.end
            shortfall = max(0.0, p.balance_owed - scheduled)
            months_free = 0
            for b in self.manager.banks:
                card = b.credit_accounts.get(p.credit_account_name) if b.name == p.bank_name else None
                if card:
                    promo = next((x for x in card.active_promos if x.promo_name == p.promo_name), None)
                    months_free = promo.months_interest_free if promo else 0
            r = p.interest_rate_after / 1200
            at_risk = p.balance_owed * ((1 + r) ** months_free - 1) if months_free else 0.0
            out.append({
                "card": p.credit_account_name,
                "bank": p.bank_name,
                "promo_name": p.promo_name,
                "balance": _r(p.balance_owed),
                "expires": p.end_date.isoformat(),
                "days_left": p.days_remaining,
                "monthly_needed": _r(p.required_monthly_payment),
                "scheduled_in_window": _r(scheduled),
                # Fully scheduled = on track; otherwise only a problem if it expires in the window
                "on_track": True if shortfall <= 0.01 else (False if in_window else None),
                "shortfall": _r(shortfall) if in_window else 0.0,
                "interest_at_risk": _r(at_risk),
                "apr_after": p.interest_rate_after,
            })
        return out

    # ── optimizer moves ───────────────────────────────────────────────

    @staticmethod
    def _optimizer_moves(optimized: dict) -> list[dict]:
        labels = {
            "SAVINGS_SWEEP": ("Move spare cash to savings", "Earns interest until it's needed for bills."),
            "SAVINGS_RECALL": ("Bring money back from savings", "Returns swept cash ahead of upcoming bills."),
            "HELOC_PARK": ("Pay spare cash onto the HELOC", "Lowers the HELOC balance (and its interest) "
                                                           "while the money isn't needed."),
            "HELOC_RECALL": ("Draw back from the HELOC", "Pulls parked cash back before bills are due."),
            "PROMO_PAYOFF": ("Pay down a 0% promo", "Clears the promo before it expires so deferred "
                                                    "interest never hits."),
            "EXTRA_CREDIT_PAYMENT": ("Extra card payment", "Pays the target card down faster."),
        }
        moves = []
        for cf in optimized["cash_flow"]:
            if cf["type"] in labels:
                title, why = labels[cf["type"]]
                moves.append({
                    "date": cf["date"].isoformat(),
                    "type": cf["type"],
                    "title": title,
                    "why": why,
                    "description": cf.get("description", ""),
                    "amount": _r(abs(cf.get("amount", 0))),
                })
        return moves

    # ── headline + ranked insights ────────────────────────────────────

    def _headline(self, base, opt, timing) -> str:
        late_base = len(base["late_payments"])
        late_opt = len(opt["late_payments"])
        upcoming = [r for r in timing if r["status"] != "already_paid"]
        if late_opt:
            first = opt["late_payments"][0]
            return (f"{late_opt} payment(s) in the next {self.days} days can't be covered as things stand — "
                    f"the first is {first['name']} on {_day(date.fromisoformat(first['date']))}. "
                    "See the fixes below.")
        if late_base:
            return (f"Paying everything on its due date leaves {late_base} payment(s) short, but the optimized "
                    f"plan gets every bill paid on time over the next {self.days} days.")
        benefit = outcome_value(opt) - outcome_value(base)
        msg = f"All {len(upcoming)} upcoming payment(s) are covered on time."
        if benefit >= 0.01:
            msg += f" Following the optimized plan leaves you {_money(benefit)} better off over {self.days} days."
        return msg

    def _insights(self, base, opt, timing, groups, promos, moves) -> list[dict]:
        items = []

        def add(severity, category, title, detail, impact=0.0, when=None):
            items.append({"severity": severity, "category": category, "title": title,
                          "detail": detail, "impact": _r(impact), "date": when})

        for row in timing:
            if row["status"] == "late":
                due = date.fromisoformat(row["due_date"])
                if row["plan_status"] == "paid":
                    add("warning", "late", f"{row['name']} is only on time if you follow the plan",
                        f"Paid on its due date from the usual account, {row['name']} ({_money(row['amount'])}) "
                        f"would be short on {_day(due)}. " + " ".join(row["fixes"][:2]),
                        when=row["due_date"])
                else:
                    add("urgent", "late", f"{row['name']} can't be paid on {_day(due)}",
                        f"{_money(row['amount'])} due, short about {_money(row['shortfall'])}. "
                        + " ".join(row["fixes"][:2]),
                        impact=-row["shortfall"], when=row["due_date"])

        if opt["lowest_checking"] is not None and opt["lowest_checking"] < LOW_CUSHION \
                and not opt["late_payments"]:
            low_date = date.fromisoformat(opt["lowest_checking_date"])
            add("warning", "cushion", f"Checking gets thin around {_day(low_date)}",
                f"{opt['lowest_checking_account']} drops to {_money(opt['lowest_checking'])}"
                f"{' (overdrawn)' if opt['lowest_checking'] < 0 else ''}. Hold off on extra spending until the "
                "next paycheck, or keep a little more in checking.", when=opt["lowest_checking_date"])

        for p in promos:
            if p["on_track"] is False:
                add("urgent" if p["days_left"] <= 60 else "warning", "promo",
                    f"{p['promo_name']} on {p['card']} won't be cleared in time",
                    f"{_money(p['balance'])} left, expires {_day(date.fromisoformat(p['expires']))}. "
                    f"The plan is short {_money(p['shortfall'])}. If any balance remains, about "
                    f"{_money(p['interest_at_risk'])} of deferred interest could be charged.",
                    impact=-p["interest_at_risk"], when=p["expires"])
            elif p["on_track"] is True:
                add("good", "promo", f"{p['promo_name']} on {p['card']} is on track",
                    f"The plan pays off {_money(p['balance'])} before it expires on "
                    f"{_day(date.fromisoformat(p['expires']))}, protecting you from up to "
                    f"{_money(p['interest_at_risk'])} of deferred interest.",
                    when=p["expires"])
            else:
                add("tip", "promo", f"Plan ahead for {p['promo_name']} on {p['card']}",
                    f"Expires {_day(date.fromisoformat(p['expires']))} (after this window). Pay about "
                    f"{_money(p['monthly_needed'])}/month to clear {_money(p['balance'])} in time.",
                    when=p["expires"])

        early = [r for r in timing if r["early_savings"] > 0]
        if early:
            total = sum(r["early_savings"] for r in early)
            names = ", ".join(f"{r['name']} on {_day(date.fromisoformat(r['pay_early_date']))}" for r in early[:3])
            add("savings", "timing", "Pay interest-bearing debts on payday",
                f"Paying these as soon as your paycheck lands instead of on the due date saves about "
                f"{_money(total)} in interest: {names}{'…' if len(early) > 3 else ''}. Regular bills "
                "(utilities, subscriptions) gain nothing from early payment.", impact=total)

        for g in groups:
            if not g["current"]["pays_off"]:
                add("urgent", "group", f"{g['group_name']} payment doesn't cover the interest",
                    f"{_money(g['payment'])}/month vs. about {_money(g['monthly_interest'])} of interest — the "
                    "balance will grow. Raise the payment or look at income-driven/refinance options.")
                continue
            if g["reallocation_savings"] >= 1:
                months = g["current"]["months"] - g["highest_rate_first"]["months"]
                add("savings", "group", f"Point {g['group_name']} at {g['highest_rate_member']} first",
                    f"Sending everything above the interest to the highest-rate loan saves about "
                    f"{_money(g['reallocation_savings'])}" + (f" and {months} month(s)" if months > 0 else "")
                    + f". On the Bill Groups page set {g['highest_rate_member']} to Fixed "
                    f"{_money(g['suggested_fixed_amount'] or 0)} (and ask your servicer to apply it that way).",
                    impact=g["reallocation_savings"])
            ex = g["with_extra"]
            if ex["pays_off"] and g["current"]["interest"] and ex["interest"] is not None:
                saved = g["current"]["interest"] - ex["interest"]
                months = g["current"]["months"] - ex["months"]
                if saved >= 1:
                    add("tip", "group", f"An extra {_money(EXTRA_MONTHLY)}/month on {g['group_name']}",
                        f"Pays it off {months} month(s) sooner and saves about {_money(saved)} in interest "
                        f"({g['current']['months']} → {ex['months']} months).", impact=saved)

        gained = (opt["interest_earned"] - base["interest_earned"]) + (base["interest_charged"] - opt["interest_charged"])
        if moves and gained >= 0.01:
            kinds = sorted({m["title"].lower() for m in moves if m["type"] in ("SAVINGS_SWEEP", "HELOC_PARK")})
            add("savings", "optimizer", "Let idle cash work between paychecks",
                f"The plan makes {len(moves)} transfer(s) ({', '.join(kinds) or 'promo payoffs'}), "
                f"worth about {_money(gained)} in interest earned or avoided, and brings the money back "
                "before bills are due.", impact=gained)

        if not any(i["severity"] in ("urgent", "warning") for i in items):
            add("good", "status", "Every bill is covered on time",
                f"Over the next {self.days} days all payments go out on their due dates without overdrawing "
                "an account.")

        items.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], -abs(i["impact"]), i["date"] or ""))
        return items
