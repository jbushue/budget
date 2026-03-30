from datetime import date
from copy import deepcopy

from .types import BillFrequency, BillType


class Bill:
    """Base class for bills/recurring expenses."""

    def __init__(
        self,
        bill_name: str,
        amount: float,
        due_date: int,  # Day of month (1-31)
        bill_type: BillType = BillType.FIXED,
        frequency: BillFrequency = BillFrequency.MONTHLY,
        due_month: int = None,  # Month (1-12) for yearly/semi-annual bills
        preferred_source_account: str = None,
        preferred_source_bank: str = None
    ):
        """
        Args:
            bill_name: Name of the bill
            amount: Amount due (for floating bills, this is estimated)
            due_date: Day of month when due (1-31)
            bill_type: 'fixed' or 'floating'
            frequency: 'monthly', 'weekly', 'biweekly', etc.
            due_month: Month (1-12) for yearly or semi-annual bills
            preferred_source_account: Preferred account name to pay from
            preferred_source_bank: Preferred bank name to pay from
        """
        if amount <= 0:
            raise ValueError("Bill amount must be positive.")

        if not (1 <= due_date <= 31):
            raise ValueError("Due date must be between 1 and 31.")
        
        if due_month is not None and not (1 <= due_month <= 12):
            raise ValueError("Due month must be between 1 and 12.")

        self.bill_name = bill_name
        self.amount = amount
        self.due_date = due_date  # Day of month
        self.due_month = due_month  # Month for yearly/semi-annual bills

        if isinstance(bill_type, str):
            bill_type = BillType[bill_type.upper()]
        self.bill_type = bill_type

        if isinstance(frequency, str):
            frequency = BillFrequency[frequency.upper()]
        self.frequency = frequency

        # Payment source preferences
        self.preferred_source_account = preferred_source_account
        self.preferred_source_bank = preferred_source_bank

        # Payment tracking
        self.payment_history: list[dict] = []
        self.is_paid_this_period = False

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None):
        """Record that this bill has been paid."""
        if amount_paid is None:
            amount_paid = self.amount

        self.payment_history.append({
            "date": payment_date or date.today(),
            "source_bank": source_bank,
            "source_account": source_account,
            "amount_paid": amount_paid
        })
        self.is_paid_this_period = True

    def reset_period(self):
        """Reset the paid status for the next period (e.g., next month)."""
        self.is_paid_this_period = False

    def get_next_due_date(self, reference_date: date) -> date:
        """Calculate the next due date relative to a reference date."""
        year = reference_date.year
        month = reference_date.month

        # Handle YEARLY frequency with due_month
        if self.frequency == BillFrequency.YEARLY:
            # If due_month not specified, use the same month as reference date
            due_month = self.due_month if self.due_month is not None else month
            
            try:
                next_due = date(year, due_month, self.due_date)
            except ValueError:
                # Handle day > max for that month
                next_due = date(year, due_month, min(self.due_date, 28))
            
            if next_due <= reference_date:
                # Bill already occurred this year, move to next year
                year += 1
                try:
                    next_due = date(year, due_month, self.due_date)
                except ValueError:
                    next_due = date(year, due_month, min(self.due_date, 28))
            
            return next_due

        # Handle SEMI_ANNUAL frequency with due_month
        if self.frequency == BillFrequency.SEMI_ANNUAL:
            # If due_month not specified, use the same month as reference date
            due_month = self.due_month if self.due_month is not None else month
            
            try:
                next_due = date(year, due_month, self.due_date)
            except ValueError:
                next_due = date(year, due_month, min(self.due_date, 28))
            
            if next_due <= reference_date:
                # Try the second occurrence (6 months later)
                second_month = (due_month + 6 - 1) % 12 + 1
                second_year = year if due_month + 6 <= 12 else year + 1
                
                try:
                    next_due = date(second_year, second_month, self.due_date)
                except ValueError:
                    next_due = date(second_year, second_month, min(self.due_date, 28))
                
                if next_due <= reference_date:
                    # Both occurrences have passed, move to next year's first occurrence
                    year += 1
                    try:
                        next_due = date(year, due_month, self.due_date)
                    except ValueError:
                        next_due = date(year, due_month, min(self.due_date, 28))
            
            return next_due

        # Start with the due date day of the current month
        try:
            next_due = date(year, month, self.due_date)
        except ValueError:
            # Handle day > 28/29/30 for months with fewer days
            next_due = date(year, month, min(self.due_date, 28))

            # Move to first day of next month and back one day
            if month == 12:
                next_due = date(year + 1, 1, 1)
            else:
                next_due = date(year, month + 1, 1)

        if next_due <= reference_date:
            # Due date has passed this month, move to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

            try:
                next_due = date(year, month, self.due_date)
            except ValueError:
                # Handle month-end edge cases
                next_due = date(year, month, min(self.due_date, 28))

        return next_due

    def copy(self):
        """Create a deep copy of this bill."""
        return deepcopy(self)

    def __repr__(self):
        status = "PAID" if self.is_paid_this_period else "UNPAID"
        return f"Bill({self.bill_name}, ${self.amount:.2f}, due day {self.due_date}, {status})"


class FloatingBill(Bill):
    """A bill with variable amount (e.g., utilities, groceries)."""

    def __init__(
        self,
        bill_name: str,
        estimated_amount: float,
        due_date: int,
        min_amount: float = None,
        max_amount: float = None,
        frequency: BillFrequency = BillFrequency.MONTHLY,
        due_month: int = None,
        preferred_source_account: str = None,
        preferred_source_bank: str = None
    ):
        """
        Args:
            estimated_amount: Best estimate of the bill amount
            min_amount: Minimum expected amount
            max_amount: Maximum expected amount
            due_month: Month (1-12) for yearly or semi-annual bills
        """
        super().__init__(
            bill_name=bill_name,
            amount=estimated_amount,
            due_date=due_date,
            bill_type=BillType.FLOATING,
            frequency=frequency,
            due_month=due_month,
            preferred_source_account=preferred_source_account,
            preferred_source_bank=preferred_source_bank
        )

        self.min_amount = min_amount or estimated_amount * 0.8
        self.max_amount = max_amount or estimated_amount * 1.2
        self.estimated_amount = estimated_amount
