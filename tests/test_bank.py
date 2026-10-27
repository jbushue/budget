"""
Tests for bank and account management functionality.
"""

import pytest
from datetime import date, timedelta
from models.bank import Bank
from models.types import AccountType, BankTypes


class TestBank:
    """Test Bank class functionality."""

    def test_bank_creation(self):
        """Test creating a bank with different types."""
        # Traditional bank
        bank = Bank("Chase Bank", bank_type="traditional")
        assert bank.name == "Chase Bank"
        assert bank.bank_type == "traditional"
        assert len(bank.accounts) == 0
        assert len(bank.credit_accounts) == 0
        assert len(bank.mortgage_accounts) == 0

        # Credit issuer
        credit_bank = Bank("Amex", bank_type="credit_issuer")
        assert credit_bank.bank_type == "credit_issuer"

        # Mortgage lender
        mortgage_bank = Bank("Wells Fargo", bank_type="mortgage_lender")
        assert mortgage_bank.bank_type == "mortgage_lender"

    def test_bank_creation_invalid_type(self):
        """Test creating a bank with invalid type - Bank accepts any type string."""
        # Bank class doesn't validate bank_type, it just stores whatever is passed
        bank = Bank("Test Bank", bank_type="invalid_type")
        assert bank.bank_type == "invalid_type"

    def test_add_checking_account(self, sample_bank):
        """Test adding a checking account."""
        bank = sample_bank
        assert "Primary Checking" in bank.accounts
        account = bank.accounts["Primary Checking"]

        assert account.account_name == "Primary Checking"
        assert account.account_type == AccountType.CHECKING
        assert account.balance == 5000.00
        assert account.interest_rate == 0.01

    def test_add_savings_account(self, sample_bank):
        """Test adding a savings account."""
        bank = sample_bank
        assert "Emergency Fund" in bank.accounts
        account = bank.accounts["Emergency Fund"]

        assert account.account_name == "Emergency Fund"
        assert account.account_type == AccountType.SAVINGS
        assert account.balance == 10000.00
        assert account.interest_rate == 4.5
        assert account.interest_accrual_date == 1

    def test_account_deposit(self, sample_bank):
        """Test depositing money into an account."""
        bank = sample_bank
        account = bank.accounts["Primary Checking"]

        initial_balance = account.balance
        account.deposit(1000.00, description="Test deposit")

        assert account.balance == initial_balance + 1000.00
        assert len(account.transaction_history) == 1
        assert account.transaction_history[0]["amount"] == 1000.00
        assert account.transaction_history[0]["description"] == "Test deposit"

    def test_account_withdraw(self, sample_bank):
        """Test withdrawing money from an account."""
        bank = sample_bank
        account = bank.accounts["Primary Checking"]

        initial_balance = account.balance
        account.withdraw(500.00, description="Test withdrawal")

        assert account.balance == initial_balance - 500.00
        assert len(account.transaction_history) == 1
        assert account.transaction_history[0]["amount"] == -500.00

    def test_account_overdraft(self, sample_bank):
        """Test overdraft protection."""
        bank = sample_bank
        account = bank.accounts["Primary Checking"]

        # Try to withdraw more than balance
        with pytest.raises(ValueError, match="Insufficient funds"):
            account.withdraw(10000.00)

        # Balance should remain unchanged
        assert account.balance == 5000.00

    def test_account_interest_accrual(self, sample_bank):
        """Test interest accrual on savings account."""
        bank = sample_bank
        savings = bank.accounts["Emergency Fund"]

        # Accrue interest for one month (4.5% APR)
        monthly_rate = 4.5 / 12 / 100  # Convert to decimal
        expected_interest = savings.balance * monthly_rate

        savings.accrue_interest()

        assert savings.balance == 10000.00 + expected_interest
        assert len(savings.transaction_history) == 1
        assert "Interest" in savings.transaction_history[0]["description"]

    def test_get_all_accounts(self, sample_bank):
        """Test getting all accounts from a bank."""
        bank = sample_bank
        all_accounts = bank.get_all_accounts()

        assert len(all_accounts) == 2
        account_names = [acc.account_name for acc in all_accounts]
        assert "Primary Checking" in account_names
        assert "Emergency Fund" in account_names

    def test_bank_copy(self, sample_bank):
        """Test copying a bank."""
        original = sample_bank
        copy = original.copy()

        assert copy.name == original.name
        assert copy.bank_type == original.bank_type
        assert len(copy.accounts) == len(original.accounts)

        # Verify accounts are copied (not the same objects)
        assert copy.accounts["Primary Checking"] is not original.accounts["Primary Checking"]
        assert copy.accounts["Primary Checking"].balance == original.accounts["Primary Checking"].balance


