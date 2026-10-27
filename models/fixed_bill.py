from datetime import date
from copy import deepcopy

from .types import BillFrequency, BillType
from .date_utils import add_months, clamped_date, next_by_days, next_by_months


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
        preferred_source_bank: str = None,
        _skip_amount_validation: bool = False,
        start_date: date | None = None,
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
            _skip_amount_validation: Internal flag for AccountLinkedBill (allows amount=0)
            start_date: Optional anchor (first due date) for non-monthly
                frequencies — weekly/biweekly step 7/14 days from it,
                quarterly/semi-annual/yearly step months from it, and a
                'once' bill is due only on it. Ignored for monthly bills.
        """
        if not _skip_amount_validation and amount <= 0:
            raise ValueError("Bill amount must be positive.")

        if not (1 <= due_date <= 31):
            raise ValueError("Due date must be between 1 and 31.")
        
        if due_month is not None and not (1 <= due_month <= 12):
            raise ValueError("Due month must be between 1 and 12.")

        self.bill_name = bill_name
        self.amount = amount
        self.due_date = due_date  # Day of month
        self.due_month = due_month  # Month for yearly/semi-annual bills
        self.start_date = start_date  # Anchor for non-monthly frequencies

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
        self.carryover_balance: float = 0.0  # Underpayment carried to next period

    @property
    def effective_amount(self) -> float:
        """Amount actually due this period, including any carryover from underpayment."""
        return self.amount + self.carryover_balance

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None):
        """Record that this bill has been paid.
        
        If amount_paid differs from effective_amount, the difference becomes
        carryover for the next period (positive = still owed, negative = credit).
        """
        due_amount = self.effective_amount
        if amount_paid is None:
            amount_paid = due_amount

        # Calculate carryover: positive means underpaid, negative means overpaid (credit)
        self.carryover_balance = max(0.0, round(due_amount - amount_paid, 2))

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

    # Month step for month-based frequencies
    _MONTH_STEPS = {
        BillFrequency.QUARTERLY: 3,
        BillFrequency.SEMI_ANNUAL: 6,
        BillFrequency.YEARLY: 12,
    }
    # Day step for day-based frequencies
    _DAY_STEPS = {
        BillFrequency.WEEKLY: 7,
        BillFrequency.BIWEEKLY: 14,
    }

    def amount_on(self, reference_date: date = None) -> float:
        """Amount due on a given date (static for regular bills)."""
        return self.amount

    def _get_implicit_anchor(self, reference_date: date) -> date:
        """
        Fallback first occurrence for WEEKLY / BIWEEKLY / ONCE bills without a
        ``start_date``.

        The anchor is the first date strictly after the *first* reference date
        this bill is asked about that falls on ``due_date`` (clamped to month
        length). It is remembered on the instance so every later lookup uses
        the same cycle - e.g. a simulation starting Jan 1 (reference Dec 31)
        anchors a weekly bill due on the 5th at Jan 5 and repeats every 7 days.
        """
        anchor = getattr(self, '_implicit_anchor', None)
        if anchor is None:
            anchor = clamped_date(reference_date.year, reference_date.month, self.due_date)
            if anchor <= reference_date:
                y, m = add_months(reference_date.year, reference_date.month, 1)
                anchor = clamped_date(y, m, self.due_date)
            self._implicit_anchor = anchor
        return anchor

    def _get_implicit_phase_month(self, reference_date: date) -> tuple[int, int]:
        """
        Fallback phase month for QUARTERLY / SEMI_ANNUAL / YEARLY bills with
        neither ``start_date`` nor ``due_month``: the month of the *first*
        reference date this bill is asked about (remembered on the instance,
        so a yearly bill does not drift into a monthly one).
        """
        phase = getattr(self, '_implicit_phase_month', None)
        if phase is None:
            phase = (reference_date.year, reference_date.month)
            self._implicit_phase_month = phase
        return phase

    def get_next_due_date(self, reference_date: date) -> date:
        """
        Calculate the next due date strictly after ``reference_date``.

        Frequency handling:
        - MONTHLY: ``due_date`` of every month (clamped to month length, so a
          bill due on the 31st falls on Feb 28/29, Apr 30, ...).
        - WEEKLY / BIWEEKLY: every 7 / 14 days from ``start_date``. Without a
          ``start_date`` the cycle is anchored on the first ``due_date`` day
          after the first reference date (see ``_get_implicit_anchor``).
        - QUARTERLY / SEMI_ANNUAL / YEARLY: every 3 / 6 / 12 months from
          ``start_date`` (keeping its day of month, clamped). Without a
          ``start_date`` the cycle is phased on ``due_month`` (day
          ``due_date``); without either, on the month of the first reference
          date (see ``_get_implicit_phase_month``).
        - ONCE: a single occurrence on ``start_date`` (or the implicit
          anchor). Once it has passed, ``date.max`` is returned.

        With an explicit ``start_date`` there are no occurrences before it.
        """
        frequency = self.frequency
        start = getattr(self, 'start_date', None)

        if frequency == BillFrequency.ONCE:
            occurrence = start or self._get_implicit_anchor(reference_date)
            return occurrence if occurrence > reference_date else date.max

        if frequency in self._DAY_STEPS:
            step = self._DAY_STEPS[frequency]
            anchor = start if start is not None else self._get_implicit_anchor(reference_date)
            return next_by_days(anchor, step, reference_date, allow_before=False)

        if frequency in self._MONTH_STEPS:
            step = self._MONTH_STEPS[frequency]
            if start is not None:
                return next_by_months(start.year, start.month, start.day, step,
                                      reference_date, allow_before=False)
            if self.due_month is not None:
                return next_by_months(reference_date.year, self.due_month, self.due_date, step,
                                      reference_date)
            phase_year, phase_month = self._get_implicit_phase_month(reference_date)
            return next_by_months(phase_year, phase_month, self.due_date, step, reference_date)

        # MONTHLY (default)
        return next_by_months(reference_date.year, reference_date.month, self.due_date, 1,
                              reference_date)

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
        preferred_source_bank: str = None,
        start_date: date | None = None,
    ):
        """
        Args:
            estimated_amount: Best estimate of the bill amount
            min_amount: Minimum expected amount
            max_amount: Maximum expected amount
            due_month: Month (1-12) for yearly or semi-annual bills
            start_date: Optional anchor for non-monthly frequencies (see Bill)
        """
        super().__init__(
            bill_name=bill_name,
            amount=estimated_amount,
            due_date=due_date,
            bill_type=BillType.FLOATING,
            frequency=frequency,
            due_month=due_month,
            preferred_source_account=preferred_source_account,
            preferred_source_bank=preferred_source_bank,
            start_date=start_date,
        )

        self.min_amount = min_amount or estimated_amount * 0.8
        self.max_amount = max_amount or estimated_amount * 1.2
        self.estimated_amount = estimated_amount
        self._actual_amount: float | None = None  # Set when the real bill arrives
        self.amount_history: list[float] = []  # Past actual amounts for averaging

    def set_actual_amount(self, actual_amount: float):
        """
        Set the actual amount for the next bill payment.
        Call this when the real bill arrives and you know the exact amount.
        The amount resets to the estimate after the bill is marked paid.
        """
        if actual_amount <= 0:
            raise ValueError("Actual amount must be positive.")
        self._actual_amount = actual_amount
        self.amount = actual_amount

    def reset_to_estimate(self):
        """Reset the amount back to the estimate (called after payment or manually)."""
        self._actual_amount = None
        self.amount = self.estimated_amount

    @property
    def has_actual_amount(self) -> bool:
        """Whether an actual amount has been set for the next payment."""
        return self._actual_amount is not None

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None):
        """Record payment, update history, recalculate estimate, then reset for next period."""
        paid_amount = amount_paid if amount_paid is not None else self.amount
        super().mark_paid(source_bank, source_account, paid_amount, payment_date)

        # Record the actual amount paid into history
        if paid_amount > 0:
            self.amount_history.append(round(paid_amount, 2))
            # Keep last 12 entries
            if len(self.amount_history) > 12:
                self.amount_history = self.amount_history[-12:]
            # Recalculate estimate from history
            self._recalculate_estimate()

        # Reset to the (possibly updated) estimate for next period
        self._actual_amount = None
        self.amount = self.estimated_amount

    def _recalculate_estimate(self):
        """
        Recalculate the estimated amount based on the rolling average
        of the last 6 actual payments. Also updates min/max from history.
        """
        if not self.amount_history:
            return

        # Use last 6 entries for the average
        recent = self.amount_history[-6:]
        self.estimated_amount = round(sum(recent) / len(recent), 2)

        # Update min/max from full history
        self.min_amount = min(self.amount_history)
        self.max_amount = max(self.amount_history)


class AccountLinkedBill(Bill):
    """
    A bill that is automatically generated from an account (credit card, mortgage, HELOC).
    
    The amount is dynamically resolved from the linked account's current state:
    - Credit cards: calculate_minimum_payment()
    - Mortgages: total_monthly_payment
    - HELOCs: calculate_minimum_payment()
    
    When mark_paid() is called, it also calls the linked account's make_payment()
    and sets the account's is_paid_this_period flag.
    """

    def __init__(
        self,
        linked_account,
        linked_bank_name: str,
        linked_account_type: str,  # 'credit', 'mortgage', 'heloc'
        bill_type: BillType = BillType.CREDIT_PAYMENT,
        preferred_source_account: str = None,
        preferred_source_bank: str = None,
    ):
        """
        Args:
            linked_account: The CreditAccount, MortgageAccount, or HELOCAccount instance
            linked_bank_name: Name of the bank that holds this account
            linked_account_type: 'credit', 'mortgage', or 'heloc'
            bill_type: BillType enum value
            preferred_source_account: Preferred account name to pay from
            preferred_source_bank: Preferred bank name to pay from
        """
        self.linked_account = linked_account
        self.linked_bank_name = linked_bank_name
        self.linked_account_type = linked_account_type

        # Initialize private tracking field before super().__init__ sets is_paid_this_period
        self._is_paid_this_period = False

        # Build a unique name for this linked bill
        bill_name = f"[Auto] {linked_account.account_name} Payment"

        # Build account_link_key for identification
        self.account_link_key = f"{linked_account_type}:{linked_bank_name}:{linked_account.account_name}"

        # Get the due date from the linked account
        due_date = getattr(linked_account, 'payment_due_date', None) or 1

        # Resolve preferred source from account defaults
        if preferred_source_bank is None:
            preferred_source_bank = getattr(linked_account, 'preferred_source_bank', None)
        if preferred_source_account is None:
            preferred_source_account = getattr(linked_account, 'preferred_source_account', None)

        # Get the initial amount (may be 0 for zero-balance credit cards)
        initial_amount = self._resolve_amount_from_account(linked_account, linked_account_type)

        # Bill.__init__ resets is_paid_this_period, which would clobber the
        # linked account's flag through our setter — remember and restore it.
        was_paid = getattr(linked_account, 'is_paid_this_period', False)

        super().__init__(
            bill_name=bill_name,
            amount=initial_amount,
            due_date=due_date,
            bill_type=bill_type,
            frequency=BillFrequency.MONTHLY,
            preferred_source_account=preferred_source_account,
            preferred_source_bank=preferred_source_bank,
            _skip_amount_validation=True,
        )
        self.is_paid_this_period = was_paid

    @staticmethod
    def _resolve_amount_from_account(account, account_type: str, reference_date=None) -> float:
        """Resolve the current payment amount from the linked account."""
        if account_type == 'credit':
            # CreditAccount.calculate_minimum_payment accepts reference_date
            try:
                return account.calculate_minimum_payment(reference_date=reference_date)
            except TypeError:
                return account.calculate_minimum_payment()
        elif account_type == 'mortgage':
            return account.total_monthly_payment
        elif account_type == 'heloc':
            # HELOCAccount.calculate_minimum_payment accepts as_of (phase depends on date)
            try:
                return account.calculate_minimum_payment(as_of=reference_date)
            except TypeError:
                return account.calculate_minimum_payment()
        return 0.0

    @property
    def amount(self) -> float:
        """Dynamic amount that delegates to the linked account (as of today)."""
        return self._resolve_amount_from_account(self.linked_account, self.linked_account_type)

    def amount_on(self, reference_date: date = None) -> float:
        """Amount due as of a specific (e.g. simulated) date."""
        return self._resolve_amount_from_account(
            self.linked_account, self.linked_account_type, reference_date
        )

    @amount.setter
    def amount(self, value):
        """Allow setting amount (used by parent __init__ and deepcopy)."""
        # Store the value but it will be overridden by the property getter
        # when the linked account is present
        self._static_amount = value

    @property
    def effective_amount(self) -> float:
        """Amount actually due this period, including any carryover."""
        return self.amount + self.carryover_balance

    @property
    def is_account_linked(self) -> bool:
        """Whether this bill is linked to an account."""
        return True

    @property
    def linked_account_balance(self) -> float:
        """Get the current balance of the linked account."""
        if self.linked_account_type == 'mortgage':
            return self.linked_account.current_principal
        return self.linked_account.balance

    @property
    def is_paid_this_period(self) -> bool:
        """Read paid status from the linked account."""
        return getattr(self.linked_account, 'is_paid_this_period', self._is_paid_this_period)

    @is_paid_this_period.setter
    def is_paid_this_period(self, value: bool):
        """Set paid status on both the bill and the linked account."""
        self._is_paid_this_period = value
        if hasattr(self.linked_account, 'is_paid_this_period'):
            self.linked_account.is_paid_this_period = value

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None):
        """
        Record payment for this linked bill.
        Also calls the linked account's make_payment() to update balances.
        """
        due_amount = self.effective_amount
        if amount_paid is None:
            amount_paid = due_amount

        # Call the linked account's make_payment
        if amount_paid > 0:
            if self.linked_account_type == 'credit':
                # Credit accounts handle source withdrawal themselves
                self.linked_account.make_payment(
                    amount_paid,
                    description=f"Bill payment: {self.bill_name}",
                    transaction_date=payment_date or date.today()
                )
            elif self.linked_account_type == 'mortgage':
                self.linked_account.make_payment(
                    amount=amount_paid,
                    payment_date=payment_date or date.today(),
                    source_bank=source_bank,
                    source_account=source_account,
                )
            elif self.linked_account_type == 'heloc':
                self.linked_account.make_payment(
                    amount_paid,
                    description=f"Bill payment: {self.bill_name}",
                    transaction_date=payment_date or date.today()
                )

        # Track carryover
        self.carryover_balance = max(0.0, round(due_amount - amount_paid, 2))

        self.payment_history.append({
            "date": payment_date or date.today(),
            "source_bank": source_bank,
            "source_account": source_account,
            "amount_paid": amount_paid
        })
        self.is_paid_this_period = True

    def reset_period(self):
        """Reset the paid status for the next period."""
        self.is_paid_this_period = False

    def copy(self):
        """Create a deep copy of this linked bill."""
        return deepcopy(self)

    def __repr__(self):
        status = "PAID" if self.is_paid_this_period else "UNPAID"
        return f"AccountLinkedBill({self.bill_name}, ${self.amount:.2f}, {self.linked_account_type}, {status})"


class GroupLinkedBill(Bill):
    """
    A bill that is automatically generated from a BillGroup (bundled loan payment).

    The amount is dynamically resolved from the linked group's total_payment.
    When mark_paid() is called, it distributes the payment across group members
    and marks the group as paid.
    """

    def __init__(
        self,
        linked_group,
        preferred_source_account: str = None,
        preferred_source_bank: str = None,
    ):
        """
        Args:
            linked_group: The BillGroup instance
            preferred_source_account: Preferred account name to pay from
            preferred_source_bank: Preferred bank name to pay from
        """
        self.linked_group = linked_group

        # Initialize private tracking field before super().__init__
        self._is_paid_this_period = False

        bill_name = f"[Auto] {linked_group.group_name} Payment"
        self.group_link_key = f"group:{linked_group.group_name}"

        due_date = linked_group.due_date

        if preferred_source_bank is None:
            preferred_source_bank = linked_group.preferred_source_bank
        if preferred_source_account is None:
            preferred_source_account = linked_group.preferred_source_account

        was_paid = linked_group.is_paid_this_period  # restored after Bill.__init__ resets it

        super().__init__(
            bill_name=bill_name,
            amount=linked_group.total_payment,
            due_date=due_date,
            bill_type=BillType.GROUP_PAYMENT,
            frequency=linked_group.frequency,
            preferred_source_account=preferred_source_account,
            preferred_source_bank=preferred_source_bank,
            _skip_amount_validation=True,
        )
        self.is_paid_this_period = was_paid

    @property
    def amount(self) -> float:
        """Dynamic amount that delegates to the linked group."""
        return self.linked_group.total_payment

    @amount.setter
    def amount(self, value):
        """Allow setting amount (used by parent __init__ and deepcopy)."""
        self._static_amount = value

    @property
    def effective_amount(self) -> float:
        """Amount actually due this period, including any carryover."""
        return self.amount + self.carryover_balance

    @property
    def is_group_linked(self) -> bool:
        """Whether this bill is linked to a bill group."""
        return True

    @property
    def is_paid_this_period(self) -> bool:
        """Read paid status from the linked group."""
        return self.linked_group.is_paid_this_period

    @is_paid_this_period.setter
    def is_paid_this_period(self, value: bool):
        """Set paid status on both the bill and the linked group."""
        self._is_paid_this_period = value
        self.linked_group.is_paid_this_period = value

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None,
                  payment_date: date = None, banks: list = None):
        """
        Record payment for this group bill.
        Distributes the payment across group member accounts and marks the group as paid.

        Args:
            source_bank: Bank name the payment came from
            source_account: Account name the payment came from
            amount_paid: Amount paid (defaults to group total_payment)
            payment_date: Date of payment
            banks: List of Bank objects needed for distribute_payment
        """
        due_amount = self.effective_amount
        if amount_paid is None:
            amount_paid = due_amount

        # Distribute payment across group members if banks are provided
        sub_payments = []
        if banks and amount_paid > 0:
            sub_payments = self.linked_group.distribute_payment(
                amount_paid, banks, payment_date or date.today()
            )

        # Mark the group as paid
        self.linked_group.mark_paid(payment_date or date.today())

        # Track carryover
        self.carryover_balance = max(0.0, round(due_amount - amount_paid, 2))

        self.payment_history.append({
            "date": payment_date or date.today(),
            "source_bank": source_bank,
            "source_account": source_account,
            "amount_paid": amount_paid,
            "sub_payments": sub_payments,
        })
        # is_paid_this_period is already set via linked_group.mark_paid above

        return sub_payments

    def reset_period(self):
        """Reset the paid status for the next period."""
        self.is_paid_this_period = False

    def copy(self):
        """Create a deep copy of this group-linked bill."""
        return deepcopy(self)

    def __repr__(self):
        status = "PAID" if self.is_paid_this_period else "UNPAID"
        return f"GroupLinkedBill({self.bill_name}, ${self.amount:.2f}, {status})"


