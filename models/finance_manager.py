from datetime import date, timedelta
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer, PaymentPlan
from models.financial_report import FinancialReport


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

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill]):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills

        self.timeline_simulator = TimelineSimulator(banks, income_sources, bills)
        self.payment_optimizer = PaymentOptimizer(banks, income_sources, bills)
        self.financial_reporter = FinancialReport(banks, income_sources, bills)

    # ========== Bank Management ==========

    def get_all_banks(self) -> list[Bank]:
        """Get all banks."""
        return self.banks

    def add_bank(self, bank: Bank) -> None:
        """Add a bank."""
        if bank not in self.banks:
            self.banks.append(bank)
            self._update_managers()

    def remove_bank(self, bank: Bank) -> None:
        """Remove a bank."""
        if bank in self.banks:
            self.banks.remove(bank)
            self._update_managers()

    def get_all_accounts(self) -> list:
        """Get all accounts across all banks."""
        accounts = []
        for bank in self.banks:
            accounts.extend(bank.get_all_accounts())
            accounts.extend(bank.get_all_credit_accounts())
            accounts.extend(bank.get_all_mortgage_accounts())
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

    # ========== Projection & Simulation ==========

    def project_balances(
        self,
        start_date: date = None,
        end_date: date = None,
        payment_strategy: dict = None
    ) -> dict:
        """
        Project account balances from start to end date.

        Args:
            start_date: Simulation start (default: today)
            end_date: Simulation end (default: today + 90 days)
            payment_strategy: Optional custom payment routing

        Returns:
            Dictionary with snapshots, final balances, cash flow, and events
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
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

    def optimize_payments(
        self,
        start_date: date = None,
        end_date: date = None,
        optimization_goal: str = "maximize_discretionary"
    ) -> PaymentPlan:
        """
        Generate an optimized payment plan.

        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            optimization_goal: 'maximize_discretionary', 'minimize_interest', etc.

        Returns:
            PaymentPlan with strategy and metrics
        """
        start_date = start_date or date.today()
        end_date = end_date or date.today() + timedelta(days=90)

        optimizer = PaymentOptimizer(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        return optimizer.optimize_payment_schedule(start_date, end_date, optimization_goal)

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

        optimizer = PaymentOptimizer(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
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
        for income in self.income_sources:
            if income.source_name == income_name:
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
        """Get total credit card debt."""
        total = 0
        for bank in self.banks:
            total += bank.total_credit_owed()
        return total

    def get_net_worth(self) -> float:
        """Get net worth (assets - liabilities)."""
        return self.get_total_assets() - self.get_total_liabilities()

    # ========== Reporting ==========

    def generate_snapshot(self) -> str:
        """Generate current financial snapshot."""
        return self.financial_reporter.current_snapshot()

    def generate_projection_report(
        self,
        start_date: date = None,
        end_date: date = None,
        include_optimization: bool = True
    ) -> str:
        """Generate comprehensive projection report."""
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

            repo = DatabaseRepository()

            # Save all banks and their accounts
            for bank in self.banks:
                repo.save_bank(bank)

            # Save all bills
            for bill in self.bills:
                repo.save_bill(bill)

            # Save all income sources
            for income in self.income_sources:
                repo.save_income_source(income)

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

            # Reinitialize managers with loaded data
            from models.timeline_simulator import TimelineSimulator
            from models.payment_optimizer import PaymentOptimizer
            from models.financial_report import FinancialReport

            self.timeline_simulator = TimelineSimulator(self.banks, self.income_sources, self.bills)
            self.payment_optimizer = PaymentOptimizer(self.banks, self.income_sources, self.bills)
            self.financial_reporter = FinancialReport(self.banks, self.income_sources, self.bills)

            repo.close()
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
        self.timeline_simulator = TimelineSimulator(self.banks, self.income_sources, self.bills)
        self.payment_optimizer = PaymentOptimizer(self.banks, self.income_sources, self.bills)
        self.financial_reporter = FinancialReport(self.banks, self.income_sources, self.bills)
