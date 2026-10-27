from datetime import date, timedelta
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator, TimelineEvent


@dataclass
class PromoPayoffPriority:
    """Represents a promotional offer that needs to be paid off before expiration."""
    credit_account_name: str
    bank_name: str
    promo_name: str
    balance_owed: float
    end_date: date
    days_remaining: int
    required_monthly_payment: float  # Amount needed per month to pay off in time
    interest_rate_after: float  # APR that will apply if not paid off
    priority_score: float  # Higher = more urgent (based on time and amount)

    def __lt__(self, other):
        # Sort by priority score descending (higher priority first)
        return self.priority_score > other.priority_score


@dataclass
class SavingsTransfer:
    """Represents a recommended transfer between checking and savings to maximize interest."""
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount: float
    transfer_date: date
    reason: str  # 'maximize_interest' or 'fund_upcoming_bills'
    estimated_interest_gain: float = 0.0  # Estimated additional interest earned

    def __repr__(self):
        return f"Transfer ${self.amount:,.2f} from {self.from_account} to {self.to_account} on {self.transfer_date}"


@dataclass
class PaymentPlan:
    """Represents an optimized payment plan for bills and mortgages."""
    strategy: dict  # {bill_name: {bank: name, account: name, date: date}}
    total_interest_paid: float
    total_fees: float
    final_discretionary: float  # Cash available after all obligations
    violations: list[str] = field(default_factory=list)  # Any constraint violations
    extra_credit_payments: list[dict] = field(default_factory=list)  # Extra payments to credit accounts
    target_credit_payoff: Optional[str] = None  # Target credit account for payoff goal
    promo_payoff_schedule: list[dict] = field(default_factory=list)  # Scheduled promo payoff payments
    promo_priorities: list[PromoPayoffPriority] = field(default_factory=list)  # Promos needing payoff
    mortgage_payments: list[dict] = field(default_factory=list)  # Scheduled mortgage payments
    total_mortgage_principal: float = 0.0  # Total principal paid in period
    total_mortgage_interest: float = 0.0  # Total mortgage interest paid in period
    transfer_recommendations: list[SavingsTransfer] = field(default_factory=list)  # Recommended transfers
    estimated_interest_earned: float = 0.0  # Estimated interest earned from savings optimization
    simulation_result: dict = field(default_factory=dict)  # Full timeline simulation result

    def __repr__(self):
        return (
            f"PaymentPlan(interest=${self.total_interest_paid:.2f}, "
            f"discretionary=${self.final_discretionary:.2f}, "
            f"violations={len(self.violations)}, "
            f"extra_credit_payments={len(self.extra_credit_payments)}, "
            f"promo_payoffs={len(self.promo_payoff_schedule)}, "
            f"mortgage_payments={len(self.mortgage_payments)}, "
            f"transfers={len(self.transfer_recommendations)})"
        )


@dataclass
class CashFlowEvent:
    """Represents a cash flow event for planning."""
    event_date: date
    event_type: str  # 'INCOME', 'BILL', 'CREDIT_PAYMENT'
    amount: float
    description: str
    source_name: Optional[str] = None  # Income source or bill name
    
    def __lt__(self, other):
        return self.event_date < other.event_date


