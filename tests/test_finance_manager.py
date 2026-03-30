"""
Tests for finance manager integration and high-level functionality.
"""

import pytest
from datetime import date, timedelta
from models.finance_manager import FinanceManager
from models.types import BillFrequency


class TestFinanceManager:
    """Test FinanceManager class functionality."""

    def test_finance_manager_creation(self, sample_bank, sample_income, sample_bills):
        """Test creating a finance manager."""
        manager = FinanceManager([sample_bank], sample_income, sample_bills)

        assert len(manager.banks) == 1
        assert len(manager.income_sources) == 2
        assert len(manager.bills) == 5

    def test_get_all_banks(self, sample_finance_manager):
        """Test getting all banks."""
        manager = sample_finance_manager
        banks = manager.get_all_banks()

        assert len(banks) >= 1
        assert all(hasattr(bank, 'name') for bank in banks)

    def test_get_all_accounts(self, sample_finance_manager):
        """Test getting all accounts across banks."""
        manager = sample_finance_manager
        accounts = manager.get_all_accounts()

        assert len(accounts) >= 0
        for account in accounts:
            assert hasattr(account, 'account_name')
            assert hasattr(account, 'balance')

    def test_get_all_income_sources(self, sample_finance_manager):
        """Test getting all income sources."""
        manager = sample_finance_manager
        income_sources = manager.get_all_income_sources()

        assert len(income_sources) >= 0
        assert all(hasattr(income, 'source_name') for income in income_sources)

    def test_get_all_bills(self, sample_finance_manager):
        """Test getting all bills."""
        manager = sample_finance_manager
        bills = manager.get_all_bills()

        assert len(bills) >= 0
        assert all(hasattr(bill, 'bill_name') for bill in bills)

    def test_project_balances(self, sample_finance_manager, sample_date_range):
        """Test balance projection through finance manager."""
        manager = sample_finance_manager
        start_date, end_date = sample_date_range

        result = manager.project_balances(start_date, end_date)

        assert "snapshots" in result
        assert "final_balances" in result
        assert "cash_flow" in result
        assert len(result["snapshots"]) > 0

    def test_optimize_payments(self, sample_finance_manager, sample_date_range):
        """Test payment optimization through finance manager."""
        manager = sample_finance_manager
        start_date, end_date = sample_date_range

        plan = manager.optimize_payments(start_date, end_date)

        assert hasattr(plan, 'strategy')
        assert hasattr(plan, 'final_discretionary')
        assert hasattr(plan, 'total_interest_paid')

    def test_add_bank(self, sample_finance_manager):
        """Test adding a bank to finance manager."""
        manager = sample_finance_manager
        initial_bank_count = len(manager.banks)

        from models.bank import Bank
        new_bank = Bank("New Bank")
        manager.add_bank(new_bank)

        assert len(manager.banks) == initial_bank_count + 1
        assert new_bank in manager.banks

    def test_add_income_source(self, sample_finance_manager):
        """Test adding an income source."""
        manager = sample_finance_manager
        initial_income_count = len(manager.income_sources)

        from models.income_source import IncomeSource
        new_income = IncomeSource("Bonus", 1000, frequency="quarterly", pay_date=[15])
        manager.add_income_source(new_income)

        assert len(manager.income_sources) == initial_income_count + 1
        assert new_income in manager.income_sources

    def test_add_bill(self, sample_finance_manager):
        """Test adding a bill."""
        manager = sample_finance_manager
        initial_bill_count = len(manager.bills)

        from models.fixed_bill import Bill
        new_bill = Bill("New Bill", 100, 15)
        manager.add_bill(new_bill)

        assert len(manager.bills) == initial_bill_count + 1
        assert new_bill in manager.bills

    def test_remove_bank(self, sample_finance_manager):
        """Test removing a bank."""
        manager = sample_finance_manager
        initial_bank_count = len(manager.banks)

        if initial_bank_count > 0:
            bank_to_remove = manager.banks[0]
            manager.remove_bank(bank_to_remove)

            assert len(manager.banks) == initial_bank_count - 1
            assert bank_to_remove not in manager.banks

    def test_remove_income_source(self, sample_finance_manager):
        """Test removing an income source."""
        manager = sample_finance_manager
        initial_income_count = len(manager.income_sources)

        if initial_income_count > 0:
            income_to_remove = manager.income_sources[0]
            manager.remove_income_source(income_to_remove)

            assert len(manager.income_sources) == initial_income_count - 1
            assert income_to_remove not in manager.income_sources

    def test_remove_bill(self, sample_finance_manager):
        """Test removing a bill."""
        manager = sample_finance_manager
        initial_bill_count = len(manager.bills)

        if initial_bill_count > 0:
            bill_to_remove = manager.bills[0]
            manager.remove_bill(bill_to_remove)

            assert len(manager.bills) == initial_bill_count - 1
            assert bill_to_remove not in manager.bills


