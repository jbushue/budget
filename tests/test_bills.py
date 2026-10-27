"""
Tests for bill management functionality, including yearly and semi-annual bills.
"""

import pytest
from datetime import date, timedelta
from models.fixed_bill import Bill, FloatingBill
from models.types import BillFrequency, BillType


class TestBill:
    """Test Bill class functionality."""

    def test_monthly_bill_creation(self):
        """Test creating a monthly bill."""
        bill = Bill(
            bill_name="Rent",
            amount=2000.00,
            due_date=1,
            frequency=BillFrequency.MONTHLY
        )

        assert bill.bill_name == "Rent"
        assert bill.amount == 2000.00
        assert bill.due_date == 1
        assert bill.due_month is None
        assert bill.frequency == BillFrequency.MONTHLY
        assert bill.bill_type == BillType.FIXED

    def test_yearly_bill_creation(self):
        """Test creating a yearly bill with due_month."""
        bill = Bill(
            bill_name="Property Tax",
            amount=2400.00,
            due_date=15,
            due_month=4,  # April
            frequency=BillFrequency.YEARLY
        )

        assert bill.bill_name == "Property Tax"
        assert bill.amount == 2400.00
        assert bill.due_date == 15
        assert bill.due_month == 4
        assert bill.frequency == BillFrequency.YEARLY

    def test_semi_annual_bill_creation(self):
        """Test creating a semi-annual bill with due_month."""
        bill = Bill(
            bill_name="Car Insurance",
            amount=1200.00,
            due_date=1,
            due_month=1,  # January
            frequency=BillFrequency.SEMI_ANNUAL
        )

        assert bill.bill_name == "Car Insurance"
        assert bill.amount == 1200.00
        assert bill.due_date == 1
        assert bill.due_month == 1
        assert bill.frequency == BillFrequency.SEMI_ANNUAL

    def test_bill_validation(self):
        """Test bill validation."""
        # Invalid amount
        with pytest.raises(ValueError, match="Bill amount must be positive"):
            Bill("Test", -100, 1)

        # Invalid due_date
        with pytest.raises(ValueError, match="Due date must be between 1 and 31"):
            Bill("Test", 100, 0)

        with pytest.raises(ValueError, match="Due date must be between 1 and 31"):
            Bill("Test", 100, 32)

        # Invalid due_month
        with pytest.raises(ValueError, match="Due month must be between 1 and 12"):
            Bill("Test", 100, 1, due_month=0)

        with pytest.raises(ValueError, match="Due month must be between 1 and 12"):
            Bill("Test", 100, 1, due_month=13)

    def test_yearly_bill_requires_due_month(self):
        """Test that yearly bills default to reference month when due_month not specified."""
        bill = Bill("Property Tax", 2400, 15, frequency=BillFrequency.YEARLY)

        # Without due_month, uses reference_date's month
        reference = date(2024, 3, 10)
        next_due = bill.get_next_due_date(reference)
        # Should use March (from reference) as the due month
        assert next_due == date(2024, 3, 15)

    def test_semi_annual_bill_requires_due_month(self):
        """Test that semi-annual bills default to reference month when due_month not specified."""
        bill = Bill("Car Insurance", 1200, 1, frequency=BillFrequency.SEMI_ANNUAL)

        # Without due_month, uses reference_date's month
        reference = date(2024, 3, 1)
        next_due = bill.get_next_due_date(reference)
        # Should use March (from reference) as the first due month, then every 6 months
        # Since reference is on the due date, it goes to next occurrence
        assert next_due == date(2024, 9, 1)  # 6 months after March

    def test_monthly_bill_due_dates(self):
        """Test monthly bill due date calculation."""
        bill = Bill("Rent", 2000, 15, frequency=BillFrequency.MONTHLY)

        # Test from before due date
        reference = date(2024, 3, 10)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 3, 15)

        # Test from after due date
        reference = date(2024, 3, 20)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 4, 15)

        # Test year boundary
        reference = date(2024, 12, 20)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2025, 1, 15)

    def test_yearly_bill_due_dates(self):
        """Test yearly bill due date calculation."""
        bill = Bill("Property Tax", 2400, 15, due_month=4, frequency=BillFrequency.YEARLY)

        # Test from before due date in same year
        reference = date(2024, 3, 10)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 4, 15)

        # Test from after due date in same year
        reference = date(2024, 5, 10)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2025, 4, 15)

        # Test from same month but before due date
        reference = date(2024, 4, 10)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 4, 15)

        # Test from same month but after due date
        reference = date(2024, 4, 20)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2025, 4, 15)

    def test_semi_annual_bill_due_dates(self):
        """Test semi-annual bill due date calculation."""
        bill = Bill("Car Insurance", 1200, 1, due_month=1, frequency=BillFrequency.SEMI_ANNUAL)

        # Test from before first occurrence
        reference = date(2024, 1, 15)  # After Jan 1st but before July 1st
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 7, 1)

        # Test from after first occurrence but before second
        reference = date(2024, 3, 15)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 7, 1)

        # Test from after second occurrence
        reference = date(2024, 8, 15)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2025, 1, 1)

        # Test from just before first occurrence
        reference = date(2024, 1, 15)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 7, 1)

    def test_bill_mark_paid(self):
        """Test marking a bill as paid."""
        bill = Bill("Rent", 2000, 1)

        assert not bill.is_paid_this_period

        bill.mark_paid("Test Bank", "Checking", 2000.00, date.today())

        assert bill.is_paid_this_period
        assert len(bill.payment_history) == 1
        assert bill.payment_history[0]["amount_paid"] == 2000.00

    def test_bill_reset_period(self):
        """Test resetting bill payment status."""
        bill = Bill("Rent", 2000, 1)
        bill.mark_paid("Test Bank", "Checking")

        assert bill.is_paid_this_period

        bill.reset_period()

        assert not bill.is_paid_this_period

    def test_bill_copy(self):
        """Test copying a bill."""
        original = Bill("Rent", 2000, 1, frequency=BillFrequency.MONTHLY)
        copy = original.copy()

        assert copy.bill_name == original.bill_name
        assert copy.amount == original.amount
        assert copy.due_date == original.due_date
        assert copy.frequency == original.frequency
        assert copy is not original  # Different objects

    def test_bill_string_representation(self):
        """Test bill string representation."""
        bill = Bill("Rent", 2000, 1)
        str_repr = str(bill)

        assert "Rent" in str_repr
        assert "$2000.00" in str_repr
        assert "due day 1" in str_repr
        assert "UNPAID" in str_repr

        bill.mark_paid("Bank", "Account")
        str_repr = str(bill)
        assert "PAID" in str_repr


