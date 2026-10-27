from datetime import date, timedelta
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer


class FinancialReport:
    """Generates comprehensive financial reports and projections."""

    # Cash-flow entry types that move money out of bank accounts to pay
    # obligations (deferred entries are excluded — no money moved).
    PAYMENT_TYPES = {
        "BILL_PAYMENT": "bills",
        "CREDIT_PAYMENT": "credit_payments",
        "MORTGAGE_PAYMENT": "mortgage_payments",
        "HELOC_PAYMENT": "heloc_payments",
        "BILL_GROUP_PAYMENT": "group_payments",
    }
    DEFERRED_TYPES = {
        "BILL_DEFERRED", "CREDIT_PAYMENT_DEFERRED", "MORTGAGE_DEFERRED",
        "HELOC_PAYMENT_DEFERRED", "BILL_GROUP_DEFERRED",
    }

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill],
                 bill_groups: list = None):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills
        self.bill_groups = bill_groups or []

    def _copy_state(self):
        """
        Deep-copy banks, income, bills and bill groups in ONE call so linked
        bills (AccountLinkedBill / GroupLinkedBill) keep pointing at the copied
        accounts/groups instead of the real ones.
        """
        return deepcopy((self.banks, self.income_sources, self.bills, self.bill_groups))

    def _new_simulator(self) -> TimelineSimulator:
        """TimelineSimulator over an isolated copy of the current state."""
        banks, income, bills, groups = self._copy_state()
        return TimelineSimulator(banks, income, bills, groups)

    def _interest_is_charged(self, cf_item: dict) -> bool:
        """True for interest charged on debt (credit/HELOC), False for interest earned."""
        kind = cf_item.get("account_kind")
        if kind is not None:
            return kind in ("credit", "heloc")
        acct = cf_item.get("account", "")
        bank_name = cf_item.get("bank")
        for bank in self.banks:
            if bank_name and bank.name != bank_name:
                continue
            if acct in bank.accounts:
                return False
            if acct in bank.credit_accounts or acct in bank.heloc_accounts:
                return True
        return False

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
    ) -> dict:
        """
        Generate a detailed projection report for a date range.

        Args:
            start_date: Projection start date
            end_date: Projection end date
            include_optimization: Whether to include optimized payment plan

        Returns:
            Dictionary with 'text' (formatted report string) and 'result' (raw simulation data)
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"PROJECTION REPORT: {start_date} to {end_date}")
        lines.append("=" * 80)

        # Simulate with current defaults
        simulator = self._new_simulator()

        result = simulator.project_balances(start_date, end_date)

        # ── Starting Balances ──
        lines.append("\n" + "─" * 80)
        lines.append("STARTING BALANCES:")
        lines.append("─" * 80)

        if result["snapshots"]:
            first_snap = result["snapshots"][0]
            for account_name, balance in sorted(first_snap["balances"].items()):
                lines.append(f"  💰 {account_name}: ${balance:,.2f}")
            for account_name, balance in sorted(first_snap.get("credit_balances", {}).items()):
                if balance > 0:
                    lines.append(f"  💳 {account_name}: ${balance:,.2f} owed")
            for account_name, balance in sorted(first_snap.get("mortgage_balances", {}).items()):
                if balance > 0:
                    lines.append(f"  🏠 {account_name}: ${balance:,.2f} remaining")

        # ── Monthly Cash Flow Summaries ──
        lines.append("\n" + "=" * 80)
        lines.append("MONTHLY CASH FLOW SUMMARIES:")
        lines.append("=" * 80)

        # Group cash flow by year-month
        monthly_data = {}
        for cf_item in result["cash_flow"]:
            cf_date = cf_item["date"]
            ym_key = (cf_date.year, cf_date.month)
            if ym_key not in monthly_data:
                monthly_data[ym_key] = {
                    "income": 0.0,
                    "bills": 0.0,
                    "credit_payments": 0.0,
                    "mortgage_payments": 0.0,
                    "heloc_payments": 0.0,
                    "group_payments": 0.0,
                    "extra_payments": 0.0,
                    "interest_earned": 0.0,
                    "interest_charged": 0.0,
                    "deferred": [],
                }
            md = monthly_data[ym_key]
            cf_type = cf_item["type"]
            amount = cf_item["amount"]

            if cf_type == "INCOME":
                md["income"] += amount
            elif cf_type in self.PAYMENT_TYPES:
                md[self.PAYMENT_TYPES[cf_type]] += abs(amount)
            elif cf_type in ("EXTRA_CREDIT_PAYMENT", "PROMO_PAYOFF"):
                md["extra_payments"] += abs(amount)
            elif cf_type == "INTEREST":
                if amount > 0:
                    # Earned on bank accounts vs. charged on credit/HELOC debt.
                    # Charged interest increases debt; it is not a cash outflow.
                    if self._interest_is_charged(cf_item):
                        md["interest_charged"] += amount
                    else:
                        md["interest_earned"] += amount
            elif cf_type in self.DEFERRED_TYPES:
                md["deferred"].append(cf_item)

        # Find end-of-month snapshots for balance display
        month_end_snapshots = {}
        for snapshot in result["snapshots"]:
            snap_date = snapshot["date"]
            ym_key = (snap_date.year, snap_date.month)
            month_end_snapshots[ym_key] = snapshot  # Last snapshot of each month wins

        # Print monthly summaries
        import calendar
        for ym_key in sorted(monthly_data.keys()):
            year, month = ym_key
            month_name = calendar.month_name[month]
            md = monthly_data[ym_key]

            # Cash outflows only — interest charged on debt is shown separately
            # (it is paid through the credit/HELOC payments above).
            total_outflows = (md["bills"] + md["credit_payments"] + md["mortgage_payments"]
                              + md["heloc_payments"] + md["group_payments"] + md["extra_payments"])
            net = md["income"] + md["interest_earned"] - total_outflows

            lines.append(f"\n{'─' * 80}")
            lines.append(f"  📅 {month_name} {year}")
            lines.append(f"{'─' * 80}")
            lines.append(f"    💵 Income:              ${md['income']:>12,.2f}")
            if md["interest_earned"] > 0:
                lines.append(f"    🏦 Interest Earned:     ${md['interest_earned']:>12,.2f}")
            lines.append(f"    📄 Bills:              -${md['bills']:>12,.2f}")
            if md["credit_payments"] > 0:
                lines.append(f"    💳 Credit Payments:    -${md['credit_payments']:>12,.2f}")
            if md["mortgage_payments"] > 0:
                lines.append(f"    🏠 Mortgage Payments:  -${md['mortgage_payments']:>12,.2f}")
            if md["heloc_payments"] > 0:
                lines.append(f"    🏦 HELOC Payments:     -${md['heloc_payments']:>12,.2f}")
            if md["group_payments"] > 0:
                lines.append(f"    📦 Group Payments:     -${md['group_payments']:>12,.2f}")
            if md["extra_payments"] > 0:
                lines.append(f"    🎯 Extra Payments:     -${md['extra_payments']:>12,.2f}")
            if md["interest_charged"] > 0:
                lines.append(f"    ⚠️  Interest Charged:   ${md['interest_charged']:>12,.2f} (added to debt)")

            if net >= 0:
                lines.append(f"    {'─' * 40}")
                lines.append(f"    ✅ Net Cash Flow:       ${net:>12,.2f}")
            else:
                lines.append(f"    {'─' * 40}")
                lines.append(f"    🔴 Net Cash Flow:      -${abs(net):>12,.2f}")

            # Show deferred/failed payments
            if md["deferred"]:
                lines.append(f"    ⚠️  Deferred Payments:")
                for d in md["deferred"]:
                    lines.append(f"       - {d['description']}: ${abs(d['amount']):,.2f}")

            # Show end-of-month balances
            snap = month_end_snapshots.get(ym_key)
            if snap:
                lines.append(f"    ── End of Month Balances ──")
                for acct_name, bal in sorted(snap["balances"].items()):
                    lines.append(f"      💰 {acct_name}: ${bal:,.2f}")
                for acct_name, bal in sorted(snap.get("credit_balances", {}).items()):
                    if bal > 0:
                        lines.append(f"      💳 {acct_name}: ${bal:,.2f} owed")
                    else:
                        lines.append(f"      💳 {acct_name}: ✅ PAID OFF")
                for acct_name, bal in sorted(snap.get("mortgage_balances", {}).items()):
                    if bal > 0:
                        lines.append(f"      🏠 {acct_name}: ${bal:,.2f} remaining")

        # ── Overall Summary ──
        lines.append("\n" + "=" * 80)
        lines.append("OVERALL SUMMARY:")
        lines.append("=" * 80)

        total_income = sum(md["income"] for md in monthly_data.values())
        total_interest_earned = sum(md["interest_earned"] for md in monthly_data.values())
        total_bills = sum(md["bills"] for md in monthly_data.values())
        total_credit_pmts = sum(md["credit_payments"] for md in monthly_data.values())
        total_mortgage_pmts = sum(md["mortgage_payments"] for md in monthly_data.values())
        total_heloc_pmts = sum(md["heloc_payments"] for md in monthly_data.values())
        total_group_pmts = sum(md["group_payments"] for md in monthly_data.values())
        total_extra_pmts = sum(md["extra_payments"] for md in monthly_data.values())
        total_interest_charged = sum(md["interest_charged"] for md in monthly_data.values())
        total_outflows = (total_bills + total_credit_pmts + total_mortgage_pmts
                          + total_heloc_pmts + total_group_pmts + total_extra_pmts)
        net_total = total_income + total_interest_earned - total_outflows

        lines.append(f"  Total Income:            ${total_income:>14,.2f}")
        if total_interest_earned > 0:
            lines.append(f"  Total Interest Earned:   ${total_interest_earned:>14,.2f}")
        lines.append(f"  Total Bills:            -${total_bills:>14,.2f}")
        if total_credit_pmts > 0:
            lines.append(f"  Total Credit Payments:  -${total_credit_pmts:>14,.2f}")
        if total_mortgage_pmts > 0:
            lines.append(f"  Total Mortgage Payments:-${total_mortgage_pmts:>14,.2f}")
        if total_heloc_pmts > 0:
            lines.append(f"  Total HELOC Payments:   -${total_heloc_pmts:>14,.2f}")
        if total_group_pmts > 0:
            lines.append(f"  Total Group Payments:   -${total_group_pmts:>14,.2f}")
        if total_extra_pmts > 0:
            lines.append(f"  Total Extra Payments:   -${total_extra_pmts:>14,.2f}")
        if total_interest_charged > 0:
            lines.append(f"  Total Interest Charged:  ${total_interest_charged:>14,.2f} (added to debt)")
        lines.append(f"  {'─' * 40}")
        if net_total >= 0:
            lines.append(f"  ✅ Net Change:           ${net_total:>14,.2f}")
        else:
            lines.append(f"  🔴 Net Change:          -${abs(net_total):>14,.2f}")

        # ── Final Balances ──
        lines.append("\n" + "=" * 80)
        lines.append("FINAL ACCOUNT BALANCES:")
        lines.append("=" * 80)

        total_bank = 0
        for account_name, balance in sorted(result["final_balances"].items()):
            lines.append(f"  💰 {account_name}: ${balance:,.2f}")
            total_bank += balance

        total_credit = 0
        for account_name, balance in sorted(result.get("credit_final_balances", {}).items()):
            if balance > 0:
                lines.append(f"  💳 {account_name}: ${balance:,.2f} owed")
            else:
                lines.append(f"  💳 {account_name}: ✅ PAID OFF")
            total_credit += balance

        total_mortgage = 0
        for account_name, balance in sorted(result.get("mortgage_final_balances", {}).items()):
            if balance > 0:
                lines.append(f"  🏠 {account_name}: ${balance:,.2f} remaining")
            else:
                lines.append(f"  🏠 {account_name}: ✅ PAID OFF")
            total_mortgage += balance

        lines.append(f"\n  Total Bank Balance:      ${total_bank:>14,.2f}")
        if total_credit > 0:
            lines.append(f"  Total Credit Owed:      -${total_credit:>14,.2f}")
        if total_mortgage > 0:
            lines.append(f"  Total Mortgage Owed:    -${total_mortgage:>14,.2f}")
        net_worth = total_bank - total_credit - total_mortgage
        lines.append(f"  {'─' * 40}")
        lines.append(f"  Net Worth:               ${net_worth:>14,.2f}")

        # ── Optimization ──
        if include_optimization:
            lines.append("\n" + "=" * 80)
            lines.append("PAYMENT OPTIMIZATION:")
            lines.append("=" * 80)

            banks, income, bills, groups = self._copy_state()
            optimizer = PaymentOptimizer(banks, income, bills, groups)

            optimized_plan = optimizer.optimize_payment_schedule(start_date, end_date)

            lines.append(f"\nStrategy:")
            for bill_name, assignment in optimized_plan.strategy.items():
                lines.append(
                    f"  {bill_name}: Pay from {assignment['bank']}/{assignment['account']}"
                )

            if optimized_plan.violations:
                lines.append("\n⚠️  Issues Detected:")
                for violation in optimized_plan.violations:
                    lines.append(f"  - {violation}")

        report_text = "\n".join(lines)
        return {"text": report_text, "result": result}

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

        simulator = self._new_simulator()

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
            for account_name, balance in sorted(snapshot.get("credit_balances", {}).items()):
                if balance > 0:
                    lines.append(f"    💳 {account_name}: ${balance:,.2f} owed")
            for account_name, balance in sorted(snapshot.get("mortgage_balances", {}).items()):
                if balance > 0:
                    lines.append(f"    🏠 {account_name}: ${balance:,.2f} remaining")

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

        simulator = self._new_simulator()

        result = simulator.project_balances(start_date, end_date)

        # Monthly summaries. Expenses are all payment outflows (stored as
        # negative amounts in the cash flow, so use abs); interest counts only
        # interest EARNED — interest charged on debt is not a cash flow.
        current_month = start_date.month
        month_cf = {"income": 0, "expenses": 0, "interest": 0}
        expense_types = set(self.PAYMENT_TYPES) | {"EXTRA_CREDIT_PAYMENT", "PROMO_PAYOFF"}

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
            elif cf_item["type"] in expense_types:
                month_cf["expenses"] += abs(cf_item["amount"])
            elif cf_item["type"] == "INTEREST" and not self._interest_is_charged(cf_item):
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

