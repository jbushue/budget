"""
Shared test fixtures and configuration for the test suite.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

# Import all models
from models.bank import Bank
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource, IncomeFrequency
from models.finance_manager import FinanceManager
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer
from models.types import BillFrequency, BillType, AccountType, BankTypes
from models.mortgage_account import MortgageAccount
from models.credit_card_account import CreditAccount, PromoOffer
from models.data_import_export import DataImportExport


@pytest.fixture
def sample_bank():
    """Create a sample bank with accounts."""
    bank = Bank("Test Bank", bank_type="traditional")

    # Add checking account
    bank.add_account(
        account_type="checking",
        account_name="Primary Checking",
        starting_balance=5000.00,
        interest_rate=0.01
    )

    # Add savings account
    bank.add_account(
        account_type="savings",
        account_name="Emergency Fund",
        starting_balance=10000.00,
        interest_rate=4.5,
        interest_accrual_date=1
    )

    return bank


@pytest.fixture
def sample_credit_bank():
    """Create a sample credit card bank."""
    bank = Bank("Credit Bank", bank_type="credit_issuer")

    # Add credit card
    bank.add_credit_account(
        account_name="Rewards Card",
        credit_limit=10000.00,
        interest_rate=18.5,
        payment_due_date=15,
        statement_date=10
    )

    return bank


@pytest.fixture
def sample_mortgage_bank():
    """Create a sample mortgage bank."""
    bank = Bank("Mortgage Bank", bank_type="mortgage_lender")

    # Add mortgage
    bank.add_mortgage_account(
        account_name="Primary Mortgage",
        original_principal=300000.00,
        current_principal=300000.00,
        interest_rate=6.5,
        loan_term_months=360,
        payment_due_date=1
    )

    return bank


@pytest.fixture
def sample_bills():
    """Create sample bills of different types."""
    return [
        # Monthly bills
        Bill(
            bill_name="Rent",
            amount=2000.00,
            due_date=1,
            frequency=BillFrequency.MONTHLY
        ),
        Bill(
            bill_name="Internet",
            amount=80.00,
            due_date=15,
            frequency=BillFrequency.MONTHLY
        ),

        # Yearly bill with due_month
        Bill(
            bill_name="Property Tax",
            amount=2400.00,
            due_date=15,
            due_month=4,  # April
            frequency=BillFrequency.YEARLY
        ),

        # Semi-annual bill with due_month
        Bill(
            bill_name="Car Insurance",
            amount=1200.00,
            due_date=1,
            due_month=1,  # January
            frequency=BillFrequency.SEMI_ANNUAL
        ),

        # Floating bill
        FloatingBill(
            bill_name="Groceries",
            estimated_amount=500.00,
            due_date=25,
            min_amount=300.00,
            max_amount=700.00,
            frequency=BillFrequency.MONTHLY
        )
    ]


@pytest.fixture
def sample_income():
    """Create sample income sources."""
    return [
        IncomeSource(
            source_name="Primary Salary",
            amount=5000.00,
            frequency=IncomeFrequency.MONTHLY,
            pay_date=[1]
        ),
        IncomeSource(
            source_name="Side Income",
            amount=1000.00,
            frequency=IncomeFrequency.QUARTERLY,
            pay_date=[15]
        )
    ]


@pytest.fixture
def sample_finance_manager(sample_bank, sample_credit_bank, sample_mortgage_bank, sample_bills, sample_income):
    """Create a complete finance manager setup."""
    banks = [sample_bank, sample_credit_bank, sample_mortgage_bank]
    return FinanceManager(banks, sample_income, sample_bills)


@pytest.fixture
def sample_date_range():
    """Create a sample date range for testing."""
    start_date = date.today()
    end_date = start_date + timedelta(days=90)  # 3 months
    return start_date, end_date

