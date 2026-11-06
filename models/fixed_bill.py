from datetime import date
from copy import deepcopy

from .types import BillFrequency, BillType
from .date_utils import add_months, clamped_date, next_by_days, next_by_months
from . import occurrences as occ


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

        # Payment tracking: each payment records the due date it pays (see occurrences)
        self.payment_history: list[dict] = []
        self.skipped: set[date] = set()  # due dates not owed (waived, paid elsewhere)
        # Due dates before this never count as overdue (set when due-date tracking began)
        self.tracked_from: date | None = None

        # Fee if paid late (None = use the app-wide default from settings)
        self.late_fee: float | None = None
        # When the bill was added (restored from the database on load); a bill
        # can't be overdue for a due date before it existed
        self.created_on: date = date.today()

    @property
    def effective_amount(self) -> float:
        """What is still owed on the due date a payment would go to now."""
        due = occ.default_due(self)
        return occ.remaining(self, due) if due else self.amount

    @property
    def carryover_balance(self) -> float:
        """Left unpaid on earlier due dates (still owed alongside the next one)."""
        due = occ.default_due(self)
        return round(sum(left for d, left in occ.overdue(self) if d != due), 2)

    @carryover_balance.setter
    def carryover_balance(self, value):
        pass  # derived from the payments now

    @property
    def is_paid_this_period(self) -> bool:
        """Nothing overdue and the next due date is paid (or skipped)."""
        return occ.is_paid_now(self)

    @is_paid_this_period.setter
    def is_paid_this_period(self, value: bool):
        """True skips the due date a payment would go to; False un-skips the next one."""
        if value:
            due = occ.default_due(self)
            if due is not None and occ.status(self, due) not in ("paid", "skipped"):
                self.skipped = set(self.skipped) | {due}
        else:
            nd = occ.next_due(self, date.today())
            self.skipped = {d for d in self.skipped if nd is None or occ.period(self, d) != occ.period(self, nd)}

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None,
                  due: date = None, moved_money: bool = True):
        """Record a payment for one due date (default: the oldest still owed, else the next).

        Paying less than is owed leaves that due date partly paid.
        """
        due = due or occ.default_due(self, payment_date or date.today())
        entry = occ.new_entry(self, due, amount_paid, payment_date, source_bank, source_account, moved_money)
        self.payment_history.append(entry)
        return entry

    def reset_period(self):
        """Undo the latest recorded payment's due date (kept for older callers)."""
        due = occ.latest_paid_due(self)
        if due is not None:
            self.payment_history = [e for e in self.payment_history if e not in occ.payments_for(self, due)]

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
        # The real amount of a due date's bill once it arrives (due date -> amount)
        self.actual_amounts: dict[date, float] = {}
        self.amount_history: list[float] = []  # Past actual amounts for averaging

    def amount_on(self, reference_date: date = None) -> float:
        """The due date's actual amount if it's known, else the estimate."""
        actual = occ.actual_for(self, reference_date) if reference_date is not None else None
        return self.amount if actual is None else actual

    def set_actual_amount(self, actual_amount: float, due: date = None):
        """
        Set the real amount of one due date's bill (default: the due date a
        payment would go to now). Other due dates keep the estimate.
        """
        if actual_amount <= 0:
            raise ValueError("Actual amount must be positive.")
        due = due or occ.default_due(self)
        if due is not None:
            self.reset_to_estimate(due)
            self.actual_amounts[due] = actual_amount

    def reset_to_estimate(self, due: date = None):
        """Go back to the estimate for a due date (default: the one a payment would go to now)."""
        due = due or occ.default_due(self)
        if due is not None:
            key = occ.period(self, due)
            self.actual_amounts = {d: v for d, v in self.actual_amounts.items() if occ.period(self, d) != key}

    @property
    def _actual_amount(self) -> float | None:
        """The actual amount for the due date a payment would go to now, if set."""
        due = occ.default_due(self)
        return occ.actual_for(self, due) if due else None

    @property
    def has_actual_amount(self) -> bool:
        """Whether the real amount is known for the due date a payment would go to now."""
        return self._actual_amount is not None

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None,
                  due: date = None, moved_money: bool = True, learn: bool = True):
        """Record payment, update history and recalculate the estimate
        (learn=False for payments a projection only imagines)."""
        entry = super().mark_paid(source_bank, source_account, amount_paid, payment_date, due, moved_money)
        paid_amount = entry["amount_paid"]

        # Record the actual amount paid into history
        if paid_amount > 0 and learn:
            self.amount_history.append(round(paid_amount, 2))
            # Keep last 12 entries
            if len(self.amount_history) > 12:
                self.amount_history = self.amount_history[-12:]
            # Recalculate estimate from history
            self._recalculate_estimate()
        self.amount = self.estimated_amount
        return entry

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
            # Any kind of loan; a student loan owes nothing before repayment starts
            in_deferment = getattr(account, "in_deferment", None)
            if in_deferment is not None and in_deferment(reference_date):
                return 0.0
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
    def is_account_linked(self) -> bool:
        """Whether this bill is linked to an account."""
        return True

    @property
    def linked_account_balance(self) -> float:
        """Get the current balance of the linked account."""
        if self.linked_account_type == 'mortgage':
            return self.linked_account.current_principal
        return self.linked_account.balance

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None, payment_date: date = None,
                  due: date = None, moved_money: bool = True):
        """
        Record payment for one due date of this linked bill.
        Also calls the linked account's make_payment() to update balances.
        """
        due = due or occ.default_due(self, payment_date or date.today())
        entry = occ.new_entry(self, due, amount_paid, payment_date, source_bank, source_account, moved_money)
        amount_paid = entry["amount_paid"]

        # Call the linked account's make_payment
        if amount_paid > 0:
            if self.linked_account_type == 'credit':
                # Split over the regular and promo balances the card's way
                # (regular first or last; promos soonest-expiring first)
                pay = getattr(self.linked_account, "pay_with_promo_plan", None)
                if pay is not None:
                    pay(amount_paid, description=f"Bill payment: {self.bill_name}",
                        transaction_date=payment_date or date.today())
                else:
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

        self.payment_history.append(entry)
        return entry

    def copy(self):
        """Create a deep copy of this linked bill."""
        return deepcopy(self)

    def __repr__(self):
        return f"AccountLinkedBill({self.bill_name}, ${self.amount:.2f}, {self.linked_account_type})"


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

        bill_name = f"[Auto] {linked_group.group_name} Payment"
        self.group_link_key = f"group:{linked_group.group_name}"

        due_date = linked_group.due_date

        if preferred_source_bank is None:
            preferred_source_bank = linked_group.preferred_source_bank
        if preferred_source_account is None:
            preferred_source_account = linked_group.preferred_source_account

        # Bill.__init__ clears the payments and skips, which live on the group
        kept = (linked_group.payment_history, set(getattr(linked_group, "skipped", set())))

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
        linked_group.payment_history, linked_group.skipped = kept

    # Payments, skips and tracking dates live on the group (it's what is saved);
    # Bill.__init__'s assignments to them are ignored
    @property
    def payment_history(self) -> list[dict]:
        return self.linked_group.payment_history

    @payment_history.setter
    def payment_history(self, value):
        self.linked_group.payment_history = value

    @property
    def skipped(self) -> set:
        return self.linked_group.skipped

    @skipped.setter
    def skipped(self, value):
        self.linked_group.skipped = set(value)

    @property
    def created_on(self) -> date:
        return self.linked_group.created_on

    @created_on.setter
    def created_on(self, value):
        pass

    @property
    def tracked_from(self):
        return getattr(self.linked_group, "tracked_from", None)

    @tracked_from.setter
    def tracked_from(self, value):
        pass

    @property
    def amount(self) -> float:
        """Dynamic amount that delegates to the linked group."""
        return self.linked_group.total_payment

    @amount.setter
    def amount(self, value):
        """Allow setting amount (used by parent __init__ and deepcopy)."""
        self._static_amount = value

    @property
    def is_group_linked(self) -> bool:
        """Whether this bill is linked to a bill group."""
        return True

    def mark_paid(self, source_bank: str, source_account: str, amount_paid: float = None,
                  payment_date: date = None, banks: list = None, due: date = None, moved_money: bool = True):
        """
        Record payment for this group bill.
        Distributes the payment across group member accounts and marks the group as paid.

        Args:
            source_bank: Bank name the payment came from
            source_account: Account name the payment came from
            amount_paid: Amount paid (defaults to group total_payment)
            payment_date: Date of payment
            banks: List of Bank objects needed for distribute_payment
            due: The due date this pays (default: the oldest still owed, else the next)
        """
        due = due or occ.default_due(self, payment_date or date.today())
        entry = occ.new_entry(self, due, amount_paid, payment_date, source_bank, source_account, moved_money)
        amount_paid = entry["amount_paid"]

        # Distribute payment across group members if banks are provided
        sub_payments = []
        if banks and amount_paid > 0:
            sub_payments = self.linked_group.distribute_payment(
                amount_paid, banks, payment_date or date.today()
            )

        entry["sub_payments"] = sub_payments
        self.payment_history.append(entry)
        return sub_payments

    def copy(self):
        """Create a deep copy of this group-linked bill."""
        return deepcopy(self)

    def __repr__(self):
        return f"GroupLinkedBill({self.bill_name}, ${self.amount:.2f})"


