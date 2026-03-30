"""
Tests for mortgage account functionality.
"""

import pytest
from datetime import date, timedelta
from models.mortgage_account import MortgageAccount
from models.types import MortgageStatus


class TestMortgageAccount:
    """Test MortgageAccount class functionality."""

    def test_mortgage_creation(self):
        """Test creating a mortgage account."""
        mortgage = MortgageAccount(
            account_name="Primary Mortgage",
            original_principal=300000.00,
            interest_rate=6.5,
            loan_term_months=360,
            payment_due_date=1
        )

        assert mortgage.account_name == "Primary Mortgage"
        assert mortgage.original_principal == 300000.00
        assert mortgage.current_principal == 300000.00
        assert mortgage.interest_rate == 6.5
        assert mortgage.loan_term_months == 360
        assert mortgage.payment_due_date == 1
        assert mortgage.status == MortgageStatus.ACTIVE

    def test_mortgage_payment_calculation(self):
        """Test mortgage payment calculation."""
        mortgage = MortgageAccount(
            account_name="Test Mortgage",
            original_principal=200000.00,
            interest_rate=5.0,
            loan_term_months=360,
            payment_due_date=1
        )

        # Should calculate monthly payment
        assert mortgage.total_monthly_payment > 0
        assert mortgage.current_monthly_principal > 0
        assert mortgage.current_monthly_interest > 0

        # Total payment should equal principal + interest + escrow
        expected_total = (mortgage.current_monthly_principal +
                         mortgage.current_monthly_interest +
                         mortgage.escrow.total_monthly)
        assert abs(mortgage.total_monthly_payment - expected_total) < 0.01

    def test_mortgage_payment_application(self):
        """Test applying mortgage payments."""
        mortgage = MortgageAccount(
            account_name="Test Mortgage",
            original_principal=200000.00,
            interest_rate=5.0,
            loan_term_months=360,
            payment_due_date=1
        )

        initial_principal = mortgage.current_principal

        # Make a payment
        mortgage.make_payment()

        # Principal should decrease
        assert mortgage.current_principal < initial_principal
        # Remaining balance should be zero (paid for this month)
        assert mortgage.remaining_balance == 0.00

    def test_mortgage_next_due_date(self):
        """Test calculating next mortgage due date."""
        mortgage = MortgageAccount(
            account_name="Test Mortgage",
            original_principal=200000.00,
            interest_rate=5.0,
            loan_term_months=360,
            payment_due_date=15
        )

        reference_date = date(2024, 1, 10)
        next_due = mortgage.get_next_due_date(reference_date)

        assert next_due == date(2024, 1, 15)  # 15th of current month

        # After due date
        reference_date = date(2024, 1, 20)
        next_due = mortgage.get_next_due_date(reference_date)

        assert next_due == date(2024, 2, 15)  # 15th of next month

    def test_mortgage_escrow_calculation(self):
        """Test mortgage escrow calculations."""
        mortgage = MortgageAccount(
            account_name="Test Mortgage",
            original_principal=250000.00,
            interest_rate=4.5,
            loan_term_months=360,
            payment_due_date=1
        )

        # Escrow should be calculated
        assert mortgage.escrow.property_tax_monthly >= 0
        assert mortgage.escrow.homeowners_insurance_monthly >= 0
        assert mortgage.escrow.total_monthly > 0

    def test_mortgage_status_transitions(self):
        """Test mortgage status changes."""
        mortgage = MortgageAccount(
            account_name="Test Mortgage",
            original_principal=100000.00,  # Small amount for quick payoff
            interest_rate=5.0,
            loan_term_months=360,
            payment_due_date=1
        )

        assert mortgage.status == MortgageStatus.ACTIVE

        # Pay off the mortgage completely
        while mortgage.current_principal > 0:
            mortgage.make_payment()

        # Should be paid off
        assert mortgage.status == MortgageStatus.PAID_OFF

    def test_mortgage_copy(self):
        """Test copying a mortgage account."""
        original = MortgageAccount(
            account_name="Original Mortgage",
            original_principal=300000.00,
            interest_rate=6.5,
            loan_term_months=360,
            payment_due_date=1
        )

        copy = original.copy()

        assert copy.account_name == original.account_name
        assert copy.original_principal == original.original_principal
        assert copy.current_principal == original.current_principal
        assert copy is not original

    def test_mortgage_string_representation(self):
        """Test mortgage string representation."""
        mortgage = MortgageAccount(
            account_name="Primary Mortgage",
            original_principal=300000.00,
            interest_rate=6.5,
            loan_term_months=360,
            payment_due_date=1
        )

        str_repr = str(mortgage)
        assert "Primary Mortgage" in str_repr
        assert "$300000.00" in str_repr
        assert "6.5%" in str_repr


class TestMortgageEscrow:
    """Test mortgage escrow functionality."""

    def test_escrow_initialization(self):
        """Test escrow initialization."""
        from models.mortgage_account import EscrowAccount

        escrow = EscrowAccount(
            property_tax_monthly=300.00,
            homeowners_insurance_monthly=150.00,
            pmi_monthly=0.00,
            hoa_monthly=0.00
        )

        assert escrow.property_tax_monthly == 300.00
        assert escrow.homeowners_insurance_monthly == 150.00
        assert escrow.pmi_monthly == 0.00
        assert escrow.hoa_monthly == 0.00
        assert escrow.total_monthly == 450.00

    def test_escrow_updates(self):
        """Test updating escrow amounts."""
        from models.mortgage_account import EscrowAccount

        escrow = EscrowAccount()

        escrow.property_tax_monthly = 250.00
        escrow.homeowners_insurance_monthly = 125.00
        escrow.hoa_monthly = 50.00

        assert escrow.total_monthly == 425.00


class TestMortgageIntegration:
    """Test mortgage integration with other components."""

    def test_mortgage_with_bank(self, sample_mortgage_bank):
        """Test mortgage account integration with bank."""
        bank = sample_mortgage_bank

        assert "Primary Mortgage" in bank.mortgage_accounts
        mortgage = bank.mortgage_accounts["Primary Mortgage"]

        # Should be accessible through bank methods
        all_mortgages = bank.get_all_mortgage_accounts()
        assert len(all_mortgages) == 1
        assert all_mortgages[0] == mortgage

    def test_mortgage_payment_schedule(self, sample_mortgage_bank):
        """Test mortgage payment scheduling."""
        from models.payment_optimizer import PaymentOptimizer

        bank = sample_mortgage_bank
        optimizer = PaymentOptimizer([bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        mortgage_schedule = optimizer._build_mortgage_schedule(start_date, end_date)

        assert len(mortgage_schedule) > 0

        # Check schedule structure
        entry = mortgage_schedule[0]
        assert "mortgage" in entry
        assert "total_payment" in entry
        assert "due_date" in entry

    def test_mortgage_in_timeline(self, sample_mortgage_bank):
        """Test mortgage payments in timeline simulation."""
        from models.timeline_simulator import TimelineSimulator

        simulator = TimelineSimulator([sample_mortgage_bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        mortgage_events = [e for e in events if e.event_type == "MORTGAGE_PAYMENT"]
        assert len(mortgage_events) == 1
        assert mortgage_events[0].event_date == date(2024, 1, 1)