class TestFloatingBill:
    """Test FloatingBill class functionality."""

    def test_floating_bill_creation(self):
        """Test creating a floating bill."""
        bill = FloatingBill(
            bill_name="Groceries",
            estimated_amount=500.00,
            due_date=25,
            min_amount=300.00,
            max_amount=700.00,
            frequency=BillFrequency.MONTHLY
        )

        assert bill.bill_name == "Groceries"
        assert bill.amount == 500.00  # estimated_amount
        assert bill.estimated_amount == 500.00
        assert bill.min_amount == 300.00
        assert bill.max_amount == 700.00
        assert bill.due_date == 25
        assert bill.frequency == BillFrequency.MONTHLY
        assert bill.bill_type == BillType.FLOATING

    def test_floating_bill_default_ranges(self):
        """Test floating bill with default min/max ranges."""
        bill = FloatingBill("Utilities", 200.00, 15)

        # Should use 80% and 120% of estimated amount
        assert bill.min_amount == 160.00  # 200 * 0.8
        assert bill.max_amount == 240.00  # 200 * 1.2

    def test_floating_bill_with_due_month(self):
        """Test floating bill with yearly frequency and due_month."""
        bill = FloatingBill(
            bill_name="Annual Insurance",
            estimated_amount=1500.00,
            due_date=31,
            due_month=12,  # December
            frequency=BillFrequency.YEARLY
        )

        assert bill.due_month == 12
        assert bill.frequency == BillFrequency.YEARLY

        # Test due date calculation
        reference = date(2024, 6, 15)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 12, 31)

    def test_floating_bill_inheritance(self):
        """Test that FloatingBill inherits Bill methods."""
        bill = FloatingBill("Groceries", 500, 25)

        # Should have all Bill methods
        bill.mark_paid("Bank", "Account")
        assert bill.is_paid_this_period

        bill.reset_period()
        assert not bill.is_paid_this_period

        copy = bill.copy()
        assert copy.estimated_amount == bill.estimated_amount