class TestCreditCardAccount:
    """Test credit card account functionality."""

    def test_add_credit_account(self, sample_credit_bank):
        """Test adding a credit card account."""
        bank = sample_credit_bank
        assert "Rewards Card" in bank.credit_accounts
        card = bank.credit_accounts["Rewards Card"]

        assert card.account_name == "Rewards Card"
        assert card.credit_limit == 10000.00
        assert card.balance == 0.00  # Start with no balance
        assert card.interest_rate == 18.5
        assert card.payment_due_date == 15
        assert card.statement_date == 10

    def test_credit_charge(self, sample_credit_bank):
        """Test charging to a credit card."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        card.make_purchase(500.00, description="Test purchase")

        assert card.balance == 500.00
        assert len(card.transaction_history) == 1
        assert card.transaction_history[0]["amount"] == 500.00
        assert card.transaction_history[0]["description"] == "Test purchase"

    def test_credit_payment(self, sample_credit_bank):
        """Test making payments on a credit card."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # First charge
        card.make_purchase(500.00)
        assert card.balance == 500.00

        # Then pay
        card.make_payment(300.00, description="Test payment")
        assert card.balance == 200.00
        assert len(card.transaction_history) == 2

    def test_credit_over_limit(self, sample_credit_bank):
        """Test charging over credit limit."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        with pytest.raises(ValueError, match="exceeds available credit"):
            card.make_purchase(15000.00)  # Over 10k limit

        assert card.balance == 0.00  # Should remain unchanged

    def test_credit_interest_accrual(self, sample_credit_bank):
        """Test interest accrual on credit card."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Charge and move to next month
        card.make_purchase(1000.00)
        card.accrue_interest()

        # Interest should be accrued (18.5% APR)
        monthly_rate = 18.5 / 12 / 100
        expected_interest = 1000.00 * monthly_rate

        assert card.balance == 1000.00 + expected_interest
        assert len(card.transaction_history) == 2  # Charge + interest

    def test_get_all_credit_accounts(self, sample_credit_bank):
        """Test getting all credit accounts."""
        bank = sample_credit_bank
        credit_accounts = bank.get_all_credit_accounts()

        assert len(credit_accounts) == 1
        assert credit_accounts[0].account_name == "Rewards Card"


class TestMortgageAccount:
    """Test mortgage account functionality."""

    def test_add_mortgage_account(self, sample_mortgage_bank):
        """Test adding a mortgage account."""
        bank = sample_mortgage_bank
        assert "Primary Mortgage" in bank.mortgage_accounts
        mortgage = bank.mortgage_accounts["Primary Mortgage"]

        assert mortgage.account_name == "Primary Mortgage"
        assert mortgage.original_principal == 300000.00
        assert mortgage.current_principal == 300000.00  # Starts with full amount
        assert mortgage.interest_rate == 6.5
        assert mortgage.loan_term_months == 360
        assert mortgage.payment_due_date == 1

    def test_mortgage_payment_calculation(self, sample_mortgage_bank):
        """Test mortgage payment calculation."""
        bank = sample_mortgage_bank
        mortgage = bank.mortgage_accounts["Primary Mortgage"]

        # Should have calculated monthly payment
        assert mortgage.total_monthly_payment > 0
        assert mortgage.current_monthly_principal > 0
        assert mortgage.current_monthly_interest > 0

        # Total payment should equal principal + interest + escrow
        expected_total = (mortgage.current_monthly_principal +
                         mortgage.current_monthly_interest +
                         mortgage.escrow.total_monthly)
        assert abs(mortgage.total_monthly_payment - expected_total) < 0.01

    def test_mortgage_payment_application(self, sample_mortgage_bank):
        """Test applying a mortgage payment."""
        bank = sample_mortgage_bank
        mortgage = bank.mortgage_accounts["Primary Mortgage"]

        initial_principal = mortgage.current_principal
        initial_balance = mortgage.total_monthly_payment

        # Make a payment
        mortgage.make_payment()

        # Principal should decrease
        assert mortgage.current_principal < initial_principal
        # Verify payment was recorded
        assert mortgage.is_paid_this_period == True

    def test_mortgage_next_due_date(self, sample_mortgage_bank):
        """Test calculating next mortgage due date."""
        bank = sample_mortgage_bank
        mortgage = bank.mortgage_accounts["Primary Mortgage"]

        today = date.today()
        next_due = mortgage.get_next_due_date(today)

        # get_next_due_date returns the next due date AFTER the reference_date.
        # The mortgage due date is the 1st.  If today is before the 1st this
        # month we expect this month's 1st; otherwise next month's 1st.
        if today.day < mortgage.payment_due_date:
            expected = date(today.year, today.month, mortgage.payment_due_date)
        else:
            if today.month == 12:
                expected = date(today.year + 1, 1, mortgage.payment_due_date)
            else:
                expected = date(today.year, today.month + 1, mortgage.payment_due_date)

        assert next_due == expected

    def test_get_all_mortgage_accounts(self, sample_mortgage_bank):
        """Test getting all mortgage accounts."""
        bank = sample_mortgage_bank
        mortgage_accounts = bank.get_all_mortgage_accounts()

        assert len(mortgage_accounts) == 1
        assert mortgage_accounts[0].account_name == "Primary Mortgage"


class TestBankIntegration:
    """Test bank integration and cross-account operations."""

    def test_multiple_account_types(self):
        """Test bank with multiple account types."""
        bank = Bank("Multi-Type Bank")

        # Add different account types
        bank.add_account("checking", "Checking", 1000.00)
        bank.add_account("savings", "Savings", 5000.00)
        bank.add_credit_account("Credit Card", 5000.00)
        bank.add_mortgage_account("Mortgage", 200000.00)

        assert len(bank.accounts) == 2  # checking + savings
        assert len(bank.credit_accounts) == 1
        assert len(bank.mortgage_accounts) == 1

        all_accounts = bank.get_all_accounts()
        assert len(all_accounts) == 2  # Only traditional accounts

        all_credit = bank.get_all_credit_accounts()
        assert len(all_credit) == 1

        all_mortgage = bank.get_all_mortgage_accounts()
        assert len(all_mortgage) == 1

    def test_bank_string_representation(self, sample_bank):
        """Test bank string representation."""
        bank = sample_bank
        str_repr = str(bank)

        assert "Test Bank" in str_repr
        assert "bank accounts" in str_repr
        assert "credit accounts" in str_repr

