from datetime import date, timedelta
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import Bill, AccountLinkedBill, GroupLinkedBill
from models.bill_group import BillGroup
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer, PaymentPlan
from models.financial_report import FinancialReport
from models.types import BillType


class FinanceManager:
    """
    Central orchestrator for personal finance management.

    Capabilities:
    - Project account balances on any date considering income and bills
    - Optimize payment strategies to maximize discretionary funds
    - Generate financial reports and forecasts
    - Model multiple banks with various account types
    - Track bills and income with flexible routing
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill], bill_groups: list[BillGroup] = None):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills
        self.bill_groups: list[BillGroup] = bill_groups or []

        # Auto-create linked bills for any accounts that don't already have one
        self._ensure_linked_bills()

        self.timeline_simulator = TimelineSimulator(banks, income_sources, bills, self.bill_groups)
        self.payment_optimizer = PaymentOptimizer(banks, income_sources, bills, self.bill_groups)
        self.financial_reporter = FinancialReport(banks, income_sources, bills, self.bill_groups)

        # Global optimization strategy — applied everywhere
        self.optimization_goal: str = "maximize_discretionary"
        self.target_credit_account: str | None = None
        self.min_hold_days: int = 7  # Min days money stays parked before sweeping
        self._cached_plan: PaymentPlan | None = None
        self._cached_plan_end: date | None = None

        # Deletions are only synced to the DB once we know the in-memory state
        # reflects it (i.e. after a successful load). Prevents a failed load
        # from wiping the database on the next save.
        self._db_sync_deletions = False

        # Planning settings (see apply_settings / models/app_settings.py).
        # Defaults keep the plain library behaviour: no everyday spending, no fees.
        self.cushion: float = 0.0
        self.everyday_spending: dict | None = None  # {"amount": per day, "bank", "account", "weekly", "mode"}
        self.fees: dict = {}

    # ========== Planning settings ==========

    def record_bill_paid(self, bill, amount: float = None, payment_date: date = None,
                         source_bank: str = "", source_account: str = "") -> None:
        """
        Mark a bill paid WITHOUT moving any money — for payments that already
        happened in real life (your balances already reflect them, e.g. via
        SimpleFIN sync or a transaction match). Card/loan balances are left alone.
        """
        from models.fixed_bill import Bill as _Bill, FloatingBill as _Floating
        payment_date = payment_date or date.today()
        if amount is None:
            amount = bill.effective_amount
        if isinstance(bill, _Floating):
            bill.mark_paid(source_bank, source_account, amount, payment_date)
        else:
            _Bill.mark_paid(bill, source_bank, source_account, amount, payment_date)
        if isinstance(bill, GroupLinkedBill):
            bill.linked_group.mark_paid(payment_date)

    def sim_options(self) -> dict:
        """Keyword arguments every TimelineSimulator/PaymentOptimizer should get."""
        return {"daily_spending": self.everyday_spending, "fees": self.fees}

    def apply_settings(self, settings: dict) -> None:
        """Load planning settings (cushion, everyday spending, fees) into the manager."""
        self.cushion = max(0.0, float(settings.get("cushion", 0.0)))
        self.fees = {k: float(settings.get(k, 0.0)) for k in ("card_late_fee", "default_late_fee", "overdraft_fee")}

        weekly = float(settings.get("everyday_weekly", 0.0))
        mode = settings.get("spending_mode", "manual")
        if mode == "learned":
            try:
                from models.ledger import learned_everyday_weekly
                learned = learned_everyday_weekly()
                if learned is not None:
                    weekly = learned
                else:
                    mode = "manual"  # not enough history yet
            except Exception:
                mode = "manual"
        bank = account = None
        if settings.get("spending_account") and ":" in settings["spending_account"]:
            bank, account = settings["spending_account"].split(":", 1)
        self.everyday_spending = (
            {"amount": weekly / 7.0, "weekly": round(weekly, 2), "mode": mode, "bank": bank, "account": account}
            if weekly > 0 else None
        )
        self.invalidate_plan_cache()

    # ========== Linked Bill Auto-Creation ==========

    def _ensure_linked_bills(self):
        """
        Auto-create AccountLinkedBill objects for all credit, mortgage, and HELOC accounts
        that don't already have a linked bill in self.bills.  Credit accounts that belong
        to a bill group are skipped (the group's GroupLinkedBill covers them).

        Also auto-creates GroupLinkedBill objects for every bill group that doesn't
        already have one.

        Also deduplicates — if multiple linked bills exist for the same account or
        group, only the first one is kept.
        """
        # Collect credit accounts covered by bill groups
        grouped_credit_keys: set[str] = set()
        for group in self.bill_groups:
            for member in group.members:
                grouped_credit_keys.add(f"credit:{member.bank_name}:{member.account_name}")

        # First, deduplicate any existing linked bills
        seen_keys = set()
        deduped = []
        for bill in self.bills:
            if isinstance(bill, GroupLinkedBill):
                if bill.group_link_key in seen_keys:
                    continue  # Skip duplicate
                seen_keys.add(bill.group_link_key)
            elif isinstance(bill, AccountLinkedBill):
                if bill.account_link_key in seen_keys:
                    continue  # Skip duplicate
                seen_keys.add(bill.account_link_key)
            deduped.append(bill)
        self.bills = deduped

        for bank in self.banks:
            # Credit accounts (skip those covered by a bill group)
            for name, credit_account in bank.credit_accounts.items():
                link_key = f"credit:{bank.name}:{name}"
                if link_key in grouped_credit_keys:
                    continue  # Covered by a bill group
                if link_key not in seen_keys:
                    linked_bill = AccountLinkedBill(
                        linked_account=credit_account,
                        linked_bank_name=bank.name,
                        linked_account_type='credit',
                        bill_type=BillType.CREDIT_PAYMENT,
                    )
                    self.bills.append(linked_bill)
                    seen_keys.add(link_key)

            # Mortgage accounts
            for name, mortgage_account in bank.mortgage_accounts.items():
                link_key = f"mortgage:{bank.name}:{name}"
                if link_key not in seen_keys:
                    linked_bill = AccountLinkedBill(
                        linked_account=mortgage_account,
                        linked_bank_name=bank.name,
                        linked_account_type='mortgage',
                        bill_type=BillType.MORTGAGE_PAYMENT,
                    )
                    self.bills.append(linked_bill)
                    seen_keys.add(link_key)

            # HELOC accounts
            for name, heloc_account in bank.heloc_accounts.items():
                link_key = f"heloc:{bank.name}:{name}"
                if link_key not in seen_keys:
                    linked_bill = AccountLinkedBill(
                        linked_account=heloc_account,
                        linked_bank_name=bank.name,
                        linked_account_type='heloc',
                        bill_type=BillType.HELOC_PAYMENT,
                    )
                    self.bills.append(linked_bill)
                    seen_keys.add(link_key)

        # Auto-create GroupLinkedBill for each bill group
        for group in self.bill_groups:
            link_key = f"group:{group.group_name}"
            if link_key not in seen_keys:
                group_bill = GroupLinkedBill(linked_group=group)
                self.bills.append(group_bill)
                seen_keys.add(link_key)

    def _rebuild_linked_bills(self):
        """
        After loading from database, reconnect linked bills to their accounts.
        Removes any stale linked bill DB rows whose accounts no longer exist,
        deduplicates linked bills, and creates new ones for accounts that
        don't have linked bills yet.

        Also reconnects GroupLinkedBill objects to their BillGroup instances,
        and ensures credit accounts covered by bill groups don't get individual
        linked bills.
        """
        # Build a lookup of all existing accounts
        account_lookup = {}
        for bank in self.banks:
            for name, acc in bank.credit_accounts.items():
                account_lookup[f"credit:{bank.name}:{name}"] = (acc, bank.name, 'credit', BillType.CREDIT_PAYMENT)
            for name, acc in bank.mortgage_accounts.items():
                account_lookup[f"mortgage:{bank.name}:{name}"] = (acc, bank.name, 'mortgage', BillType.MORTGAGE_PAYMENT)
            for name, acc in bank.heloc_accounts.items():
                account_lookup[f"heloc:{bank.name}:{name}"] = (acc, bank.name, 'heloc', BillType.HELOC_PAYMENT)

        # Build a lookup of bill groups
        group_lookup = {f"group:{g.group_name}": g for g in self.bill_groups}

        # Collect credit accounts covered by bill groups
        grouped_credit_keys: set[str] = set()
        for group in self.bill_groups:
            for member in group.members:
                grouped_credit_keys.add(f"credit:{member.bank_name}:{member.account_name}")

        # Reconnect existing linked bills loaded from DB, deduplicating
        reconnected_keys = set()
        stale_bills = []
        for bill in self.bills:
            if isinstance(bill, GroupLinkedBill):
                key = bill.group_link_key
                if key in reconnected_keys:
                    stale_bills.append(bill)
                elif key in group_lookup:
                    group = group_lookup[key]
                    bill.linked_group = group
                    # Group settings may have been edited since the bill was built
                    bill.due_date = group.due_date
                    bill.frequency = group.frequency
                    bill.preferred_source_bank = group.preferred_source_bank
                    bill.preferred_source_account = group.preferred_source_account
                    reconnected_keys.add(key)
                else:
                    # Group no longer exists — mark for removal
                    stale_bills.append(bill)
            elif isinstance(bill, AccountLinkedBill):
                key = bill.account_link_key
                if key in reconnected_keys:
                    # Duplicate — mark for removal
                    stale_bills.append(bill)
                elif key in grouped_credit_keys:
                    # Credit account is now covered by a bill group — remove individual bill
                    stale_bills.append(bill)
                elif key in account_lookup:
                    acc, bank_name, acc_type, bt = account_lookup[key]
                    if bill.linked_account is not acc:
                        # Swapping in the real account (e.g. after a DB load):
                        # carry the bill's paid flag over to it
                        bill.linked_account = acc
                        bill.is_paid_this_period = bill._is_paid_this_period
                    bill.linked_bank_name = bank_name
                    bill.linked_account_type = acc_type
                    bill.due_date = getattr(acc, 'payment_due_date', None) or 1
                    reconnected_keys.add(key)
                else:
                    # Account no longer exists — mark for removal
                    stale_bills.append(bill)

        # Remove stale and duplicate linked bills
        for bill in stale_bills:
            self.bills.remove(bill)

        # Create new linked bills for accounts that don't have one yet
        # (skip credit accounts covered by bill groups)
        for key, (acc, bank_name, acc_type, bt) in account_lookup.items():
            if key in reconnected_keys:
                continue
            if key in grouped_credit_keys:
                continue  # Covered by a bill group
            linked_bill = AccountLinkedBill(
                linked_account=acc,
                linked_bank_name=bank_name,
                linked_account_type=acc_type,
                bill_type=bt,
            )
            self.bills.append(linked_bill)

        # Create new GroupLinkedBill for groups that don't have one yet
        for key, group in group_lookup.items():
            if key not in reconnected_keys:
                group_bill = GroupLinkedBill(linked_group=group)
                self.bills.append(group_bill)

    # ========== Bank Management ==========

    def get_all_banks(self) -> list[Bank]:
        """Get all banks."""
        return self.banks

    def add_bank(self, bank: Bank) -> None:
        """Add a bank."""
        if bank not in self.banks:
            self.banks.append(bank)
            self.refresh()

    def remove_bank(self, bank: Bank) -> None:
        """Remove a bank."""
        if bank in self.banks:
            self.banks.remove(bank)
            self.refresh()

    def get_all_accounts(self) -> list:
        """Get all accounts across all banks."""
        accounts = []
        for bank in self.banks:
            accounts.extend(bank.get_all_accounts())
            accounts.extend(bank.get_all_credit_accounts())
            accounts.extend(bank.get_all_mortgage_accounts())
            accounts.extend(bank.get_all_heloc_accounts())
        return accounts

    # ========== Income Management ==========

    def get_all_income_sources(self) -> list[IncomeSource]:
        """Get all income sources."""
        return self.income_sources

    def add_income_source(self, income: IncomeSource) -> None:
        """Add an income source."""
        if income not in self.income_sources:
            self.income_sources.append(income)
            self._update_managers()

    def remove_income_source(self, income: IncomeSource) -> None:
        """Remove an income source."""
        if income in self.income_sources:
            self.income_sources.remove(income)
            self._update_managers()

    # ========== Bill Management ==========

    def get_all_bills(self) -> list[Bill]:
        """Get all bills."""
        return self.bills

    def add_bill(self, bill: Bill) -> None:
        """Add a bill."""
        if bill not in self.bills:
            self.bills.append(bill)
            self._update_managers()

    def remove_bill(self, bill: Bill) -> None:
        """Remove a bill."""
        if bill in self.bills:
            self.bills.remove(bill)
            self._update_managers()

    # ========== Bill Group Management ==========

    def get_all_bill_groups(self) -> list[BillGroup]:
        """Get all bill groups."""
        return self.bill_groups

    def add_bill_group(self, group: BillGroup) -> None:
        """Add a bill group."""
        if group not in self.bill_groups:
            self.bill_groups.append(group)
            self.refresh()

    def remove_bill_group(self, group: BillGroup) -> None:
        """Remove a bill group."""
        if group in self.bill_groups:
            self.bill_groups.remove(group)
            self.refresh()

    def refresh(self) -> None:
        """
        Re-sync derived state after structural changes (accounts or groups
        added/removed, group membership or settings edited): drops group
        members whose account no longer exists, rebuilds linked bills, and
        rebuilds the simulators.
        """
        for group in self.bill_groups:
            group.members = [
                m for m in group.members
                if any(b.name == m.bank_name and m.account_name in b.credit_accounts for b in self.banks)
            ]
        self._rebuild_linked_bills()
        self._update_managers()

    def get_grouped_account_keys(self) -> set[tuple[str, str]]:
        """Get all (bank_name, account_name) pairs that belong to any bill group."""
        keys = set()
        for group in self.bill_groups:
            keys.update(group.get_grouped_account_keys())
        return keys

    # ========== Projection & Simulation ==========

    def project_balances(
        self,
        start_date: date = None,
        end_date: date = None,
        payment_strategy: dict = None,
        optimized: bool = True,
    ) -> dict:
        """
        Project account balances from start to end date.

        When `optimized` is True (default), uses the PaymentOptimizer to
        inject savings sweeps, promo payoffs, extra credit payments, and
        HELOC parking into the timeline so the projection reflects all
        optimizations in the actual balances.

        Args:
            start_date: Simulation start (default: today)
            end_date: Simulation end (default: today + 90 days)
            payment_strategy: Optional custom payment routing
            optimized: Whether to run through the optimizer (default True)

        Returns:
            Dictionary with snapshots, final balances, cash flow, and events
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        # Deep-copy all state as a single unit so AccountLinkedBill references
        # to their linked accounts stay connected within the copied graph.
        copied_banks, copied_income, copied_bills, copied_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )

        if optimized:
            optimizer = PaymentOptimizer(
                copied_banks, copied_income, copied_bills, copied_groups, **self.sim_options()
            )
            result, _ = optimizer.run_optimized_simulation(
                start_date, end_date,
                optimization_goal=self.optimization_goal,
                target_credit_account=self.target_credit_account,
                min_hold_days=self.min_hold_days,
            )
            return result
        else:
            simulator = TimelineSimulator(
                copied_banks, copied_income, copied_bills, copied_groups, **self.sim_options()
            )
            return simulator.project_balances(start_date, end_date, payment_strategy)

    def get_balance_on_date(
        self,
        target_date: date,
        bank_name: str = None,
        account_name: str = None
    ) -> dict | float:
        """
        Get account balance(s) on a specific date.

        Args:
            target_date: Target date for balance projection
            bank_name: Specific bank (optional)
            account_name: Specific account (optional)

        Returns:
            If specific account: float balance
            Otherwise: dict of all account balances
        """
        result = self.project_balances(
            start_date=date.today(),
            end_date=target_date
        )

        final_balances = result["final_balances"]

        if bank_name and account_name:
            key = f"{bank_name}:{account_name}"
            return final_balances.get(key, 0.0)
        elif bank_name:
            # Return all accounts in this bank
            return {
                k: v for k, v in final_balances.items()
                if k.startswith(f"{bank_name}:")
            }
        else:
            return final_balances

    def forecast_cash_flow(
        self,
        start_date: date = None,
        end_date: date = None
    ) -> list[dict]:
        """
        Get detailed cash flow projection.

        Returns list of transactions with date, type, description, amount.
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        result = self.project_balances(start_date, end_date)
        return result["cash_flow"]

    def get_critical_dates(self, months: int = 3) -> dict:
        """
        Get all critical financial dates (income, bills, etc.) for N months.

        Returns:
            {date: [list of events on that date]}
        """
        end_date = date.today() + timedelta(days=30 * months)
        start_date = date.today()

        result = self.project_balances(start_date, end_date)

        critical_dates = {}
        for event in result["events"]:
            if event.event_date not in critical_dates:
                critical_dates[event.event_date] = []
            critical_dates[event.event_date].append({
                "type": event.event_type,
                "description": event.description,
                "amount": event.amount
            })

        return critical_dates

    # ========== Payment Optimization ==========

    def set_optimization_strategy(
        self,
        goal: str = "maximize_discretionary",
        target_credit_account: str = None
    ):
        """
        Set the global optimization strategy. Invalidates cached plan.

        Args:
            goal: 'maximize_discretionary', 'minimize_interest', or 'payoff_credit_account'
            target_credit_account: Required when goal is 'payoff_credit_account'
        """
        self.optimization_goal = goal
        self.target_credit_account = target_credit_account
        self._cached_plan = None
        self._cached_plan_end = None

    def get_global_plan(self, end_date: date = None) -> PaymentPlan:
        """
        Get the global optimized payment plan using the current strategy.
        Caches the result so multiple views share the same plan.
        """
        end_date = end_date or date.today() + timedelta(days=90)

        # Return cached if still valid for this end_date
        if (self._cached_plan is not None
                and self._cached_plan_end is not None
                and self._cached_plan_end == end_date):
            return self._cached_plan

        self._cached_plan = self.optimize_payments(
            end_date=end_date,
            optimization_goal=self.optimization_goal,
            target_credit_account=self.target_credit_account
        )
        self._cached_plan_end = end_date
        return self._cached_plan

    def invalidate_plan_cache(self):
        """Invalidate the cached plan (call after data changes)."""
        self._cached_plan = None
        self._cached_plan_end = None

    def optimize_payments(
        self,
        start_date: date = None,
        end_date: date = None,
        optimization_goal: str = None,
        target_credit_account: str = None
    ) -> PaymentPlan:
        """
        Generate an optimized payment plan.

        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            optimization_goal: Override global goal (defaults to self.optimization_goal)
            target_credit_account: Override global target (defaults to self.target_credit_account)

        Returns:
            PaymentPlan with strategy and metrics
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)
        goal = optimization_goal or self.optimization_goal
        target = target_credit_account or self.target_credit_account

        copied_banks, copied_income, copied_bills, copied_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )

        optimizer = PaymentOptimizer(
            copied_banks,
            copied_income,
            copied_bills,
            copied_groups,
            **self.sim_options(),
        )

        return optimizer.optimize_payment_schedule(
            start_date, end_date, goal, target
        )

    def get_multiple_strategies(
        self,
        start_date: date = None,
        end_date: date = None,
        num_strategies: int = 3
    ) -> list[PaymentPlan]:
        """
        Generate and compare multiple payment strategies.

        Returns:
            List of PaymentPlan objects sorted by discretionary funds
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        copied_banks, copied_income, copied_bills, copied_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )

        optimizer = PaymentOptimizer(
            copied_banks,
            copied_income,
            copied_bills,
            copied_groups,
            **self.sim_options(),
        )

        return optimizer.generate_multiple_strategies(start_date, end_date, num_strategies)

    # ========== Bill & Income Management ==========

    def assign_bill_payment_source(
        self,
        bill_name: str,
        bank_name: str,
        account_name: str
    ) -> None:
        """Assign which account should pay a specific bill."""
        for bill in self.bills:
            if bill.bill_name == bill_name:
                bill.preferred_source_bank = bank_name
                bill.preferred_source_account = account_name
                return
        raise ValueError(f"Bill '{bill_name}' not found.")

    def set_income_distribution(
        self,
        income_name: str,
        distribution: dict
    ) -> None:
        """Set how income should be distributed across accounts."""
        from models.types import DistributionType
        
        for income in self.income_sources:
            if income.source_name == income_name:
                # Convert dict to DistributionType if needed
                if isinstance(distribution, dict):
                    income.distribution = DistributionType.__fromdict__(distribution)
                else:
                    income.distribution = distribution
                return
        raise ValueError(f"Income source '{income_name}' not found.")

    def get_upcoming_bills(self, days: int = 30) -> list[Bill]:
        """Get bills due in the next N days."""
        end_date = date.today() + timedelta(days=days)
        upcoming = []

        for bill in self.bills:
            next_due = bill.get_next_due_date(date.today() - timedelta(days=1))
            if next_due <= end_date:
                upcoming.append(bill)

        return sorted(upcoming, key=lambda b: b.get_next_due_date(date.today() - timedelta(days=1)))

    def get_upcoming_income(self, days: int = 30) -> list[IncomeSource]:
        """Get income deposits expected in the next N days."""
        end_date = date.today() + timedelta(days=days)
        upcoming = []

        for income in self.income_sources:
            next_pay = income.get_next_pay_date(date.today() - timedelta(days=1))
            if next_pay <= end_date:
                upcoming.append(income)

        return sorted(upcoming, key=lambda i: i.get_next_pay_date(date.today() - timedelta(days=1)))

    # ========== Account Management ==========

    def get_account_balance(self, bank_name: str, account_name: str) -> float:
        """Get current balance of a specific account."""
        bank = next((b for b in self.banks if b.name == bank_name), None)
        if not bank:
            raise ValueError(f"Bank '{bank_name}' not found.")

        if account_name in bank.accounts:
            return bank.accounts[account_name].balance
        elif account_name in bank.credit_accounts:
            return bank.credit_accounts[account_name].balance
        else:
            raise ValueError(f"Account '{account_name}' not found in {bank_name}.")

    def get_total_assets(self) -> float:
        """Get total cash across all bank accounts."""
        total = 0
        for bank in self.banks:
            total += bank.total_balance()
        return total

    def get_total_liabilities(self) -> float:
        """Get total liabilities (credit + mortgage + HELOC)."""
        total = 0
        for bank in self.banks:
            total += bank.total_liabilities()
        return total

    def get_net_worth(self) -> float:
        """Get net worth (assets - liabilities)."""
        return self.get_total_assets() - self.get_total_liabilities()

    def calculate_safe_to_spend(self) -> dict:
        """
        Calculate discretionary funds over the next two pay periods.
        
        Logic:
        - Current checking balance already reflects bills/payments that have been paid
        - Add any income arriving within the next two pay periods
        - Subtract all UNPAID obligations due within the next two pay periods
          (this now includes linked bills for credit/mortgage/HELOC payments)
        
        Result = checking + upcoming_income - unpaid_obligations = discretionary
        """
        today = date.today()
        
        # ── Find pay dates to determine the two-pay-period window ──
        all_pay_dates = []
        for income in self.income_sources:
            try:
                dates = income.get_pay_dates_in_range(today - timedelta(days=1), today + timedelta(days=75))
                all_pay_dates.extend(dates)
            except Exception:
                pass
        all_pay_dates = sorted(set(all_pay_dates))
        
        # Find the next two distinct pay dates
        next_pay_date = None
        second_pay_date = None
        for pd in all_pay_dates:
            if pd > today:
                if next_pay_date is None:
                    next_pay_date = pd
                elif pd > next_pay_date and second_pay_date is None:
                    second_pay_date = pd
                    break
        
        if not next_pay_date:
            next_pay_date = today + timedelta(days=14)
        if not second_pay_date:
            second_pay_date = next_pay_date + timedelta(days=14)
        
        horizon = second_pay_date

        grouped_keys = self.get_grouped_account_keys()
        
        # ── Sum checking account balances (already reflects paid items) ──
        total_checking = 0.0
        for bank in self.banks:
            for acc in bank.get_all_accounts():
                if acc.account_type.value == "checking":
                    total_checking += acc.balance
        
        # ── Sum income arriving between now and horizon ──
        upcoming_income = 0.0
        for income in self.income_sources:
            try:
                dates = income.get_pay_dates_in_range(today - timedelta(days=1), horizon)
                for pd in dates:
                    if pd > today:
                        upcoming_income += income.amount
            except Exception:
                pass
        
        # ── Sum UNPAID obligations due between now and horizon ──
        # Now we only iterate self.bills — linked bills cover credit/mortgage/HELOC/groups
        committed = 0.0
        
        for bill in self.bills:
            if bill.is_paid_this_period:
                continue

            # Skip linked bills whose account is in a bill group
            if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'credit':
                if (bill.linked_bank_name, bill.linked_account.account_name) in grouped_keys:
                    continue
                # Skip zero-balance credit cards
                if bill.linked_account.balance <= 0:
                    continue

            try:
                next_due = bill.get_next_due_date(today - timedelta(days=1))
                if next_due <= horizon:
                    committed += bill.effective_amount
            except Exception:
                pass

        # The headline number comes from the dashboard's projection (lowest
        # checking balance − cushion − overdue/short bills, with everyday
        # spending) so every screen shows the same safe-to-spend. The totals
        # above remain as the breakdown.
        try:
            from models.dashboard import build_dashboard
            discretionary = build_dashboard(self, today)["safe_to_spend"]
        except Exception:
            discretionary = total_checking + upcoming_income - committed
        return {
            'safe_to_spend': round(discretionary, 2),
            'total_checking': round(total_checking, 2),
            'committed_bills': round(committed, 2),
            'upcoming_income': round(upcoming_income, 2),
            'next_income_date': next_pay_date.isoformat(),
            'horizon_date': horizon.isoformat(),
        }

    def auto_reset_periods(self) -> int:
        """
        Auto-reset bills/mortgages whose billing period has rolled over.
        Returns count of bills reset.
        
        Since all payments are now tracked as bills (including linked bills),
        we only need to iterate self.bills.
        """
        today = date.today()
        reset_count = 0
        
        for bill in self.bills:
            if not bill.is_paid_this_period:
                continue
            try:
                history = bill.payment_history
                if not history and isinstance(bill, GroupLinkedBill):
                    history = bill.linked_group.payment_history
                if history:
                    last_paid = history[-1].get('date', today)
                    if isinstance(last_paid, str):
                        last_paid = date.fromisoformat(last_paid)
                    next_after_payment = bill.get_next_due_date(last_paid)
                    if next_after_payment <= today:
                        bill.is_paid_this_period = False
                        reset_count += 1
            except Exception:
                pass
        
        if reset_count > 0:
            self.save_to_database()
        
        return reset_count

    def record_net_worth_snapshot(self) -> dict | None:
        """Record current net worth to the database. Returns the snapshot data."""
        try:
            from models.database import get_session
            from sqlalchemy import text
            
            total_assets = self.get_total_assets()
            total_liabilities = self.get_total_liabilities()  # includes mortgages and HELOCs
            net_worth = total_assets - total_liabilities
            
            session = get_session()
            try:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS net_worth_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_assets REAL NOT NULL,
                        total_liabilities REAL NOT NULL,
                        net_worth REAL NOT NULL,
                        snapshot_date TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))
                
                # Only record once per day
                today_str = date.today().isoformat()
                existing = session.execute(text(
                    "SELECT id FROM net_worth_snapshots WHERE snapshot_date = :d"
                ), {"d": today_str}).fetchone()
                
                if existing:
                    session.execute(text(
                        "UPDATE net_worth_snapshots SET total_assets=:a, total_liabilities=:l, net_worth=:n WHERE snapshot_date=:d"
                    ), {"a": total_assets, "l": total_liabilities, "n": net_worth, "d": today_str})
                else:
                    from datetime import datetime, timezone
                    session.execute(text("""
                        INSERT INTO net_worth_snapshots (total_assets, total_liabilities, net_worth, snapshot_date, created_at)
                        VALUES (:a, :l, :n, :d, :ts)
                    """), {"a": total_assets, "l": total_liabilities, "n": net_worth,
                           "d": today_str, "ts": datetime.now(timezone.utc).isoformat()})
                
                session.commit()
                return {
                    'total_assets': total_assets,
                    'total_liabilities': total_liabilities,
                    'net_worth': net_worth,
                    'snapshot_date': today_str,
                }
            finally:
                session.close()
        except Exception:
            return None

    def run_what_if_scenario(self, modifications: dict, days: int = 90) -> dict:
        """
        Run a what-if scenario by applying modifications to a copy of current state.
        
        modifications can include:
        - add_bills: [{bill_name, amount, due_date, frequency}]
        - remove_bills: [bill_name, ...]  (also supports '__CUT_20%__' for percentage cuts)
        - adjust_income: [{source_name, new_amount}]
        - remove_income: [source_name, ...]
        - extra_payments: [{bank_name, account_name, amount}]
        
        adjust_income new_amount special values:
        - 0: sets income to $0 (job loss)
        - negative value (e.g. -10): percentage raise (10% raise)
        - positive value: sets income to that exact amount
        """
        end = date.today() + timedelta(days=days)
        
        # Run baseline and scenario in parallel-ish fashion using separate copies
        # Deepcopy as a unit so linked bill references stay connected
        baseline_banks, baseline_income, baseline_bills, baseline_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )
        baseline_sim = TimelineSimulator(
            baseline_banks, baseline_income,
            baseline_bills, baseline_groups, **self.sim_options()
        )
        baseline = baseline_sim.project_balances(date.today(), end)
        
        # Create modified copies for scenario
        mod_banks, mod_income, mod_bills, mod_bill_groups = deepcopy(
            (self.banks, self.income_sources, self.bills, self.bill_groups)
        )
        
        # Apply modifications
        if 'add_bills' in modifications:
            for b in modifications['add_bills']:
                new_bill = Bill(
                    bill_name=b.get('bill_name', 'New Bill'),
                    amount=b.get('amount', 0),
                    due_date=b.get('due_date', 1),
                    frequency=b.get('frequency', 'monthly'),
                )
                mod_bills.append(new_bill)
        
        if 'remove_bills' in modifications:
            cut_pct = None
            bill_removals = []
            credit_removals = []    # "credit:BankName:AccountName"
            mortgage_removals = []  # "mortgage:BankName:AccountName"
            heloc_removals = []     # "heloc:BankName:AccountName"
            group_removals = []     # "group:GroupName"
            for name in modifications['remove_bills']:
                if isinstance(name, str) and name.startswith('__CUT_') and name.endswith('__'):
                    try:
                        pct_str = name.replace('__CUT_', '').replace('%__', '')
                        cut_pct = float(pct_str) / 100.0
                    except ValueError:
                        pass
                elif isinstance(name, str) and name.startswith('credit:'):
                    credit_removals.append(name[len('credit:'):])
                elif isinstance(name, str) and name.startswith('mortgage:'):
                    mortgage_removals.append(name[len('mortgage:'):])
                elif isinstance(name, str) and name.startswith('heloc:'):
                    heloc_removals.append(name[len('heloc:'):])
                elif isinstance(name, str) and name.startswith('group:'):
                    group_removals.append(name[len('group:'):])
                else:
                    bill_removals.append(name)
            
            # Remove regular bills
            if bill_removals:
                mod_bills = [b for b in mod_bills if b.bill_name not in bill_removals]
            
            # Remove credit accounts (zero out balance so no payments are generated)
            for key in credit_removals:
                parts = key.split(':', 1)
                if len(parts) == 2:
                    bank_name, acct_name = parts
                    for bank in mod_banks:
                        if bank.name == bank_name and acct_name in bank.credit_accounts:
                            card = bank.credit_accounts[acct_name]
                            card.balance = 0
                            card.regular_balance = 0
                            card.promo_balance = {k: 0.0 for k in card.promo_balance}
            
            # Remove mortgage payments (zero out principal so no payments are generated)
            for key in mortgage_removals:
                parts = key.split(':', 1)
                if len(parts) == 2:
                    bank_name, acct_name = parts
                    for bank in mod_banks:
                        if bank.name == bank_name:
                            mortgages = getattr(bank, 'mortgage_accounts', {})
                            if isinstance(mortgages, dict) and acct_name in mortgages:
                                mortgages[acct_name].current_principal = 0
                                mortgages[acct_name].is_paid_this_period = True
            
            # Remove HELOC payments (zero out balance)
            for key in heloc_removals:
                parts = key.split(':', 1)
                if len(parts) == 2:
                    bank_name, acct_name = parts
                    for bank in mod_banks:
                        if bank.name == bank_name:
                            helocs = getattr(bank, 'heloc_accounts', {})
                            if isinstance(helocs, dict) and acct_name in helocs:
                                helocs[acct_name].balance = 0
                                helocs[acct_name].is_paid_this_period = True
            
            # Remove bill groups
            if group_removals:
                mod_bill_groups = [g for g in mod_bill_groups if g.group_name not in group_removals]
                mod_bills = [b for b in mod_bills
                             if not (isinstance(b, GroupLinkedBill) and b.linked_group.group_name in group_removals)]
            
            # Apply percentage cut to all remaining regular bills
            if cut_pct is not None:
                for b in mod_bills:
                    if not isinstance(b, (AccountLinkedBill, GroupLinkedBill)):
                        b.amount = b.amount * (1 - cut_pct)
        
        if 'adjust_income' in modifications:
            for adj in modifications['adjust_income']:
                source_name = adj.get('source_name', '')
                new_amount = adj.get('new_amount', 0)
                
                for inc in mod_income:
                    if inc.source_name == source_name:
                        if new_amount == 0:
                            inc.amount = 0
                        elif new_amount < 0:
                            # Negative value signals a percentage raise
                            pct = abs(new_amount) / 100.0
                            inc.amount = inc.amount * (1 + pct)
                        else:
                            inc.amount = new_amount
        
        if 'remove_income' in modifications:
            mod_income = [i for i in mod_income if i.source_name not in modifications['remove_income']]
        
        if 'extra_payments' in modifications:
            for ep in modifications['extra_payments']:
                for bank in mod_banks:
                    if bank.name == ep.get('bank_name'):
                        acc_name = ep.get('account_name')
                        if acc_name in bank.credit_accounts:
                            bank.credit_accounts[acc_name].make_payment(
                                ep.get('amount', 0),
                                transaction_date=date.today()
                            )
        
        # Run scenario simulation WITH bill groups
        scenario_sim = TimelineSimulator(mod_banks, mod_income, mod_bills, mod_bill_groups, **self.sim_options())
        scenario = scenario_sim.project_balances(date.today(), end)
        
        # Calculate deltas
        baseline_final = sum(baseline['final_balances'].values())
        scenario_final = sum(scenario['final_balances'].values())

        # Plain-language outcome summaries (late payments, lowest balance, interest)
        from models.payment_insights import summarize_simulation, describe_outcome_change
        baseline_summary = summarize_simulation(baseline, self.banks)
        scenario_summary = summarize_simulation(scenario, self.banks)

        return {
            'baseline_final_balance': baseline_final,
            'scenario_final_balance': scenario_final,
            'difference': round(scenario_final - baseline_final, 2),
            'baseline_snapshots': baseline['snapshots'],
            'scenario_snapshots': scenario['snapshots'],
            'baseline_summary': baseline_summary,
            'scenario_summary': scenario_summary,
            'changes': describe_outcome_change(baseline_summary, scenario_summary,
                                               'your current plan', 'This scenario'),
        }

    def payment_insights(self, days: int = 90, start_date: date = None) -> dict:
        """Plain-language payment recommendations (see models/payment_insights.py)."""
        from models.payment_insights import PaymentInsightsAnalyzer
        return PaymentInsightsAnalyzer(self, start_date=start_date, days=days).analyze()

    # ========== Reporting ==========

    def generate_snapshot(self) -> str:
        """Generate current financial snapshot."""
        return self.financial_reporter.current_snapshot()

    def generate_projection_report(
        self,
        start_date: date = None,
        end_date: date = None,
        include_optimization: bool = True
    ) -> dict:
        """Generate comprehensive projection report. Returns dict with 'text' and 'result'."""
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        return self.financial_reporter.projection_report(
            start_date, end_date, include_optimization
        )

    def generate_detailed_timeline(
        self,
        start_date: date = None,
        end_date: date = None,
        payment_strategy: dict = None
    ) -> str:
        """Generate day-by-day timeline."""
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=30)

        return self.financial_reporter.detailed_timeline(
            start_date, end_date, payment_strategy
        )

    def generate_budget_analysis(self, months: int = 3) -> str:
        """Generate budget analysis for N months."""
        return self.financial_reporter.budget_analysis(months)

    def generate_payment_schedule(self, months: int = 1) -> str:
        """Generate payment schedule for next N months."""
        return self.financial_reporter.payment_schedule(months)

    # ========== State Management ==========

    def save_to_database(self) -> bool:
        """
        Save current financial state to SQLite database.

        Returns:
            True if successful, False otherwise
        """
        try:
            from models.db_repository import DatabaseRepository

            # Make sure linked bills/groups reflect the current accounts first
            self.refresh()

            repo = DatabaseRepository()

            # Save all banks and their accounts
            for bank in self.banks:
                repo.save_bank(bank)

            # Save all bills (including linked bills)
            for bill in self.bills:
                repo.save_bill(bill)

            # Save all income sources
            for income in self.income_sources:
                repo.save_income_source(income)

            # Save all bill groups
            for group in self.bill_groups:
                repo.save_bill_group(group)

            # Remove rows for anything deleted in memory
            if self._db_sync_deletions:
                repo.prune_deleted(self.banks, self.bills, self.income_sources, self.bill_groups)

            repo.close()
            return True
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
            return False

    def load_from_database(self) -> bool:
        """
        Load financial state from SQLite database.

        Returns:
            True if successful, False otherwise
        """
        try:
            from models.db_repository import DatabaseRepository

            repo = DatabaseRepository()

            # Load banks and accounts
            loaded_banks = repo.load_banks()
            if loaded_banks:
                self.banks = loaded_banks

            # Load bills
            loaded_bills = repo.load_bills()
            if loaded_bills:
                self.bills = loaded_bills

            # Load income sources
            loaded_incomes = repo.load_income_sources()
            if loaded_incomes:
                self.income_sources = loaded_incomes

            # Load bill groups
            loaded_groups = repo.load_bill_groups()
            if loaded_groups is not None:
                self.bill_groups = loaded_groups

            # Reconnect linked bills to loaded accounts, create missing ones,
            # and rebuild the simulators
            self.refresh()

            repo.close()
            self._db_sync_deletions = True
            try:
                from models.app_settings import get_settings
                self.apply_settings(get_settings())
            except Exception as e:
                print(f"⚠️  Could not load settings: {e}")
            return True
        except Exception as e:
            print(f"❌ Error loading from database: {e}")
            return False

    def initialize_database(self) -> None:
        """Initialize the database with schema."""
        try:
            from models.database import init_db
            init_db()
        except Exception as e:
            print(f"❌ Error initializing database: {e}")

    def _update_managers(self) -> None:
        """Update internal managers when data changes."""
        self.timeline_simulator = TimelineSimulator(self.banks, self.income_sources, self.bills, self.bill_groups)
        self.payment_optimizer = PaymentOptimizer(self.banks, self.income_sources, self.bills, self.bill_groups)
        self.financial_reporter = FinancialReport(self.banks, self.income_sources, self.bills, self.bill_groups)
        self.invalidate_plan_cache()
