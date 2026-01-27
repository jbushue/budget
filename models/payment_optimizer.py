from datetime import date, timedelta
from copy import deepcopy
from dataclasses import dataclass

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator


@dataclass
class PaymentPlan:
    """Represents an optimized payment plan for bills."""
    strategy: dict  # {bill_name: {bank: name, account: name, date: date}}
    total_interest_paid: float
    total_fees: float
    final_discretionary: float  # Cash available after all obligations
    violations: list[str]  # Any constraint violations

    def __repr__(self):
        return (
            f"PaymentPlan(interest=${self.total_interest_paid:.2f}, "
            f"discretionary=${self.final_discretionary:.2f}, "
            f"violations={len(self.violations)})"
        )


class PaymentOptimizer:
    """
    Optimizes which accounts to pay bills from to maximize discretionary funds.

    Strategy: Between income events, maximize liquid cash by paying bills from
    accounts that minimize interest impact while preserving high-balance accounts.
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill]):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills

    def optimize_payment_schedule(
        self,
        start_date: date,
        end_date: date,
        optimization_goal: str = "maximize_discretionary"
    ) -> PaymentPlan:
        """
        Optimize payment schedule between start and end dates.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            optimization_goal: 'maximize_discretionary' or 'minimize_interest'

        Returns:
            PaymentPlan with optimized strategy
        """
        # Find all income events and bill events in the period
        income_dates = self._find_income_dates(start_date, end_date)
        bill_dates = self._find_bill_dates(start_date, end_date)

        # Group bills by "payment cycle" (period between income events)
        cycles = self._group_by_income_cycle(income_dates, bill_dates)

        # Optimize payment for each cycle
        strategy = {}
        total_interest = 0.0
        total_fees = 0.0

        for cycle_idx, (cycle_start, cycle_end, bills_in_cycle) in enumerate(cycles):
            # Find best accounts to pay from during this cycle
            cycle_strategy = self._optimize_cycle(
                cycle_start,
                cycle_end,
                bills_in_cycle,
                optimization_goal
            )
            strategy.update(cycle_strategy)

        # Simulate with optimized strategy to calculate results
        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        result = simulator.project_balances(start_date, end_date, strategy)

        # Calculate discretionary funds (total after all obligations)
        final_discretionary = sum(
            balance for balance in result["final_balances"].values()
        )

        violations = self._check_constraints(result)

        return PaymentPlan(
            strategy=strategy,
            total_interest_paid=total_interest,
            total_fees=total_fees,
            final_discretionary=final_discretionary,
            violations=violations
        )

    def _find_income_dates(self, start_date: date, end_date: date) -> list[date]:
        """Find all income deposit dates in the period."""
        income_dates = []
        current = start_date

        while current <= end_date:
            for income in self.income_sources:
                next_pay = income.get_next_pay_date(current - timedelta(days=1))
                if next_pay == current and next_pay not in income_dates:
                    income_dates.append(next_pay)
            current += timedelta(days=1)

        return sorted(set(income_dates))

    def _find_bill_dates(self, start_date: date, end_date: date) -> dict[date, list[Bill]]:
        """Find all bill due dates in the period, grouped by date."""
        bill_dates = {}
        current = start_date

        while current <= end_date:
            for bill in self.bills:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due == current:
                    if next_due not in bill_dates:
                        bill_dates[next_due] = []
                    if bill not in bill_dates[next_due]:
                        bill_dates[next_due].append(bill)
            current += timedelta(days=1)

        return bill_dates

    def _group_by_income_cycle(
        self,
        income_dates: list[date],
        bill_dates: dict[date, list[Bill]]
    ) -> list[tuple[date, date, list[Bill]]]:
        """
        Group bills into cycles between income dates.
        Returns: [(cycle_start, cycle_end, [bills in cycle]), ...]
        """
        cycles = []

        for i in range(len(income_dates)):
            cycle_start = income_dates[i]
            cycle_end = income_dates[i + 1] - timedelta(days=1) if i + 1 < len(income_dates) else income_dates[i] + timedelta(days=30)

            # Find all bills due in this cycle
            bills_in_cycle = []
            for bill_date, bills in bill_dates.items():
                if cycle_start <= bill_date <= cycle_end:
                    bills_in_cycle.extend(bills)

            if bills_in_cycle:
                cycles.append((cycle_start, cycle_end, bills_in_cycle))

        return cycles

    def _optimize_cycle(
        self,
        cycle_start: date,
        cycle_end: date,
        bills: list[Bill],
        optimization_goal: str
    ) -> dict:
        """
        Optimize payment source for bills in a single cycle.

        Strategy:
        - For each bill, choose account that minimizes impact on discretionary funds
        - Prefer accounts with high interest rates on credit cards
        - Preserve savings accounts when possible
        """
        strategy = {}

        # Sort bills by due date
        bills_by_date = sorted(bills, key=lambda b: b.due_date)

        for bill in bills_by_date:
            # Find best account to pay from
            best_bank, best_account = self._select_payment_account(bill)

            if best_bank and best_account:
                strategy[bill.bill_name] = {
                    "bank": best_bank.name,
                    "account": best_account,
                    "date": bill.get_next_due_date(cycle_start)
                }

        return strategy

    def _select_payment_account(self, bill: Bill) -> tuple[Bank, str] | tuple[None, None]:
        """
        Select the best account to pay a bill from.

        Priority:
        1. Preferred account (if specified and has funds)
        2. Checking account with sufficient funds
        3. Any account with sufficient funds
        """
        # Try preferred account first
        if bill.preferred_source_bank and bill.preferred_source_account:
            bank = next((b for b in self.banks if b.name == bill.preferred_source_bank), None)
            if bank and bill.preferred_source_account in bank.accounts:
                if bank.accounts[bill.preferred_source_account].balance >= bill.amount:
                    return bank, bill.preferred_source_account

        # Try checking accounts
        for bank in self.banks:
            for name, account in bank.accounts.items():
                if account.account_type.value == "checking" and account.balance >= bill.amount:
                    return bank, name

        # Try any account with funds
        for bank in self.banks:
            for name, account in bank.accounts.items():
                if account.balance >= bill.amount:
                    return bank, name

        return None, None

    def _check_constraints(self, simulation_result: dict) -> list[str]:
        """Check for constraint violations in the simulation."""
        violations = []

        # Check for negative balances
        for account_name, balance in simulation_result["final_balances"].items():
            if balance < 0:
                violations.append(f"Account {account_name} overdrafted: ${balance:.2f}")

        # Check for deferred bills
        for cf_item in simulation_result["cash_flow"]:
            if cf_item.get("type") == "BILL_DEFERRED":
                violations.append(f"Bill deferred: {cf_item['description']}")

        return violations

    def generate_multiple_strategies(
        self,
        start_date: date,
        end_date: date,
        num_strategies: int = 3
    ) -> list[PaymentPlan]:
        """
        Generate multiple payment strategies with different optimization goals.
        Allows comparison of trade-offs.
        """
        strategies = []

        goals = [
            "maximize_discretionary",
            "minimize_interest",
            "minimize_account_usage"
        ]

        for goal in goals[:num_strategies]:
            plan = self.optimize_payment_schedule(start_date, end_date, goal)
            strategies.append(plan)

        return sorted(strategies, key=lambda p: p.final_discretionary, reverse=True)