class PaymentOptimizer:
    """
    Optimizes which accounts to pay bills from to maximize discretionary funds
    while ensuring all bills are paid on time.

    This optimizer uses the TimelineSimulator as the single source of truth for
    how bills, income, mortgages, and credit payments are calculated. It then
    layers on additional analysis and optimizations:

    - Determines optimal payment routing (which account pays which bill)
    - Plans promotional offer payoff schedules
    - Calculates extra credit card payments for payoff goals
    - Recommends savings transfers for interest optimization
    - Validates constraints (overdrafts, missed payments, low balances)

    Strategy:
    - Pay bills from accounts with lowest opportunity cost (checking before savings)
    - Time payments close to due date to maximize float
    - For credit payoff goal, maximize extra payments to target credit account
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill], bill_groups=None):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills
        self.bill_groups = bill_groups or []

    # ─────────────────────────────────────────────────────────────────────
    #  UNIFIED OPTIMIZATION: build events + run the optimized simulation
    # ─────────────────────────────────────────────────────────────────────

    def run_optimized_simulation(
        self,
        start_date: date,
        end_date: date,
        optimization_goal: str = "maximize_discretionary",
        target_credit_account: str = None,
        discretionary_buffer: float = 300.0,
        min_hold_days: int = 7,
    ) -> tuple[dict, 'PaymentPlan']:
        """
        Two-pass optimization:
          1. Run a baseline simulation to understand cash flow patterns
          2. Build injection events (sweeps, promo payoffs, extra payments)
          3. Re-run the simulation with injected events applied

        Args:
            min_hold_days: Minimum number of days money must stay parked in
                savings or HELOC before it's worth sweeping. Prevents wasteful
                sweep-then-recall churn that doesn't meaningfully affect
                interest/dividends. Default 7.

        Returns:
            (simulation_result, payment_plan_summary)
        """
        if optimization_goal == "payoff_credit_account" and not target_credit_account:
            raise ValueError("target_credit_account is required for 'payoff_credit_account' goal")

        # ── Pass 1: Baseline simulation ──────────────────────────────────
        baseline = self._run_simulation(start_date, end_date)

        # Extract schedules from baseline
        bill_schedule = self._extract_bill_schedule(baseline)
        mortgage_schedule = self._extract_mortgage_schedule(baseline)
        credit_schedule = self._extract_credit_schedule(baseline)
        income_dates = self._extract_income_dates(baseline)

        # Build payment routing strategy
        strategy = self._create_payment_strategy(
            start_date, end_date, income_dates, bill_schedule,
            optimization_goal, mortgage_schedule, credit_schedule
        )

        # ── Build optimization injection events ──────────────────────────
        injected_events = defaultdict(list)

        # Find promo priorities and schedule payoff events
        promo_priorities = self._find_promo_payoff_priorities(start_date, end_date)
        promo_payoff_schedule = self._calculate_promo_payoff_schedule(
            start_date, end_date, income_dates, bill_schedule,
            promo_priorities, credit_schedule, mortgage_schedule
        )
        self._inject_promo_payoff_events(injected_events, promo_payoff_schedule)

        # Extra credit payments for payoff goal
        extra_credit_payments = []
        if optimization_goal == "payoff_credit_account" and target_credit_account:
            extra_credit_payments = self._calculate_extra_credit_payments(
                start_date, end_date, income_dates, bill_schedule,
                target_credit_account, strategy, promo_payoff_schedule,
                credit_schedule, mortgage_schedule
            )
            self._inject_extra_credit_events(injected_events, extra_credit_payments, target_credit_account)

        # Savings sweeps, HELOC parking, and recalls
        self._inject_sweep_events(
            injected_events, start_date, end_date, income_dates,
            bill_schedule, credit_schedule, mortgage_schedule,
            promo_payoff_schedule, extra_credit_payments,
            discretionary_buffer, min_hold_days, baseline=baseline
        )

        # ── Pass 2: Optimized simulation with injected events ────────────
        optimized_result = self._run_simulation(
            start_date, end_date, strategy,
            injected_events=dict(injected_events)
        )

        # ── Build summary PaymentPlan from the optimized result ──────────
        # Interest CHARGED on debt (credit cards / HELOCs) vs. interest
        # EARNED on bank accounts are reported separately.
        total_interest = sum(
            cf['amount'] for cf in optimized_result['cash_flow']
            if cf.get('type') == 'INTEREST' and cf['amount'] > 0
            and self._is_interest_charged(cf)
        )

        mortgage_payments = [
            cf for cf in optimized_result['cash_flow']
            if cf.get('type') == 'MORTGAGE_PAYMENT'
        ]
        total_mortgage_principal = sum(cf.get('principal', 0) for cf in mortgage_payments)
        total_mortgage_interest = sum(cf.get('interest', 0) for cf in mortgage_payments)

        final_discretionary = sum(optimized_result["final_balances"].values())

        # Validate constraints
        violations = self._check_constraints(optimized_result, bill_schedule, mortgage_schedule)

        # Check promo payoff completeness
        for promo in promo_priorities:
            total_scheduled = sum(
                p['amount'] for p in promo_payoff_schedule
                if p['promo_name'] == promo.promo_name
                and p['credit_account'] == promo.credit_account_name
            )
            shortfall = promo.balance_owed - total_scheduled
            if shortfall > 0.01:
                if promo.end_date > end_date:
                    violations.append(
                        f"INFO: Promo '{promo.promo_name}' on {promo.credit_account_name} "
                        f"expires {promo.end_date} (beyond analysis window). "
                        f"Remaining balance: ${shortfall:.2f}. Plan ahead."
                    )
                else:
                    violations.append(
                        f"WARNING: Promo '{promo.promo_name}' on {promo.credit_account_name} "
                        f"may not be fully paid off before {promo.end_date}. "
                        f"Shortfall: ${shortfall:.2f}. Deferred interest may apply."
                    )

        # Interest earned on bank accounts (savings sweeps etc.)
        estimated_interest = sum(
            cf['amount'] for cf in optimized_result['cash_flow']
            if cf.get('type') == 'INTEREST'
            and cf['amount'] > 0
            and not self._is_interest_charged(cf)
        )
        # Gather transfer recommendations from cash_flow
        transfer_recommendations = []
        for cf in optimized_result['cash_flow']:
            if cf.get('type') in ('SAVINGS_SWEEP', 'SAVINGS_RECALL', 'HELOC_PARK', 'HELOC_RECALL'):
                transfer_recommendations.append(SavingsTransfer(
                    from_bank=cf.get('from_bank', ''),
                    from_account=cf.get('from_account', ''),
                    to_bank=cf.get('to_bank', ''),
                    to_account=cf.get('to_account', ''),
                    amount=abs(cf.get('amount', 0)),
                    transfer_date=cf['date'],
                    reason=cf['type'].lower(),
                ))

        plan = PaymentPlan(
            strategy=strategy,
            total_interest_paid=total_interest,
            total_fees=0.0,
            final_discretionary=final_discretionary,
            violations=violations,
            extra_credit_payments=extra_credit_payments,
            target_credit_payoff=target_credit_account,
            promo_payoff_schedule=promo_payoff_schedule,
            promo_priorities=promo_priorities,
            mortgage_payments=mortgage_payments,
            total_mortgage_principal=total_mortgage_principal,
            total_mortgage_interest=total_mortgage_interest,
            transfer_recommendations=transfer_recommendations,
            estimated_interest_earned=estimated_interest,
            simulation_result=optimized_result,
        )

        return optimized_result, plan

    def _is_interest_charged(self, cf: dict) -> bool:
        """
        True when an INTEREST cash-flow entry is interest charged on debt
        (credit card / HELOC), False when it is interest earned on a bank
        account. Uses the simulator's account_kind tag, falling back to an
        account-name lookup.
        """
        kind = cf.get('account_kind')
        if kind is not None:
            return kind in ('credit', 'heloc')
        acct = cf.get('account', '')
        bank_name = cf.get('bank')
        for bank in self.banks:
            if bank_name and bank.name != bank_name:
                continue
            if acct in bank.accounts:
                return False
            if acct in bank.credit_accounts or acct in bank.heloc_accounts:
                return True
        return False

    def _inject_promo_payoff_events(
        self,
        injected: dict,
        promo_schedule: list[dict],
    ):
        """Convert promo payoff schedule into TimelineEvent objects."""
        for p in promo_schedule:
            evt_date = p['date']
            # Find source checking account
            src_bank, src_account = self._find_best_checking_account()
            if not src_bank:
                continue
            injected[evt_date].append(TimelineEvent(
                event_date=evt_date,
                event_type="PROMO_PAYOFF",
                amount=p['amount'],
                description=p['description'],
                from_bank=src_bank,
                from_account=src_account,
                to_bank=p['bank'],
                to_account=p['credit_account'],
                promo_name=p.get('promo_name'),
            ))

    def _inject_extra_credit_events(
        self,
        injected: dict,
        extra_payments: list[dict],
        target_credit_account: str,
    ):
        """Convert extra credit payments into TimelineEvent objects."""
        for ep in extra_payments:
            evt_date = ep['date']
            src_bank, src_account = self._find_best_checking_account()
            if not src_bank:
                continue
            injected[evt_date].append(TimelineEvent(
                event_date=evt_date,
                event_type="EXTRA_CREDIT_PAYMENT",
                amount=ep['amount'],
                description=ep['description'],
                from_bank=src_bank,
                from_account=src_account,
                to_bank=ep['bank'],
                to_account=target_credit_account,
            ))

    def _inject_sweep_events(
        self,
        injected: dict,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        credit_schedule: list[dict],
        mortgage_schedule: list[dict],
        promo_payoff_schedule: list[dict],
        extra_credit_payments: list[dict],
        discretionary_buffer: float,
        min_hold_days: int = 7,
        baseline: dict = None,
    ):
        """
        Build savings-sweep, HELOC-park, and recall events.

        If the baseline simulation result is given, HELOC payments are counted
        as outflows and only the part of each paycheck deposited to checking
        is counted as available cash.

        Strategy:
        - On each income date, after accounting for upcoming outflows until
          the next income date, sweep excess checking into the best
          interest-bearing vehicle (savings or HELOC in draw period).
        - Before large outflow clusters, recall from savings/HELOC if
          checking will be insufficient.
        - Always keep at least `discretionary_buffer` in checking for
          groceries, gas, and fun.
        - Only sweep if the money can stay parked for at least
          `min_hold_days` before it would need to be recalled. This
          prevents wasteful churn (park today, recall tomorrow) that
          doesn't meaningfully affect interest or dividends.
        """
        if not income_dates:
            return

        min_sweep = 100.0  # Don't bother with tiny transfers

        # Find checking/savings/HELOC pairs
        checking_info = []
        savings_info = []
        heloc_info = []

        for bank in self.banks:
            for name, acc in bank.accounts.items():
                if acc.account_type.value == "checking":
                    checking_info.append((bank.name, name, acc))
                elif acc.account_type.value == "savings" and acc.interest_rate > 0:
                    savings_info.append((bank.name, name, acc))
            for name, heloc in bank.heloc_accounts.items():
                from models.types import HELOCPhase
                if heloc.get_phase_on_date(start_date) == HELOCPhase.DRAW and heloc.balance > 0:
                    heloc_info.append((bank.name, name, heloc))

        if not checking_info:
            return

        # Determine best parking target: highest-rate savings or HELOC (whichever saves more)
        best_savings = max(savings_info, key=lambda x: x[2].interest_rate, default=None)
        best_heloc = max(heloc_info, key=lambda x: x[2].interest_rate, default=None)

        primary_checking_bank, primary_checking_name, _ = checking_info[0]

        # Build a timeline of known outflows
        outflows_by_date = defaultdict(float)
        for b in bill_schedule:
            outflows_by_date[b['due_date']] += b['amount']
        for c in credit_schedule:
            outflows_by_date[c['due_date']] += c['minimum_payment']
        for m in mortgage_schedule:
            outflows_by_date[m['due_date']] += m['total_payment']
        for p in promo_payoff_schedule:
            outflows_by_date[p['date']] += p['amount']
        for ep in extra_credit_payments:
            outflows_by_date[ep['date']] += ep['amount']

        # Build income amounts by date
        income_by_date = defaultdict(float)
        if baseline is not None:
            checking_keys = {(b, n) for b, n, _ in checking_info}
            for cf in baseline.get('cash_flow', []):
                if cf.get('type') == 'HELOC_PAYMENT':
                    outflows_by_date[cf['date']] += -cf['amount']
                elif cf.get('type') == 'INCOME' and (cf.get('bank'), cf.get('account')) in checking_keys:
                    income_by_date[cf['date']] += cf['amount']
        else:
            for income in self.income_sources:
                pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
                for pd in pay_dates:
                    income_by_date[pd] += income.amount

        # Track how much is "parked" so we know how much we can recall
        parked_in_savings = 0.0
        parked_in_heloc = 0.0

        # Simulate a lightweight cash-flow model to determine sweep amounts.
        # Start with today's checking minus whatever is due before the first payday.
        sim_checking = sum(acc.balance for _, _, acc in checking_info)
        sim_checking -= sum(amt for d, amt in outflows_by_date.items() if d < income_dates[0])

        for i, income_date in enumerate(income_dates):
            # Add income arriving on this date
            sim_checking += income_by_date.get(income_date, 0)

            # Find the next income date (or end_date + 1 day)
            next_income = income_dates[i + 1] if i + 1 < len(income_dates) else end_date + timedelta(days=1)

            # Sum all outflows between this income date (inclusive) and next
            outflows_in_period = sum(
                amt for d, amt in outflows_by_date.items()
                if income_date <= d < next_income
            )

            sim_checking -= outflows_in_period

            # How much can we sweep?
            excess = sim_checking - discretionary_buffer
            if excess >= min_sweep:
                sweep_amount = (excess // 100) * 100  # Round down to $100
                if sweep_amount >= min_sweep:
                    sweep_date = income_date + timedelta(days=1)
                    if sweep_date > end_date:
                        sweep_date = income_date

                    # ── Min hold-days check ──
                    # Look ahead: will we need to recall this money within
                    # min_hold_days? If so, skip the sweep — it's not worth
                    # the churn.
                    earliest_recall_date = sweep_date + timedelta(days=min_hold_days)
                    need_recall_soon = False

                    # Start from the actual checking balance BEFORE this
                    # period's outflows were subtracted, subtract the sweep,
                    # then walk forward day by day through the hold window.
                    pre_outflow_checking = sim_checking + outflows_in_period
                    lookahead_balance = pre_outflow_checking - sweep_amount

                    # Gather all dates with cash-flow events in the hold window
                    hold_window_dates = set()
                    for d in outflows_by_date:
                        if income_date <= d < earliest_recall_date:
                            hold_window_dates.add(d)
                    for d in income_by_date:
                        if income_date <= d < earliest_recall_date:
                            hold_window_dates.add(d)

                    for d in sorted(hold_window_dates):
                        lookahead_balance += income_by_date.get(d, 0)
                        lookahead_balance -= outflows_by_date.get(d, 0)
                        if lookahead_balance < discretionary_buffer:
                            need_recall_soon = True
                            break

                    if need_recall_soon:
                        # Not worth sweeping — we'd just recall it right back
                        continue

                    # Also skip if the sweep wouldn't survive until end_date
                    # and there's not enough time to earn meaningful interest
                    days_to_end = (end_date - sweep_date).days
                    if days_to_end < min_hold_days:
                        continue

                    # Decide: park in HELOC (if saves more) or savings
                    target_type = "SAVINGS_SWEEP"
                    target_bank = best_savings[0] if best_savings else None
                    target_account = best_savings[1] if best_savings else None

                    if best_heloc:
                        heloc_rate = best_heloc[2].interest_rate
                        savings_rate = best_savings[2].interest_rate if best_savings else 0
                        if heloc_rate > savings_rate:
                            target_type = "HELOC_PARK"
                            target_bank = best_heloc[0]
                            target_account = best_heloc[1]

                    if target_bank and target_account:
                        desc = f"Sweep to {target_account}" if target_type == "SAVINGS_SWEEP" else f"Park in HELOC {target_account}"
                        injected[sweep_date].append(TimelineEvent(
                            event_date=sweep_date,
                            event_type=target_type,
                            amount=sweep_amount,
                            description=desc,
                            from_bank=primary_checking_bank,
                            from_account=primary_checking_name,
                            to_bank=target_bank,
                            to_account=target_account,
                        ))
                        sim_checking -= sweep_amount
                        if target_type == "SAVINGS_SWEEP":
                            parked_in_savings += sweep_amount
                        else:
                            parked_in_heloc += sweep_amount

            # Check if checking will go below buffer BEFORE bills due
            # If so, generate a recall event 1 day before the first large outflow
            if sim_checking < discretionary_buffer and (parked_in_savings > 0 or parked_in_heloc > 0):
                shortfall = discretionary_buffer - sim_checking + min_sweep
                # Recall from wherever we parked
                recall_date = income_date
                if parked_in_savings > 0:
                    recall_amount = min(shortfall, parked_in_savings)
                    recall_amount = (recall_amount // 100 + 1) * 100  # Round up
                    recall_amount = min(recall_amount, parked_in_savings)
                    if recall_amount >= min_sweep and best_savings:
                        injected[recall_date].append(TimelineEvent(
                            event_date=recall_date,
                            event_type="SAVINGS_RECALL",
                            amount=recall_amount,
                            description=f"Recall from {best_savings[1]}",
                            from_bank=best_savings[0],
                            from_account=best_savings[1],
                            to_bank=primary_checking_bank,
                            to_account=primary_checking_name,
                        ))
                        sim_checking += recall_amount
                        parked_in_savings -= recall_amount
                        shortfall -= recall_amount

                if shortfall > 0 and parked_in_heloc > 0 and best_heloc:
                    recall_amount = min(shortfall, parked_in_heloc)
                    recall_amount = (recall_amount // 100 + 1) * 100
                    recall_amount = min(recall_amount, parked_in_heloc)
                    if recall_amount >= min_sweep:
                        injected[recall_date].append(TimelineEvent(
                            event_date=recall_date,
                            event_type="HELOC_RECALL",
                            amount=recall_amount,
                            description=f"Recall from HELOC {best_heloc[1]}",
                            from_bank=best_heloc[0],
                            from_account=best_heloc[1],
                            to_bank=primary_checking_bank,
                            to_account=primary_checking_name,
                        ))
                        sim_checking += recall_amount
                        parked_in_heloc -= recall_amount

    def _find_best_checking_account(self) -> tuple[str, str] | tuple[None, None]:
        """Find the checking account with the highest balance."""
        best = None
        for bank in self.banks:
            for name, acc in bank.accounts.items():
                if acc.account_type.value == "checking":
                    if best is None or acc.balance > best[2]:
                        best = (bank.name, name, acc.balance)
        return (best[0], best[1]) if best else (None, None)

    def optimize_payment_schedule(
        self,
        start_date: date,
        end_date: date,
        optimization_goal: str = "maximize_discretionary",
        target_credit_account: str = None,
        discretionary_buffer: float = 300.0,
        min_hold_days: int = 7,
    ) -> PaymentPlan:
        """
        Optimize payment schedule between start and end dates.

        Uses a two-pass approach: run baseline simulation, compute
        optimization events, then re-run with those events injected into
        the timeline so all optimizations are reflected in balances.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            optimization_goal:
                - 'maximize_discretionary': Maximize cash on hand
                - 'minimize_interest': Minimize interest charges
                - 'payoff_credit_account': Maximize payments to target credit account
            target_credit_account: Required when optimization_goal is 'payoff_credit_account'
            discretionary_buffer: Minimum cash kept in checking for daily expenses
            min_hold_days: Minimum days money must stay parked before sweeping

        Returns:
            PaymentPlan with optimized strategy and the simulation result
        """
        _, plan = self.run_optimized_simulation(
            start_date, end_date, optimization_goal,
            target_credit_account, discretionary_buffer, min_hold_days
        )
        return plan

    # ─────────────────────────────────────────────────────────────────────
    #  TIMELINE SIMULATION (single source of truth)
    # ─────────────────────────────────────────────────────────────────────

    def _run_simulation(
        self,
        start_date: date,
        end_date: date,
        payment_strategy: dict = None,
        injected_events: dict = None,
    ) -> dict:
        """
        Run a timeline simulation. This is the ONLY place we create a
        TimelineSimulator — every schedule, balance, and cash-flow event
        is derived from this result.
        """
        # Deepcopy as a single unit so AccountLinkedBill references stay connected
        copied_banks, copied_income, copied_bills, copied_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )
        simulator = TimelineSimulator(
            copied_banks,
            copied_income,
            copied_bills,
            copied_groups
        )
        return simulator.project_balances(
            start_date, end_date, payment_strategy,
            injected_events=injected_events,
        )

    # ─────────────────────────────────────────────────────────────────────
    #  EXTRACT SCHEDULES FROM SIMULATION RESULT
    # ─────────────────────────────────────────────────────────────────────

    def _extract_bill_schedule(self, simulation_result: dict) -> list[dict]:
        """
        Extract the bill schedule from a simulation result's events.
        The timeline simulator is the authority on when bills are due.

        Credit-card and mortgage linked bills are NOT included — they are
        covered by _extract_credit_schedule / _extract_mortgage_schedule, and
        including them here double-counted those outflows. Bill-group
        payments ARE included (flagged 'is_group') so their outflows count.
        """
        from models.fixed_bill import AccountLinkedBill
        bill_schedule = []
        for event in simulation_result.get('events', []):
            if event.event_type not in ('BILL_DUE', 'BILL_GROUP_PAYMENT'):
                continue
            bill_name = event.description.replace("Bill: ", "")
            bill_obj = next((b for b in self.bills if b.bill_name == bill_name), None)
            if (isinstance(bill_obj, AccountLinkedBill)
                    and bill_obj.linked_account_type in ('credit', 'mortgage')):
                continue
            bill_schedule.append({
                'bill': bill_obj,
                'bill_name': bill_name,
                'amount': event.amount,
                'due_date': event.event_date,
                'preferred_bank': bill_obj.preferred_source_bank if bill_obj else None,
                'preferred_account': bill_obj.preferred_source_account if bill_obj else None,
                'is_group': event.event_type == 'BILL_GROUP_PAYMENT',
            })
        return sorted(bill_schedule, key=lambda x: x['due_date'])

    def _extract_mortgage_schedule(self, simulation_result: dict) -> list[dict]:
        """
        Extract the mortgage payment schedule from bill events.
        Since mortgages are now AccountLinkedBill objects, their events are BILL_DUE.
        """
        from models.fixed_bill import AccountLinkedBill
        mortgage_schedule = []
        for event in simulation_result.get('events', []):
            if event.event_type == 'BILL_DUE':
                bill_name = event.description.replace("Bill: ", "")
                bill_obj = next((b for b in self.bills if b.bill_name == bill_name), None)
                if isinstance(bill_obj, AccountLinkedBill) and bill_obj.linked_account_type == 'mortgage':
                    mortgage = bill_obj.linked_account
                    mortgage_schedule.append({
                        'mortgage': mortgage,
                        'mortgage_name': mortgage.account_name,
                        'bill_name': bill_name,
                        'bank_name': bill_obj.linked_bank_name,
                        'total_payment': event.amount,
                        'principal': mortgage.current_monthly_principal,
                        'interest': mortgage.current_monthly_interest,
                        'escrow': mortgage.escrow.total_monthly,
                        'due_date': event.event_date,
                        'preferred_bank': mortgage.preferred_source_bank,
                        'preferred_account': mortgage.preferred_source_account,
                    })
        return sorted(mortgage_schedule, key=lambda x: x['due_date'])

    def _extract_income_dates(self, simulation_result: dict) -> list[date]:
        """
        Extract unique income dates from a simulation result's events.
        """
        income_dates = set()
        for event in simulation_result.get('events', []):
            if event.event_type == 'INCOME':
                income_dates.add(event.event_date)
        return sorted(income_dates)

    def _extract_credit_schedule(self, simulation_result: dict) -> list[dict]:
        """
        Extract the credit payment schedule from bill events.
        Since credit cards are now AccountLinkedBill objects, their events are BILL_DUE.
        """
        from models.fixed_bill import AccountLinkedBill
        credit_schedule = []
        for event in simulation_result.get('events', []):
            if event.event_type == 'BILL_DUE':
                bill_name = event.description.replace("Bill: ", "")
                bill_obj = next((b for b in self.bills if b.bill_name == bill_name), None)
                if isinstance(bill_obj, AccountLinkedBill) and bill_obj.linked_account_type == 'credit':
                    credit = bill_obj.linked_account
                    credit_schedule.append({
                        'credit_account': credit,
                        'credit_name': credit.account_name,
                        'bill_name': bill_name,
                        'bank_name': bill_obj.linked_bank_name,
                        'minimum_payment': event.amount,
                        'full_balance': credit.balance,
                        'due_date': event.event_date,
                        'interest_rate': credit.interest_rate,
                    })
        return sorted(credit_schedule, key=lambda x: x['due_date'])

    # ─────────────────────────────────────────────────────────────────────
    #  BACKWARD-COMPATIBLE SCHEDULE BUILDERS
    #  (kept for direct use in tests and internal methods that need
    #   schedules without running a full simulation first)
    # ─────────────────────────────────────────────────────────────────────

    def _find_income_dates(self, start_date: date, end_date: date) -> list[date]:
        """Find all income deposit dates in the period using efficient method."""
        all_income_dates = []

        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                if pay_date not in all_income_dates:
                    all_income_dates.append(pay_date)

        return sorted(all_income_dates)

    def _build_bill_schedule(self, start_date: date, end_date: date) -> list[dict]:
        """Build a schedule of all bills due in the period with amounts and due dates."""
        bill_schedule = []

        for bill in self.bills:
            current = start_date
            while current <= end_date:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due > end_date:
                    break
                if next_due >= start_date:
                    bill_schedule.append({
                        'bill': bill,
                        'bill_name': bill.bill_name,
                        'amount': bill.amount,
                        'due_date': next_due,
                        'preferred_bank': bill.preferred_source_bank,
                        'preferred_account': bill.preferred_source_account
                    })
                current = next_due + timedelta(days=1)

        return sorted(bill_schedule, key=lambda x: x['due_date'])

    def _build_mortgage_schedule(self, start_date: date, end_date: date) -> list[dict]:
        """Build a schedule of all mortgage payments due in the period."""
        mortgage_schedule = []

        for bank in self.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                current = start_date
                while current <= end_date:
                    next_due = mortgage.get_next_due_date(current - timedelta(days=1))
                    if next_due > end_date:
                        break
                    if next_due >= start_date:
                        mortgage_schedule.append({
                            'mortgage': mortgage,
                            'mortgage_name': mortgage.account_name,
                            'bank_name': bank.name,
                            'total_payment': mortgage.total_monthly_payment,
                            'principal': mortgage.current_monthly_principal,
                            'interest': mortgage.current_monthly_interest,
                            'escrow': mortgage.escrow.total_monthly,
                            'due_date': next_due,
                            'preferred_bank': mortgage.preferred_source_bank,
                            'preferred_account': mortgage.preferred_source_account
                        })
                    current = next_due + timedelta(days=1)

        return sorted(mortgage_schedule, key=lambda x: x['due_date'])

    def _build_credit_payment_schedule(self, start_date: date, end_date: date) -> list[dict]:
        """Build a schedule of all credit card minimum payments due in the period."""
        credit_schedule = []

        for bank in self.banks:
            for credit_name, credit_account in bank.credit_accounts.items():
                if credit_account.payment_due_date and credit_account.balance > 0:
                    current = start_date
                    while current <= end_date:
                        if current.day == credit_account.payment_due_date:
                            min_payment = credit_account.calculate_minimum_payment()
                            credit_schedule.append({
                                'credit_account': credit_account,
                                'credit_name': credit_name,
                                'bank_name': bank.name,
                                'minimum_payment': min_payment,
                                'full_balance': credit_account.balance,
                                'due_date': current,
                                'interest_rate': credit_account.interest_rate
                            })
                        current += timedelta(days=1)

        return sorted(credit_schedule, key=lambda x: x['due_date'])

    def _build_cash_flow_timeline(self, start_date: date, end_date: date) -> list[CashFlowEvent]:
        """
        Build a complete timeline of cash flow events.

        This is a lightweight summary kept for backward compatibility.
        """
        events = []

        # Add income events
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                events.append(CashFlowEvent(
                    event_date=pay_date,
                    event_type='INCOME',
                    amount=income.amount,
                    description=f"Income: {income.source_name}",
                    source_name=income.source_name
                ))

        # Add bill events
        for bill in self.bills:
            current = start_date
            while current <= end_date:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due > end_date:
                    break
                if next_due >= start_date:
                    events.append(CashFlowEvent(
                        event_date=next_due,
                        event_type='BILL',
                        amount=-bill.amount,
                        description=f"Bill: {bill.bill_name}",
                        source_name=bill.bill_name
                    ))
                current = next_due + timedelta(days=1)

        # Add mortgage events
        for bank in self.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                current = start_date
                while current <= end_date:
                    next_due = mortgage.get_next_due_date(current - timedelta(days=1))
                    if next_due > end_date:
                        break
                    if next_due >= start_date:
                        events.append(CashFlowEvent(
                            event_date=next_due,
                            event_type='MORTGAGE',
                            amount=-mortgage.total_monthly_payment,
                            description=f"Mortgage: {mortgage.account_name}",
                            source_name=mortgage.account_name
                        ))
                    current = next_due + timedelta(days=1)

        # Add credit card payment events
        for bank in self.banks:
            for credit_name, credit_account in bank.credit_accounts.items():
                if credit_account.payment_due_date and credit_account.balance > 0:
                    current = start_date
                    while current <= end_date:
                        if current.day == credit_account.payment_due_date:
                            min_payment = credit_account.calculate_minimum_payment()
                            events.append(CashFlowEvent(
                                event_date=current,
                                event_type='CREDIT_PAYMENT',
                                amount=-min_payment,
                                description=f"Credit: {credit_name} (min payment)",
                                source_name=credit_name
                            ))
                        current += timedelta(days=1)

        return sorted(events)

    # ─────────────────────────────────────────────────────────────────────
    #  PROMO PAYOFF ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def _find_promo_payoff_priorities(self, start_date: date, end_date: date) -> list[PromoPayoffPriority]:
        """
        Find all promotional offers that need to be paid off before expiration.

        Returns a prioritized list of promos, sorted by urgency (expiring soonest first,
        then by amount owed).
        """
        promo_priorities = []
        today = start_date

        for bank in self.banks:
            for credit_name, credit_account in bank.credit_accounts.items():
                for promo in credit_account.active_promos:
                    if promo.has_expired(start_date) or promo.interest_charged:
                        continue

                    promo_balance = credit_account.promo_balance.get(promo.promo_name, 0.0)

                    if promo_balance <= 0:
                        continue

                    days_remaining = (promo.end_date - today).days

                    if days_remaining <= 0:
                        days_remaining = 1

                    months_remaining = max(days_remaining / 30.0, 0.1)
                    required_monthly = promo_balance / months_remaining
                    required_monthly = min(required_monthly, promo_balance)

                    time_urgency = 1000 / max(days_remaining, 1)
                    balance_factor = promo_balance / 1000
                    interest_factor = credit_account.interest_rate / 10

                    priority_score = time_urgency * 2 + balance_factor + interest_factor

                    promo_priorities.append(PromoPayoffPriority(
                        credit_account_name=credit_name,
                        bank_name=bank.name,
                        promo_name=promo.promo_name,
                        balance_owed=promo_balance,
                        end_date=promo.end_date,
                        days_remaining=days_remaining,
                        required_monthly_payment=required_monthly,
                        interest_rate_after=credit_account.interest_rate,
                        priority_score=priority_score
                    ))

        return sorted(promo_priorities)

    def _calculate_promo_payoff_schedule(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        promo_priorities: list[PromoPayoffPriority],
        credit_schedule: list[dict] = None,
        mortgage_schedule: list[dict] = None,
    ) -> list[dict]:
        """
        Calculate a schedule of payments to pay off promotional balances before expiration.

        Promos MUST be paid off before expiration to avoid deferred interest.
        This method guarantees full payoff using as few payments as possible by:
        1. Determining monthly payment dates (one per calendar month) from available income dates
        2. Scheduling one large payment per month per promo instead of many small ones
        3. Scheduling any remaining shortfall on the last payment date before expiration
        """
        promo_payments = []
        credit_schedule = credit_schedule or []
        mortgage_schedule = mortgage_schedule or []

        if not promo_priorities or not income_dates:
            return []

        # Track running balances per income period to know what's available
        running_balance = sum(
            account.balance
            for bank in self.banks
            for account in bank.accounts.values()
        )

        safety_buffer = 300.0

        remaining_promo_balances = {
            f"{p.bank_name}:{p.credit_account_name}:{p.promo_name}": p.balance_owed
            for p in promo_priorities
        }

        # ── Pick one payment date per calendar month ─────────────────────
        # Use the LAST income date in each month so we accumulate the most
        # funds before making the payment.
        monthly_income_dates: list[date] = []
        month_buckets: dict[tuple[int, int], list[date]] = {}
        for d in income_dates:
            key = (d.year, d.month)
            month_buckets.setdefault(key, []).append(d)
        for key in sorted(month_buckets):
            # Pick the last income date in each month
            monthly_income_dates.append(max(month_buckets[key]))

        if not monthly_income_dates:
            monthly_income_dates = income_dates[:1] if income_dates else [start_date]

        # ── Pre-compute cumulative available funds at each monthly date ──
        # Walk through ALL income dates to track the running balance, but
        # only schedule promo payments on the monthly payment dates.
        available_at_monthly: dict[date, float] = {}
        sim_balance = running_balance

        for i, income_date in enumerate(income_dates):
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )
            sim_balance += income_amount

            next_income = income_dates[i + 1] if i + 1 < len(income_dates) else end_date + timedelta(days=1)

            bills_in_period = sum(
                b['amount'] for b in bill_schedule
                if income_date <= b['due_date'] < next_income
            )
            credit_payments_in_period = sum(
                c['minimum_payment'] for c in credit_schedule
                if income_date <= c['due_date'] < next_income
            )
            mortgage_payments_in_period = sum(
                m['total_payment'] for m in mortgage_schedule
                if income_date <= m['due_date'] < next_income
            )
            sim_balance -= bills_in_period
            sim_balance -= credit_payments_in_period
            sim_balance -= mortgage_payments_in_period

            if income_date in monthly_income_dates:
                available_at_monthly[income_date] = max(0, sim_balance - safety_buffer)

        # ── Pass 1: Schedule one payment per month per promo ─────────────
        for mi, monthly_date in enumerate(monthly_income_dates):
            available_for_promos = available_at_monthly.get(monthly_date, 0)
            if available_for_promos <= 0:
                continue

            for promo in promo_priorities:
                promo_key = f"{promo.bank_name}:{promo.credit_account_name}:{promo.promo_name}"
                remaining = remaining_promo_balances.get(promo_key, 0)

                if remaining <= 0:
                    continue

                # Only schedule payments before the promo expires
                if monthly_date >= promo.end_date:
                    continue

                # How many monthly payment dates remain before this promo expires?
                future_monthly_dates = [
                    d for d in monthly_income_dates[mi:] if d < promo.end_date
                ]
                num_remaining_months = len(future_monthly_dates)

                if num_remaining_months <= 0:
                    continue

                # Spread remaining balance evenly across remaining monthly dates
                target_payment = remaining / num_remaining_months
                # Round up to the penny to avoid perpetual small shortfalls
                target_payment = round(target_payment + 0.005, 2)

                next_monthly = monthly_income_dates[mi + 1] if mi + 1 < len(monthly_income_dates) else end_date + timedelta(days=1)
                promo_expires_soon = promo.end_date <= next_monthly
                if promo_expires_soon:
                    # Last chance — pay it all
                    payment_amount = min(remaining, available_for_promos)
                else:
                    payment_amount = min(target_payment, remaining, available_for_promos)

                if payment_amount > 0.01:
                    payment_amount = round(payment_amount, 2)

                    payment_date = monthly_date + timedelta(days=3)
                    if payment_date >= promo.end_date:
                        payment_date = promo.end_date - timedelta(days=1)
                    if payment_date < start_date:
                        payment_date = start_date

                    promo_payments.append({
                        'credit_account': promo.credit_account_name,
                        'bank': promo.bank_name,
                        'promo_name': promo.promo_name,
                        'amount': payment_amount,
                        'date': payment_date,
                        'description': f"Promo payoff: {promo.promo_name} on {promo.credit_account_name}",
                        'is_urgent': promo_expires_soon,
                        'promo_end_date': promo.end_date
                    })

                    remaining_promo_balances[promo_key] -= payment_amount
                    remaining_promo_balances[promo_key] = round(remaining_promo_balances[promo_key], 2)
                    available_for_promos -= payment_amount
                    # Also update the sim_balance so future monthly availability is accurate
                    for future_d in monthly_income_dates[mi:]:
                        if future_d in available_at_monthly:
                            available_at_monthly[future_d] -= payment_amount

                if available_for_promos <= 0:
                    break

        # ── Pass 2: Guarantee full payoff for any remaining shortfalls ──
        # If any promo still has a remaining balance, add it to an existing
        # payment on the closest date, or create one final payment.
        for promo in promo_priorities:
            promo_key = f"{promo.bank_name}:{promo.credit_account_name}:{promo.promo_name}"
            remaining = remaining_promo_balances.get(promo_key, 0)

            if remaining <= 0.01:
                continue

            # Find the last income date before the promo expires
            last_income_before_expiry = None
            for d in reversed(income_dates):
                if d < promo.end_date:
                    last_income_before_expiry = d
                    break

            if not last_income_before_expiry:
                last_income_before_expiry = start_date

            payment_date = last_income_before_expiry + timedelta(days=3)
            if payment_date >= promo.end_date:
                payment_date = promo.end_date - timedelta(days=1)
            if payment_date < start_date:
                payment_date = start_date

            payment_amount = round(remaining, 2)

            # Try to consolidate with an existing payment for this promo
            # that is on the same date or within a few days
            consolidated = False
            for existing in promo_payments:
                if (existing['promo_name'] == promo.promo_name
                        and existing['credit_account'] == promo.credit_account_name
                        and abs((existing['date'] - payment_date).days) <= 3):
                    existing['amount'] = round(existing['amount'] + payment_amount, 2)
                    existing['is_urgent'] = True
                    consolidated = True
                    break

            if not consolidated:
                promo_payments.append({
                    'credit_account': promo.credit_account_name,
                    'bank': promo.bank_name,
                    'promo_name': promo.promo_name,
                    'amount': payment_amount,
                    'date': payment_date,
                    'description': f"Promo payoff (final): {promo.promo_name} on {promo.credit_account_name}",
                    'is_urgent': True,
                    'promo_end_date': promo.end_date
                })

            remaining_promo_balances[promo_key] = 0.0

        # ── Final consolidation: merge payments on the same date ─────────
        consolidated_payments = []
        payment_map: dict[str, dict] = {}  # key → payment dict
        for p in promo_payments:
            key = f"{p['promo_name']}|{p['credit_account']}|{p['date'].isoformat()}"
            if key in payment_map:
                payment_map[key]['amount'] = round(payment_map[key]['amount'] + p['amount'], 2)
                if p.get('is_urgent'):
                    payment_map[key]['is_urgent'] = True
            else:
                payment_map[key] = dict(p)
        consolidated_payments = list(payment_map.values())

        # Sort by date for clean display
        consolidated_payments.sort(key=lambda p: (p['date'], p['promo_name']))

        return consolidated_payments

    # ─────────────────────────────────────────────────────────────────────
    #  PAYMENT STRATEGY (account routing optimization)
    # ─────────────────────────────────────────────────────────────────────

    def _create_payment_strategy(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        optimization_goal: str,
        mortgage_schedule: list[dict] = None,
        credit_schedule: list[dict] = None
    ) -> dict:
        """
        Create an optimized payment strategy for all bills, mortgages, and credit card payments.

        Strategy rules:
        1. Always pay bills, mortgages, and credit minimums on or before due date
        2. Pay from checking accounts before savings (lower opportunity cost)
        3. Consider timing relative to income to avoid overdraft
        4. For minimize_interest: Pay credit card bills as early as possible

        Strategy keys are "{bill_name}_{due_date ISO}" — the same key the
        TimelineSimulator looks up for each bill occurrence, so the routing
        chosen here is actually applied. Mortgage and credit entries use the
        linked bill's name ("[Auto] <account> Payment").
        """
        strategy = {}
        mortgage_schedule = mortgage_schedule or []
        credit_schedule = credit_schedule or []

        # Create a working copy of balances to track available funds
        working_balances = {}
        for bank in self.banks:
            for name, account in bank.accounts.items():
                working_balances[f"{bank.name}:{name}"] = account.balance

        # Track income by date to know when funds arrive
        income_by_date = {}
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                if pay_date not in income_by_date:
                    income_by_date[pay_date] = 0.0
                income_by_date[pay_date] += income.amount

        # Track which income dates have been processed
        processed_income_dates = set()

        # Process bills in chronological order
        for bill_info in bill_schedule:
            if bill_info.get('is_group') or bill_info['bill'] is None:
                # Group payments are routed by the group's own source account
                continue
            bill = bill_info['bill']
            due_date = bill_info['due_date']
            amount = bill_info['amount']

            payment_date = self._determine_payment_date(
                due_date, income_dates, optimization_goal
            )

            # Add any income that arrives before payment date to working balances
            for inc_date, inc_amount in income_by_date.items():
                if inc_date <= payment_date and inc_date not in processed_income_dates:
                    processed_income_dates.add(inc_date)
                    for bank in self.banks:
                        for name, account in bank.accounts.items():
                            if account.account_type.value == "checking":
                                key = f"{bank.name}:{name}"
                                if key not in working_balances:
                                    working_balances[key] = 0.0
                                working_balances[key] += inc_amount
                                break
                        break

            best_bank, best_account = self._select_payment_account_smart(
                bill, amount, working_balances, optimization_goal
            )

            if best_bank and best_account:
                key = f"{best_bank}:{best_account}"
                if key in working_balances:
                    working_balances[key] -= amount

                strategy_key = f"{bill.bill_name}_{due_date.isoformat()}"
                strategy[strategy_key] = {
                    "bank": best_bank,
                    "account": best_account,
                    "date": payment_date,
                    "amount": amount,
                    "bill_name": bill.bill_name
                }

        # Process mortgages in chronological order
        for mortgage_info in mortgage_schedule:
            mortgage = mortgage_info['mortgage']
            due_date = mortgage_info['due_date']
            amount = mortgage_info['total_payment']

            payment_date = due_date

            for inc_date, inc_amount in income_by_date.items():
                if inc_date <= payment_date and inc_date not in processed_income_dates:
                    processed_income_dates.add(inc_date)
                    for bank in self.banks:
                        for name, account in bank.accounts.items():
                            if account.account_type.value == "checking":
                                key = f"{bank.name}:{name}"
                                if key not in working_balances:
                                    working_balances[key] = 0.0
                                working_balances[key] += inc_amount
                                break
                        break

            best_bank, best_account = self._select_mortgage_payment_account(
                mortgage, amount, working_balances
            )

            if best_bank and best_account:
                key = f"{best_bank}:{best_account}"
                if key in working_balances:
                    working_balances[key] -= amount

                bill_name = mortgage_info.get('bill_name') or f"[Auto] {mortgage.account_name} Payment"
                strategy[f"{bill_name}_{due_date.isoformat()}"] = {
                    "bank": best_bank,
                    "account": best_account,
                    "date": payment_date,
                    "amount": amount,
                    "type": "mortgage",
                    "bill_name": bill_name,
                    "mortgage_name": mortgage.account_name,
                }

        # Process credit card payments in chronological order
        for credit_info in credit_schedule:
            credit_account = credit_info['credit_account']
            due_date = credit_info['due_date']
            amount = credit_info['minimum_payment']

            if amount <= 0:
                continue

            payment_date = due_date

            # Add any income that arrives before payment date to working balances
            for inc_date, inc_amount in income_by_date.items():
                if inc_date <= payment_date and inc_date not in processed_income_dates:
                    processed_income_dates.add(inc_date)
                    for bank in self.banks:
                        for name, account in bank.accounts.items():
                            if account.account_type.value == "checking":
                                key = f"{bank.name}:{name}"
                                if key not in working_balances:
                                    working_balances[key] = 0.0
                                working_balances[key] += inc_amount
                                break
                        break

            # Reuse mortgage payment account selection (same priority logic)
            best_bank, best_account = self._select_credit_payment_account(
                credit_info, amount, working_balances
            )

            if best_bank and best_account:
                key = f"{best_bank}:{best_account}"
                if key in working_balances:
                    working_balances[key] -= amount

                credit_name = credit_info['credit_name']
                bill_name = credit_info.get('bill_name') or f"[Auto] {credit_name} Payment"
                strategy_key = f"{bill_name}_{due_date.isoformat()}"
                strategy[strategy_key] = {
                    "bank": best_bank,
                    "account": best_account,
                    "date": payment_date,
                    "amount": amount,
                    "full_balance": credit_info['full_balance'],
                    "interest_rate": credit_info['interest_rate'],
                    "type": "credit_payment",
                    "credit_name": credit_name,
                    "bill_name": bill_name,
                }

        return strategy

    def _select_mortgage_payment_account(
        self,
        mortgage,
        amount: float,
        working_balances: dict
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Select the best account to pay a mortgage from.

        Priority:
        1. Preferred account (if has funds)
        2. Checking accounts with sufficient funds
        """
        if mortgage.preferred_source_bank and mortgage.preferred_source_account:
            key = f"{mortgage.preferred_source_bank}:{mortgage.preferred_source_account}"
            if key in working_balances and working_balances[key] >= amount:
                return mortgage.preferred_source_bank, mortgage.preferred_source_account

        for bank in self.banks:
            for name, account in bank.accounts.items():
                if account.account_type.value == "checking":
                    key = f"{bank.name}:{name}"
                    balance = working_balances.get(key, account.balance)
                    if balance >= amount:
                        return bank.name, name

        for bank in self.banks:
            for name, account in bank.accounts.items():
                key = f"{bank.name}:{name}"
                balance = working_balances.get(key, account.balance)
                if balance >= amount:
                    return bank.name, name

        return None, None

    def _select_credit_payment_account(
        self,
        credit_info: dict,
        amount: float,
        working_balances: dict
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Select the best account to pay a credit card payment from.

        Priority:
        1. Checking accounts with sufficient funds (highest balance first)
        2. Any account with sufficient funds
        """
        # Prefer checking accounts with sufficient funds
        for bank in self.banks:
            for name, account in bank.accounts.items():
                if account.account_type.value == "checking":
                    key = f"{bank.name}:{name}"
                    balance = working_balances.get(key, account.balance)
                    if balance >= amount:
                        return bank.name, name

        # Fall back to any account
        for bank in self.banks:
            for name, account in bank.accounts.items():
                key = f"{bank.name}:{name}"
                balance = working_balances.get(key, account.balance)
                if balance >= amount:
                    return bank.name, name

        return None, None

    def _determine_payment_date(
        self,
        due_date: date,
        income_dates: list[date],
        optimization_goal: str
    ) -> date:
        """
        Determine the optimal payment date for a bill.

        - For maximize_discretionary: Pay on due date to maximize float
        - For minimize_interest: Pay as early as possible after income
        - For payoff_credit_account: Pay on due date to free up cash for credit
        """
        if optimization_goal == "minimize_interest":
            for income_date in income_dates:
                if income_date <= due_date:
                    return max(income_date, due_date - timedelta(days=3))
            return due_date
        else:
            return due_date

    def _select_payment_account_smart(
        self,
        bill: Bill,
        amount: float,
        working_balances: dict,
        optimization_goal: str
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Select the best account to pay a bill from using smart selection.

        Priority:
        1. Preferred account (if has funds)
        2. Checking accounts with sufficient funds (ordered by balance, lowest first)
        3. Savings accounts with sufficient funds (last resort)
        4. If no account has sufficient funds, return account with highest balance
        """
        candidates = []
        all_accounts = []

        if bill.preferred_source_bank and bill.preferred_source_account:
            key = f"{bill.preferred_source_bank}:{bill.preferred_source_account}"
            if key in working_balances and working_balances[key] >= amount:
                return bill.preferred_source_bank, bill.preferred_source_account

        for bank in self.banks:
            for name, account in bank.accounts.items():
                key = f"{bank.name}:{name}"
                balance = working_balances.get(key, account.balance)

                account_info = {
                    'bank': bank.name,
                    'account': name,
                    'balance': balance,
                    'type': account.account_type.value,
                    'interest_rate': account.interest_rate
                }

                all_accounts.append(account_info)

                if balance >= amount:
                    candidates.append(account_info)

        if candidates:
            def sort_key(c):
                type_priority = 0 if c['type'] == 'checking' else 1
                balance_priority = c['balance']
                return (type_priority, balance_priority)

            candidates.sort(key=sort_key)
            best = candidates[0]
            return best['bank'], best['account']

        # No account has sufficient funds - return the one with highest balance
        if all_accounts:
            all_accounts.sort(key=lambda c: (-1 if c['type'] == 'checking' else 0, -c['balance']))
            best = all_accounts[0]
            return best['bank'], best['account']

        return None, None

    # ─────────────────────────────────────────────────────────────────────
    #  CREDIT PAYOFF PLANNING
    # ─────────────────────────────────────────────────────────────────────

    def _calculate_extra_credit_payments(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        target_credit_account: str,
        strategy: dict,
        promo_payoff_schedule: list[dict] = None,
        credit_schedule: list[dict] = None,
        mortgage_schedule: list[dict] = None,
    ) -> list[dict]:
        """
        Calculate extra payments that can be made to the target credit account
        after all mandatory bills, credit card minimums, and promo payoffs are paid.
        """
        extra_payments = []
        safety_buffer = 500.0
        promo_payoff_schedule = promo_payoff_schedule or []
        credit_schedule = credit_schedule or []
        mortgage_schedule = mortgage_schedule or []

        target_credit = None
        target_bank_name = None
        for bank in self.banks:
            for name, credit in bank.credit_accounts.items():
                if name == target_credit_account:
                    target_credit = credit
                    target_bank_name = bank.name
                    break
            if target_credit:
                break

        if not target_credit:
            return []

        running_balance = sum(
            account.balance
            for bank in self.banks
            for account in bank.accounts.values()
        )

        remaining_credit_balance = target_credit.balance

        for promo_payment in promo_payoff_schedule:
            if promo_payment['credit_account'] == target_credit_account:
                remaining_credit_balance -= promo_payment['amount']

        for i, income_date in enumerate(income_dates):
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )

            running_balance += income_amount

            next_income = income_dates[i + 1] if i + 1 < len(income_dates) else end_date + timedelta(days=1)

            bills_in_period = sum(
                b['amount'] for b in bill_schedule
                if income_date <= b['due_date'] < next_income
            )

            running_balance -= bills_in_period

            # Subtract credit card minimum payments due in this period
            credit_payments_in_period = sum(
                c['minimum_payment'] for c in credit_schedule
                if income_date <= c['due_date'] < next_income
            )

            running_balance -= credit_payments_in_period

            # Subtract mortgage payments due in this period
            running_balance -= sum(
                m['total_payment'] for m in mortgage_schedule
                if income_date <= m['due_date'] < next_income
            )

            promos_in_period = sum(
                p['amount'] for p in promo_payoff_schedule
                if income_date <= p['date'] < next_income
            )

            running_balance -= promos_in_period

            excess = running_balance - safety_buffer

            if excess > 0 and remaining_credit_balance > 0:
                payment_amount = min(excess, remaining_credit_balance)
                payment_amount = (payment_amount // 50) * 50

                if payment_amount >= 50:
                    payment_date = income_date + timedelta(days=2)
                    if payment_date > end_date:
                        payment_date = end_date

                    extra_payments.append({
                        'credit_account': target_credit_account,
                        'bank': target_bank_name,
                        'amount': payment_amount,
                        'date': payment_date,
                        'description': f"Extra payment to {target_credit_account}"
                    })

                    running_balance -= payment_amount
                    remaining_credit_balance -= payment_amount

        return extra_payments

    # ─────────────────────────────────────────────────────────────────────
    #  CONSTRAINT VALIDATION
    # ─────────────────────────────────────────────────────────────────────

    def _check_constraints(self, simulation_result: dict, bill_schedule: list[dict], mortgage_schedule: list[dict] = None) -> list[str]:
        """
        Check for constraint violations in the simulation.
        """
        violations = []
        mortgage_schedule = mortgage_schedule or []

        # Check for negative balances at any point
        for snapshot in simulation_result.get('snapshots', []):
            for account_name, balance in snapshot.get('balances', {}).items():
                if balance < -0.01:
                    violations.append(
                        f"Account {account_name} would overdraft on {snapshot['date']}: ${balance:.2f}"
                    )

        # Check for deferred/unpaid bills of every payment type
        deferred_labels = {
            "BILL_DEFERRED": "Bill could not be paid",
            "CREDIT_PAYMENT_DEFERRED": "Credit card payment could not be paid",
            "MORTGAGE_DEFERRED": "Mortgage payment could not be paid",
            "HELOC_PAYMENT_DEFERRED": "HELOC payment could not be paid",
            "BILL_GROUP_DEFERRED": "Bill group payment could not be paid",
        }
        for cf_item in simulation_result["cash_flow"]:
            label = deferred_labels.get(cf_item.get("type"))
            if label:
                violations.append(f"{label}: {cf_item['description']} on {cf_item['date']}")

        # Check that all bills have a payment strategy.
        # Include all payment types — linked bills produce CREDIT_PAYMENT,
        # MORTGAGE_PAYMENT, HELOC_PAYMENT, or BILL_GROUP_PAYMENT cash-flow
        # entries instead of plain BILL_PAYMENT.  Deferred entries also count
        # (they are already reported separately above).
        paid_types = {
            "BILL_PAYMENT", "BILL_DEFERRED",
            "CREDIT_PAYMENT", "CREDIT_PAYMENT_DEFERRED",
            "MORTGAGE_PAYMENT", "MORTGAGE_DEFERRED",
            "HELOC_PAYMENT", "HELOC_PAYMENT_DEFERRED",
            "BILL_GROUP_PAYMENT", "BILL_GROUP_DEFERRED",
        }
        paid_bills = set()
        for cf_item in simulation_result["cash_flow"]:
            if cf_item.get("type") in paid_types:
                paid_bills.add(cf_item.get("description", ""))

        # Also exclude bills that are already covered by the dedicated
        # mortgage / credit schedule checks below.
        mortgage_bill_names = {m.get('mortgage_name', '') for m in (mortgage_schedule or [])}
        credit_bill_names: set[str] = set()
        for cf_item in simulation_result["cash_flow"]:
            if cf_item.get("type") in ("CREDIT_PAYMENT", "CREDIT_PAYMENT_DEFERRED"):
                credit_bill_names.add(cf_item.get("description", ""))

        for bill_info in bill_schedule:
            name = bill_info['bill_name']
            # Skip bills already tracked by specialised sections
            if name in paid_bills:
                continue
            # Group payments are logged under the group name and their
            # deferrals are reported above
            if bill_info.get('is_group'):
                continue
            # Skip bills whose linked account is handled by the mortgage
            # or credit card specific checks that follow.
            bill_obj = bill_info.get('bill')
            if bill_obj and hasattr(bill_obj, 'linked_account_type'):
                if bill_obj.linked_account_type in ('mortgage', 'credit', 'heloc'):
                    continue
            violations.append(f"No payment scheduled for: {name} due {bill_info['due_date']}")

        # Check mortgage payments
        if mortgage_schedule:
            # A mortgage counts as handled if a payment (or a deferral, which is
            # reported above) was recorded for it. Match on the account name
            # (mortgage_name) and on the linked bill name (description).
            paid_mortgages = set()
            for cf_item in simulation_result["cash_flow"]:
                if cf_item.get("type") in ("MORTGAGE_PAYMENT", "MORTGAGE_DEFERRED"):
                    if cf_item.get("mortgage_name"):
                        paid_mortgages.add(cf_item["mortgage_name"])
                    paid_mortgages.add(cf_item.get("description", ""))

            for mortgage_info in mortgage_schedule:
                mortgage_name = mortgage_info.get('mortgage_name', mortgage_info.get('account_name', ''))
                due_date = mortgage_info.get('due_date')
                total_payment = mortgage_info.get('total_payment', 0)

                bill_name = mortgage_info.get('bill_name')
                if (mortgage_name and mortgage_name not in paid_mortgages
                        and (not bill_name or bill_name not in paid_mortgages)):
                    violations.append(
                        f"Mortgage payment not scheduled: {mortgage_name} "
                        f"(${total_payment:,.2f} due {due_date})"
                    )

                for snapshot in simulation_result.get('snapshots', []):
                    if snapshot['date'] == due_date:
                        source_bank = mortgage_info.get('source_bank')
                        source_account = mortgage_info.get('source_account')

                        if source_bank and source_account:
                            account_key = f"{source_bank}:{source_account}"
                            balance = snapshot.get('balances', {}).get(account_key, 0)

                            if balance < total_payment:
                                shortfall = total_payment - balance
                                violations.append(
                                    f"Insufficient funds for {mortgage_name} on {due_date}: "
                                    f"need ${total_payment:,.2f}, have ${balance:,.2f} "
                                    f"(shortfall: ${shortfall:,.2f})"
                                )
                        break

        # Check for low balance warnings — only for accounts that had money
        # withdrawn from them.  Accounts that start below the threshold and
        # have no outflows are not flagged (they aren't "dropping" to a low
        # balance, they were already there).
        low_balance_threshold = 100.0

        # Determine which accounts actually had outflows during the period
        accounts_with_outflows: set[str] = set()
        outflow_types = {
            "BILL_PAYMENT", "BILL_DEFERRED", "MORTGAGE_PAYMENT",
            "MORTGAGE_DEFERRED", "CREDIT_PAYMENT", "CREDIT_PAYMENT_DEFERRED",
            "HELOC_PAYMENT", "HELOC_PAYMENT_DEFERRED",
            "BILL_GROUP_PAYMENT", "BILL_GROUP_DEFERRED",
        }
        for cf_item in simulation_result.get("cash_flow", []):
            if cf_item.get("type") in outflow_types:
                bank_name = cf_item.get("bank", "")
                account_name_cf = cf_item.get("account", "")
                if bank_name and account_name_cf:
                    accounts_with_outflows.add(f"{bank_name}:{account_name_cf}")

        # Record starting balances from the first snapshot
        starting_balances: dict[str, float] = {}
        snapshots = simulation_result.get('snapshots', [])
        if snapshots:
            for acct, bal in snapshots[0].get('balances', {}).items():
                starting_balances[acct] = bal

        warned_accounts: set[str] = set()
        for snapshot in snapshots:
            for account_name, balance in snapshot.get('balances', {}).items():
                if account_name in warned_accounts:
                    continue  # Already warned once for this account
                if 0 <= balance < low_balance_threshold:
                    # Only warn if this account had outflows AND it wasn't
                    # already below the threshold at the start
                    was_above_threshold = starting_balances.get(account_name, 0) >= low_balance_threshold
                    had_outflows = account_name in accounts_with_outflows
                    if had_outflows and was_above_threshold:
                        violations.append(
                            f"Low balance warning: {account_name} drops to "
                            f"${balance:.2f} on {snapshot['date']}"
                        )
                        warned_accounts.add(account_name)

        return violations

    # ─────────────────────────────────────────────────────────────────────
    #  MULTI-STRATEGY COMPARISON
    # ─────────────────────────────────────────────────────────────────────

    def generate_multiple_strategies(
        self,
        start_date: date,
        end_date: date,
        num_strategies: int = 3,
        target_credit_account: str = None
    ) -> list[PaymentPlan]:
        """
        Generate multiple payment strategies with different optimization goals.
        Allows comparison of trade-offs.
        """
        strategies = []

        if not self.banks:
            return []

        has_accounts = any(
            len(bank.accounts) > 0 for bank in self.banks
        )
        if not has_accounts:
            return []

        goals = ["maximize_discretionary", "minimize_interest"]

        if target_credit_account:
            target_exists = any(
                target_credit_account in bank.credit_accounts
                for bank in self.banks
            )
            if target_exists:
                goals.append("payoff_credit_account")

        for goal in goals[:num_strategies]:
            try:
                if goal == "payoff_credit_account":
                    plan = self.optimize_payment_schedule(
                        start_date, end_date, goal, target_credit_account
                    )
                else:
                    plan = self.optimize_payment_schedule(start_date, end_date, goal)
                strategies.append(plan)
            except Exception as e:
                import sys
                print(f"Warning: Strategy '{goal}' failed: {e}", file=sys.stderr)
                continue

        return sorted(strategies, key=lambda p: p.final_discretionary, reverse=True)

    def get_credit_payoff_plan(
        self,
        target_credit_account: str,
        months: int = 12,
        start_date: date = None
    ) -> PaymentPlan:
        """
        Generate a plan specifically focused on paying off a credit account.
        """
        start_date = start_date or date.today()
        end_date = start_date + timedelta(days=30 * months)

        return self.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="payoff_credit_account",
            target_credit_account=target_credit_account
        )

    # ─────────────────────────────────────────────────────────────────────
    #  SAVINGS OPTIMIZATION
    # ─────────────────────────────────────────────────────────────────────

    def _calculate_savings_transfers(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        mortgage_schedule: list[dict],
        promo_payoff_schedule: list[dict],
        extra_credit_payments: list[dict],
        credit_schedule: list[dict] = None
    ) -> tuple[list[SavingsTransfer], float]:
        """
        Calculate optimal transfers between checking and savings accounts to maximize interest.

        Strategy:
        1. After income arrives and bills are accounted for, identify excess funds in checking
        2. Transfer excess to savings accounts with higher APY (within same bank)
        3. Before bills are due, transfer back from savings to checking as needed
        4. Prioritize high-yield savings accounts
        """
        transfers = []
        total_estimated_interest = 0.0

        checking_buffer = 500.0
        min_transfer_amount = 100.0

        # Find all checking/savings pairs within each bank
        bank_account_pairs = []
        for bank in self.banks:
            checking_accounts = []
            savings_accounts = []

            for name, account in bank.accounts.items():
                if account.account_type.value == "checking":
                    checking_accounts.append({
                        'name': name,
                        'account': account,
                        'balance': account.balance,
                        'apy': account.interest_rate
                    })
                elif account.account_type.value == "savings":
                    savings_accounts.append({
                        'name': name,
                        'account': account,
                        'balance': account.balance,
                        'apy': account.interest_rate
                    })

            savings_accounts.sort(key=lambda x: x['apy'], reverse=True)

            if checking_accounts and savings_accounts:
                bank_account_pairs.append({
                    'bank': bank,
                    'bank_name': bank.name,
                    'checking': checking_accounts,
                    'savings': savings_accounts
                })

        if not bank_account_pairs:
            return [], 0.0

        # Build a timeline of cash needs
        cash_events = []

        for income_date in income_dates:
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )
            if income_amount > 0:
                cash_events.append({
                    'date': income_date,
                    'type': 'income',
                    'amount': income_amount
                })

        for bill in bill_schedule:
            cash_events.append({
                'date': bill['due_date'],
                'type': 'bill',
                'amount': -bill['amount']
            })

        for mortgage in mortgage_schedule:
            cash_events.append({
                'date': mortgage['due_date'],
                'type': 'mortgage',
                'amount': -mortgage['total_payment']
            })

        for promo in promo_payoff_schedule:
            cash_events.append({
                'date': promo['date'],
                'type': 'promo_payment',
                'amount': -promo['amount']
            })

        for payment in extra_credit_payments:
            cash_events.append({
                'date': payment['date'],
                'type': 'credit_payment',
                'amount': -payment['amount']
            })

        # Add credit card minimum payments
        for credit_pay in (credit_schedule or []):
            cash_events.append({
                'date': credit_pay['due_date'],
                'type': 'credit_minimum',
                'amount': -credit_pay['minimum_payment']
            })

        cash_events.sort(key=lambda x: x['date'])

        # Process each bank's accounts
        for pair in bank_account_pairs:
            bank_name = pair['bank_name']
            primary_checking = pair['checking'][0]
            best_savings = pair['savings'][0]

            # Skip if savings APY is negligible (less than 0.1%)
            if best_savings['apy'] < 0.1:
                continue

            checking_balance = primary_checking['balance']
            savings_balance = best_savings['balance']

            pending_return_from_savings = 0.0

            for i, event in enumerate(cash_events):
                event_date = event['date']

                if event_date < start_date or event_date > end_date:
                    continue

                if event['type'] == 'income':
                    checking_balance += event['amount']
                else:
                    checking_balance += event['amount']

                if event['type'] == 'income':
                    next_income_idx = None
                    for j in range(i + 1, len(cash_events)):
                        if cash_events[j]['type'] == 'income':
                            next_income_idx = j
                            break

                    outflows_before_next_income = 0.0
                    if next_income_idx:
                        for j in range(i + 1, next_income_idx):
                            if cash_events[j]['amount'] < 0:
                                outflows_before_next_income += abs(cash_events[j]['amount'])
                    else:
                        for j in range(i + 1, len(cash_events)):
                            if cash_events[j]['amount'] < 0:
                                outflows_before_next_income += abs(cash_events[j]['amount'])

                    required_in_checking = outflows_before_next_income + checking_buffer
                    excess = checking_balance - required_in_checking

                    if excess >= min_transfer_amount:
                        transfer_amount = (excess // 100) * 100

                        if transfer_amount >= min_transfer_amount:
                            if next_income_idx:
                                days_in_savings = (cash_events[next_income_idx]['date'] - event_date).days
                            else:
                                days_in_savings = (end_date - event_date).days

                            daily_rate = best_savings['apy'] / 100 / 365
                            interest_earned = transfer_amount * daily_rate * days_in_savings

                            transfers.append(SavingsTransfer(
                                from_bank=bank_name,
                                from_account=primary_checking['name'],
                                to_bank=bank_name,
                                to_account=best_savings['name'],
                                amount=transfer_amount,
                                transfer_date=event_date + timedelta(days=1),
                                reason='maximize_interest',
                                estimated_interest_gain=interest_earned
                            ))

                            checking_balance -= transfer_amount
                            savings_balance += transfer_amount
                            pending_return_from_savings += transfer_amount
                            total_estimated_interest += interest_earned

                if event['amount'] < 0:
                    shortfall = checking_buffer - checking_balance

                    if shortfall > 0 and pending_return_from_savings > 0:
                        return_amount = min(shortfall + checking_buffer, pending_return_from_savings, savings_balance)

                        if return_amount >= min_transfer_amount:
                            return_amount = (return_amount // 100) * 100

                            transfers.append(SavingsTransfer(
                                from_bank=bank_name,
                                from_account=best_savings['name'],
                                to_bank=bank_name,
                                to_account=primary_checking['name'],
                                amount=return_amount,
                                transfer_date=event_date - timedelta(days=1),
                                reason='fund_upcoming_bills',
                                estimated_interest_gain=0.0
                            ))

                            savings_balance -= return_amount
                            checking_balance += return_amount
                            pending_return_from_savings -= return_amount

        # Sort transfers by date
        transfers.sort(key=lambda x: x.transfer_date)

        # Consolidate transfers on the same date between the same accounts
        consolidated = []
        for transfer in transfers:
            merged = False
            for existing in consolidated:
                if (existing.transfer_date == transfer.transfer_date and
                    existing.from_bank == transfer.from_bank and
                    existing.from_account == transfer.from_account and
                    existing.to_account == transfer.to_account and
                    existing.reason == transfer.reason):
                    existing.amount += transfer.amount
                    existing.estimated_interest_gain += transfer.estimated_interest_gain
                    merged = True
                    break

            if not merged:
                consolidated.append(transfer)

        return consolidated, total_estimated_interest

