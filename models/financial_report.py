from datetime import date, timedelta
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer


class FinancialReport:
    """Generates comprehensive financial reports and projections."""

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill]):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills

    def current_snapshot(self) -> str:
        """Generate a snapshot of current financial state."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"FINANCIAL SNAPSHOT - {date.today()}")
        lines.append("=" * 80)

        # Bank accounts
        lines.append("\nBANK ACCOUNTS:")
        total_bank_balance = 0
        for bank in self.banks:
            lines.append(f"\n  {bank.name}:")
            for account in bank.get_all_accounts():
                lines.append(
                    f"    {account.account_name} ({account.account_type.value}): "
                    f"${account.balance:,.2f}"
                )
                total_bank_balance += account.balance

        lines.append(f"\n  TOTAL BANK BALANCE: ${total_bank_balance:,.2f}")

        # Credit accounts
        lines.append("\n\nCREDIT ACCOUNTS:")
        total_credit_owed = 0
        total_available_credit = 0
        for bank in self.banks:
            if bank.get_all_credit_accounts():
                lines.append(f"\n  {bank.name}:")
                for credit in bank.get_all_credit_accounts():
                    lines.append(
                        f"    {credit.account_name}: "
                        f"Balance owed ${credit.balance:,.2f}, "
                        f"Available credit ${credit.available_credit:,.2f}"
                    )
                    total_credit_owed += credit.balance
                    total_available_credit += credit.available_credit

        lines.append(f"\n  TOTAL OWED: ${total_credit_owed:,.2f}")
        lines.append(f"  TOTAL AVAILABLE CREDIT: ${total_available_credit:,.2f}")

        # Net worth
        net_worth = total_bank_balance - total_credit_owed
        lines.append(f"\n\nNET WORTH: ${net_worth:,.2f}")

        return "\n".join(lines)

    def projection_report(
        self,
        start_date: date,
        end_date: date,
        include_optimization: bool = True
    ) -> str:
        """
        Generate a detailed projection report for a date range.

        Args:
            start_date: Projection start date
            end_date: Projection end date
            include_optimization: Whether to include optimized payment plan
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"PROJECTION REPORT: {start_date} to {end_date}")
        lines.append("=" * 80)

        # Simulate with current defaults
        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        result = simulator.project_balances(start_date, end_date)

        # Timeline summary
        lines.append("\n" + "=" * 80)
        lines.append("TIMELINE EVENTS:")
        lines.append("=" * 80)

        for event in result["events"]:
            lines.append(
                f"{event.event_date}: [{event.event_type}] {event.description} "
                f"(${event.amount:,.2f})"
            )

        # Cash flow summary
        lines.append("\n" + "=" * 80)
        lines.append("CASH FLOW SUMMARY:")
        lines.append("=" * 80)

        income_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "INCOME")
        expense_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "BILL_PAYMENT")
        interest_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "INTEREST")

        lines.append(f"Total Income: ${income_total:,.2f}")
        lines.append(f"Total Expenses: ${-expense_total:,.2f}")
        lines.append(f"Total Interest: ${interest_total:,.2f}")
        lines.append(f"Net Change: ${income_total + expense_total + interest_total:,.2f}")

        # Final balances
        lines.append("\n" + "=" * 80)
        lines.append("FINAL ACCOUNT BALANCES:")
        lines.append("=" * 80)

        total_final = 0
        for account_name, balance in sorted(result["final_balances"].items()):
            lines.append(f"  {account_name}: ${balance:,.2f}")
            total_final += balance

        lines.append(f"\n  TOTAL: ${total_final:,.2f}")

        # Optimization recommendation
        if include_optimization:
            lines.append("\n" + "=" * 80)
            lines.append("PAYMENT OPTIMIZATION:")
            lines.append("=" * 80)

            optimizer = PaymentOptimizer(
                deepcopy(self.banks),
                deepcopy(self.income_sources),
                deepcopy(self.bills)
            )

            optimized_plan = optimizer.optimize_payment_schedule(start_date, end_date)

            lines.append(f"\nOptimized Plan: {optimized_plan}")
            lines.append(f"Strategy:")
            for bill_name, assignment in optimized_plan.strategy.items():
                lines.append(
                    f"  {bill_name}: Pay from {assignment['bank']}/{assignment['account']}"
                )

            if optimized_plan.violations:
                lines.append("\nViolations/Issues:")
                for violation in optimized_plan.violations:
                    lines.append(f"  - {violation}")

        return "\n".join(lines)

    def detailed_timeline(
        self,
        start_date: date,
        end_date: date,
        payment_strategy: dict = None
    ) -> str:
        """Generate a detailed day-by-day timeline."""
        lines = []
        lines.append("=" * 120)
        lines.append(f"DETAILED TIMELINE: {start_date} to {end_date}")
        lines.append("=" * 120)

        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        result = simulator.project_balances(start_date, end_date, payment_strategy)

        # Group cash flow by date
        cf_by_date = {}
        for cf_item in result["cash_flow"]:
            cf_date = cf_item["date"]
            if cf_date not in cf_by_date:
                cf_by_date[cf_date] = []
            cf_by_date[cf_date].append(cf_item)

        # Print day by day
        for snapshot in result["snapshots"]:
            snap_date = snapshot["date"]
            lines.append(f"\n{snap_date.strftime('%A, %B %d, %Y')}:")

            # Show transactions for this date
            if snap_date in cf_by_date:
                for cf in cf_by_date[snap_date]:
                    if cf["amount"] > 0:
                        lines.append(f"  ✓ {cf['description']}: +${cf['amount']:,.2f}")
                    else:
                        lines.append(f"  ✗ {cf['description']}: ${cf['amount']:,.2f}")

            # Show balances
            lines.append("  Balances:")
            for account_name, balance in sorted(snapshot["balances"].items()):
                lines.append(f"    {account_name}: ${balance:,.2f}")

        return "\n".join(lines)

    def budget_analysis(self, months: int = 3) -> str:
        """
        Analyze budget patterns over N months.
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"BUDGET ANALYSIS ({months} MONTHS)")
        lines.append("=" * 80)

        end_date = date.today() + timedelta(days=30 * months)
        start_date = date.today()

        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        result = simulator.project_balances(start_date, end_date)

        # Monthly summaries
        current_month = start_date.month
        month_cf = {"income": 0, "expenses": 0, "interest": 0}

        lines.append(f"\nMonthly Breakdown:")
        for cf_item in result["cash_flow"]:
            cf_month = cf_item["date"].month

            if cf_month != current_month:
                # Print summary for previous month
                net = month_cf["income"] - month_cf["expenses"] + month_cf["interest"]
                lines.append(
                    f"  Month {current_month}: "
                    f"Income: ${month_cf['income']:,.2f}, "
                    f"Expenses: ${month_cf['expenses']:,.2f}, "
                    f"Interest: ${month_cf['interest']:,.2f}, "
                    f"Net: ${net:,.2f}"
                )
                current_month = cf_month
                month_cf = {"income": 0, "expenses": 0, "interest": 0}

            if cf_item["type"] == "INCOME":
                month_cf["income"] += cf_item["amount"]
            elif cf_item["type"] == "BILL_PAYMENT":
                month_cf["expenses"] += cf_item["amount"]
            elif cf_item["type"] == "INTEREST":
                month_cf["interest"] += cf_item["amount"]

        # Print final month
        net = month_cf["income"] - month_cf["expenses"] + month_cf["interest"]
        lines.append(
            f"  Month {current_month}: "
            f"Income: ${month_cf['income']:,.2f}, "
            f"Expenses: ${month_cf['expenses']:,.2f}, "
            f"Interest: ${month_cf['interest']:,.2f}, "
            f"Net: ${net:,.2f}"
        )

        # Low balance warnings
        lines.append(f"\nLow Balance Warnings:")
        low_balances = []
        for snapshot in result["snapshots"]:
            for account_name, balance in snapshot["balances"].items():
                if balance < 0:
                    low_balances.append((snapshot["date"], account_name, balance))

        if low_balances:
            for warn_date, account_name, balance in low_balances:
                lines.append(
                    f"  {warn_date}: {account_name} has negative balance: ${balance:,.2f}"
                )
        else:
            lines.append("  No negative balances detected")

        return "\n".join(lines)

    def payment_schedule(self, months: int = 1) -> str:
        """Generate a simple payment schedule."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"PAYMENT SCHEDULE (Next {months} months)")
        lines.append("=" * 80)

        end_date = date.today() + timedelta(days=30 * months)
        start_date = date.today()

        # Get all upcoming bills
        upcoming_bills = {}
        current = start_date

        while current <= end_date:
            for bill in self.bills:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due == current and next_due not in upcoming_bills:
                    upcoming_bills[next_due] = []
                if next_due == current and bill not in upcoming_bills[next_due]:
                    upcoming_bills[next_due].append(bill)
            current += timedelta(days=1)

        # Print by date
        for bill_date in sorted(upcoming_bills.keys()):
            lines.append(f"\n{bill_date.strftime('%A, %B %d, %Y')}:")
            total_due = 0
            for bill in upcoming_bills[bill_date]:
                lines.append(f"  • {bill.bill_name}: ${bill.amount:,.2f}")
                total_due += bill.amount
            lines.append(f"  TOTAL DUE: ${total_due:,.2f}")

        return "\n".join(lines)