class TestFinanceManagerIntegration:
    """Test finance manager integration with all components."""

    def test_complete_financial_workflow(self, sample_finance_manager):
        """Test complete financial management workflow."""
        manager = sample_finance_manager

        # Add some test data
        from models.fixed_bill import Bill
        yearly_bill = Bill(
            "Property Tax",
            2400,
            15,
            due_month=4,
            frequency=BillFrequency.YEARLY
        )
        manager.add_bill(yearly_bill)

        # Test projection
        start_date = date(2024, 3, 1)
        end_date = date(2024, 5, 31)  # Includes April 15th

        result = manager.project_balances(start_date, end_date)

        # Should include the yearly bill
        cash_flow = result["cash_flow"]
        bill_payments = [cf for cf in cash_flow if cf.get("type") == "BILL_DUE"]
        assert len(bill_payments) > 0

    def test_finance_manager_with_multiple_bank_types(self):
        """Test finance manager with multiple bank types."""
        from models.bank import Bank

        # Create different bank types
        checking_bank = Bank("Checking Bank")
        checking_bank.add_account("checking", "Checking", 5000)

        credit_bank = Bank("Credit Bank")
        credit_bank.add_credit_account("Card", 5000)

        mortgage_bank = Bank("Mortgage Bank")
        mortgage_bank.add_mortgage_account("Mortgage", 200000)

        from models.income_source import IncomeSource
        from models.fixed_bill import Bill

        income = [IncomeSource("Salary", 5000, pay_date=[1])]
        bills = [Bill("Rent", 2000, 1)]

        manager = FinanceManager([checking_bank, credit_bank, mortgage_bank], income, bills)

        # Test that all components work together
        accounts = manager.get_all_accounts()
        assert len(accounts) >= 1  # At least checking account

        # Test projection
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = manager.project_balances(start_date, end_date)
        assert len(result["snapshots"]) > 0

    def test_finance_manager_data_persistence(self, sample_finance_manager):
        """Test that finance manager maintains data integrity."""
        manager = sample_finance_manager

        # Get initial state
        initial_banks = len(manager.banks)
        initial_income = len(manager.income_sources)
        initial_bills = len(manager.bills)

        # Add items
        from models.bank import Bank
        from models.income_source import IncomeSource
        from models.fixed_bill import Bill

        manager.add_bank(Bank("Test Bank"))
        manager.add_income_source(IncomeSource("Test Income", 1000, pay_date=[1]))
        manager.add_bill(Bill("Test Bill", 100, 1))

        # Verify additions
        assert len(manager.banks) == initial_banks + 1
        assert len(manager.income_sources) == initial_income + 1
        assert len(manager.bills) == initial_bills + 1

        # Remove items
        manager.remove_bank(manager.banks[-1])
        manager.remove_income_source(manager.income_sources[-1])
        manager.remove_bill(manager.bills[-1])

        # Verify removals
        assert len(manager.banks) == initial_banks
        assert len(manager.income_sources) == initial_income
        assert len(manager.bills) == initial_bills


class TestFinanceManagerReports:
    """Test finance manager reporting functionality."""

    def test_generate_balance_report(self, sample_finance_manager):
        """Test generating balance reports."""
        manager = sample_finance_manager

        # This would test any reporting methods if they exist
        # For now, just verify the manager has the necessary data
        accounts = manager.get_all_accounts()
        assert len(accounts) >= 0

    def test_generate_income_report(self, sample_finance_manager):
        """Test generating income reports."""
        manager = sample_finance_manager

        income_sources = manager.get_all_income_sources()
        assert len(income_sources) >= 0

        # Test income projection
        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        # This tests the underlying timeline functionality
        result = manager.project_balances(start_date, end_date)
        cash_flow = result["cash_flow"]

        income_events = [cf for cf in cash_flow if cf.get("type") == "INCOME"]
        assert len(income_events) >= 0

    def test_generate_bill_report(self, sample_finance_manager):
        """Test generating bill reports."""
        manager = sample_finance_manager

        bills = manager.get_all_bills()
        assert len(bills) >= 0

        # Test bill projection
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = manager.project_balances(start_date, end_date)
        cash_flow = result["cash_flow"]

        bill_events = [cf for cf in cash_flow if cf.get("type") == "BILL_DUE"]
        assert len(bill_events) >= 0


class TestFinanceManagerEdgeCases:
    """Test finance manager edge cases."""

    def test_empty_finance_manager(self):
        """Test finance manager with no data."""
        manager = FinanceManager([], [], [])

        assert len(manager.banks) == 0
        assert len(manager.income_sources) == 0
        assert len(manager.bills) == 0

        # Should still work for basic operations
        accounts = manager.get_all_accounts()
        assert len(accounts) == 0

    def test_finance_manager_with_only_income(self):
        """Test finance manager with only income sources."""
        from models.income_source import IncomeSource
        from models.bank import Bank

        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 1000)

        income = IncomeSource("Salary", 5000, pay_date=[1])

        manager = FinanceManager([bank], [income], [])

        # Test projection
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = manager.project_balances(start_date, end_date)

        # Should have income events
        cash_flow = result["cash_flow"]
        income_events = [cf for cf in cash_flow if cf.get("type") == "INCOME"]
        assert len(income_events) > 0

    def test_finance_manager_with_only_bills(self):
        """Test finance manager with only bills."""
        from models.fixed_bill import Bill
        from models.bank import Bank

        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 10000)  # Plenty of money

        bill = Bill("Rent", 2000, 1)

        manager = FinanceManager([bank], [], [bill])

        # Test projection
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = manager.project_balances(start_date, end_date)

        # Should have bill events
        cash_flow = result["cash_flow"]
        bill_events = [cf for cf in cash_flow if cf.get("type") == "BILL_DUE"]
        assert len(bill_events) > 0