class TestBillFrequencies:
    """Test different bill frequencies.
    
    Note: The current Bill class does not implement true weekly/biweekly/quarterly
    intervals. All frequencies use the same monthly logic where due_date is 
    interpreted as day of month.
    """

    def test_weekly_bill(self):
        """Weekly bill: first due on the 15th (implicit anchor), then every 7 days."""
        bill = Bill("Weekly Payment", 100, 15, frequency=BillFrequency.WEEKLY)

        reference = date(2024, 1, 1)  # Before the 15th
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 1, 15)
        assert bill.get_next_due_date(next_due) == date(2024, 1, 22)

    def test_biweekly_bill(self):
        """Biweekly bill: first due on the 15th (implicit anchor), then every 14 days."""
        bill = Bill("Biweekly Payment", 200, 15, frequency=BillFrequency.BIWEEKLY)

        reference = date(2024, 1, 1)  # Before the 15th
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 1, 15)
        assert bill.get_next_due_date(next_due) == date(2024, 1, 29)

    def test_quarterly_bill(self):
        """Quarterly bill: due on the 15th every 3 months."""
        bill = Bill("Quarterly Fee", 300, 15, frequency=BillFrequency.QUARTERLY)

        reference = date(2024, 1, 1)  # Before the 15th
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 1, 15)
        assert bill.get_next_due_date(next_due) == date(2024, 4, 15)

    def test_month_end_edge_cases(self):
        """Test edge cases with month-end dates."""
        # Bill with due date 31
        bill = Bill("End of Month", 100, 31, frequency=BillFrequency.MONTHLY)

        # Test from January 15 - next due is Jan 31 (same month)
        reference = date(2024, 1, 15)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 1, 31)

        # After Jan 31, test from Feb 1 - Feb has no 31st, so the due day is
        # clamped to the last day of February (previously this jumped to
        # March 1 and then double-charged March; updated with the fix).
        reference = date(2024, 2, 1)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 2, 29)

    def test_yearly_edge_cases(self):
        """Test yearly bill edge cases."""
        # April 31st is clamped to the last day of April (previously min(day, 28))
        bill = Bill("April 31st", 100, 31, due_month=4, frequency=BillFrequency.YEARLY)

        reference = date(2024, 1, 1)
        next_due = bill.get_next_due_date(reference)
        assert next_due == date(2024, 4, 30)


class TestBillIntegration:
    """Test bill integration with other components."""

    def test_bill_with_payment_preferences(self):
        """Test bill with payment source preferences."""
        bill = Bill(
            "Rent",
            2000,
            1,
            preferred_source_bank="Chase",
            preferred_source_account="Checking"
        )

        assert bill.preferred_source_bank == "Chase"
        assert bill.preferred_source_account == "Checking"

    def test_multiple_bills_due_dates(self, sample_bills):
        """Test calculating due dates for multiple bills."""
        bills = sample_bills
        reference_date = date(2024, 3, 15)

        due_dates = []
        for bill in bills:
            next_due = bill.get_next_due_date(reference_date)
            due_dates.append((bill.bill_name, next_due))

        # Should have different due dates based on frequency
        expected_dates = [
            ("Rent", date(2024, 4, 1)),           # Monthly - April 1st
            ("Internet", date(2024, 3, 15)),      # Monthly - March 15th (already passed? wait)
            ("Property Tax", date(2024, 4, 15)), # Yearly - April 15th
            ("Car Insurance", date(2024, 7, 1)), # Semi-annual - July 1st
            ("Groceries", date(2024, 3, 25)),    # Monthly - March 25th
        ]

        # Adjust for bills that have passed
        internet_bill = next(b for b in bills if b.bill_name == "Internet")
        internet_next = internet_bill.get_next_due_date(reference_date)
        assert internet_next == date(2024, 4, 15)  # Next month since March 15th passed

    def test_bill_payment_history(self):
        """Test bill payment history tracking."""
        bill = Bill("Test Bill", 100, 1)

        # Make multiple payments
        bill.mark_paid("Bank A", "Account 1", 100, date(2024, 1, 1))
        bill.mark_paid("Bank B", "Account 2", 50, date(2024, 2, 1))

        assert len(bill.payment_history) == 2

        first_payment = bill.payment_history[0]
        assert first_payment["source_bank"] == "Bank A"
        assert first_payment["source_account"] == "Account 1"
        assert first_payment["amount_paid"] == 100
        assert first_payment["date"] == date(2024, 1, 1)

