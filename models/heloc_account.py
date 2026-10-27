"""
HELOC (Home Equity Line of Credit) Account model.

A HELOC has two distinct phases:
1. **Draw Period** (e.g., 15 years): You can borrow up to the credit limit.
   Minimum payments are interest-only (total accrued interest each month).
2. **Repayment Period** (remaining years): No new draws allowed.
   Payments are fully amortized principal + interest over the remaining term.
"""

from datetime import date, timedelta
from copy import deepcopy
import math

from .types import HELOCPhase
from .date_utils import add_months, clamped_date, next_by_months


class HELOCAccount:
    """
    Represents a Home Equity Line of Credit account.

    During the draw period, minimum payments equal the monthly accrued interest.
    After the draw period ends, the outstanding balance is amortized over the
    remaining repayment period with fully amortized P+I payments.
    """

    def __init__(
        self,
        account_name: str,
        credit_limit: float,
        interest_rate: float,           # Annual percentage rate (APR) as %
        draw_period_months: int,        # Length of draw period (e.g., 180 for 15 years)
        total_term_months: int,         # Total loan term (e.g., 360 for 30 years)
        start_date: date = None,        # When the HELOC was opened
        current_balance: float = 0.0,   # Current amount drawn / owed
        payment_due_date: int = 1,      # Day of month for payment
        preferred_source_bank: str = None,
        preferred_source_account: str = None,
    ):
        if credit_limit <= 0:
            raise ValueError("Credit limit must be positive.")
        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative.")
        if draw_period_months <= 0:
            raise ValueError("Draw period must be positive.")
        if total_term_months <= draw_period_months:
            raise ValueError("Total term must be longer than draw period.")
        if current_balance < 0:
            raise ValueError("Balance cannot be negative.")
        if not (1 <= payment_due_date <= 31):
            raise ValueError("Payment due date must be between 1 and 31.")

        self.account_name = account_name
        self.credit_limit = credit_limit
        self.interest_rate = interest_rate
        self.draw_period_months = draw_period_months
        self.total_term_months = total_term_months
        self.start_date = start_date or date.today()
        self.balance = current_balance
        self.payment_due_date = payment_due_date

        self.preferred_source_bank = preferred_source_bank
        self.preferred_source_account = preferred_source_account

        # Tracking
        self.transaction_history: list[dict] = []
        self.payment_history: list[dict] = []
        self.is_paid_this_period = False
        # Interest accrued (via accrue_interest) and not yet covered by a
        # payment. During the draw period the minimum payment is this amount
        # once interest is being accrued, so interest-only payments keep the
        # balance flat.
        self.unpaid_interest: float = 0.0

    # ── Phase detection ───────────────────────────────────────────────

    @property
    def repayment_period_months(self) -> int:
        """Months allocated to repayment after draw period ends."""
        return self.total_term_months - self.draw_period_months

    @property
    def draw_end_date(self) -> date:
        """Date when the draw period ends."""
        year, month = add_months(self.start_date.year, self.start_date.month, self.draw_period_months)
        return clamped_date(year, month, self.start_date.day)

    @property
    def maturity_date(self) -> date:
        """Date when the entire loan term ends."""
        year, month = add_months(self.start_date.year, self.start_date.month, self.total_term_months)
        return clamped_date(year, month, self.start_date.day)

    @property
    def current_phase(self) -> HELOCPhase:
        """Determine the current phase of the HELOC (as of today)."""
        return self.get_phase_on_date(date.today())

    def get_phase_on_date(self, ref_date: date = None) -> HELOCPhase:
        """Determine phase on a specific date (default today)."""
        ref_date = ref_date or date.today()
        if self.balance <= 0:
            return HELOCPhase.PAID_OFF
        if ref_date < self.draw_end_date:
            return HELOCPhase.DRAW
        return HELOCPhase.REPAYMENT

    def is_draw_period(self, as_of: date = None) -> bool:
        """Whether draws are allowed on the given date (ignores balance)."""
        return (as_of or date.today()) < self.draw_end_date

    @property
    def months_elapsed(self) -> int:
        """Months elapsed since start date."""
        today = date.today()
        return (today.year - self.start_date.year) * 12 + (today.month - self.start_date.month)

    @property
    def months_into_repayment(self) -> int:
        """Months elapsed since repayment period started (0 if still in draw)."""
        return self.get_months_into_repayment()

    def get_months_into_repayment(self, as_of: date = None) -> int:
        """Months elapsed since repayment started as of a date (0 if still in draw)."""
        as_of = as_of or date.today()
        if self.get_phase_on_date(as_of) != HELOCPhase.REPAYMENT:
            return 0
        end = self.draw_end_date
        return (as_of.year - end.year) * 12 + (as_of.month - end.month)

    @property
    def remaining_repayment_months(self) -> int:
        """Months remaining in the repayment period."""
        return self.get_remaining_repayment_months()

    def get_remaining_repayment_months(self, as_of: date = None) -> int:
        """Months remaining in the repayment period as of a date (default today)."""
        phase = self.get_phase_on_date(as_of)
        if phase == HELOCPhase.DRAW:
            return self.repayment_period_months
        if phase == HELOCPhase.PAID_OFF:
            return 0
        return max(1, self.repayment_period_months - self.get_months_into_repayment(as_of))

    # ── Interest & payment calculations ───────────────────────────────

    @property
    def monthly_interest_rate(self) -> float:
        """Monthly interest rate as decimal."""
        return self.interest_rate / 100 / 12

    @property
    def current_monthly_interest(self) -> float:
        """Interest accrued this month on the outstanding balance."""
        return round(self.balance * self.monthly_interest_rate, 2)

    @property
    def available_credit(self) -> float:
        """Available credit today (only meaningful during draw period)."""
        return self.get_available_credit()

    def get_available_credit(self, as_of: date = None) -> float:
        """Available credit on a given date (0 outside the draw period)."""
        if not self.is_draw_period(as_of):
            return 0.0
        return max(0.0, self.credit_limit - self.balance)

    def calculate_minimum_payment(self, as_of: date = None) -> float:
        """
        Calculate the minimum payment due on a given date (default today).

        Draw period: interest-only. Once interest has been accrued via
        accrue_interest (e.g. in the timeline simulation) this is the accrued
        interest not yet paid; otherwise it is the monthly interest on the
        current balance.
        Repayment period: fully amortized P+I over remaining repayment months.
        """
        if self.balance <= 0:
            return 0.0

        phase = self.get_phase_on_date(as_of)

        if phase == HELOCPhase.DRAW:
            # Interest-only minimum during draw period
            unpaid = getattr(self, 'unpaid_interest', 0.0)
            if unpaid > 0:
                return round(min(unpaid, self.balance), 2)
            return self.current_monthly_interest

        # Repayment period — fully amortized payment
        return self._amortized_payment(self.get_remaining_repayment_months(as_of))

    def _amortized_payment(self, months_remaining: int) -> float:
        """Calculate amortized monthly payment for a given number of remaining months."""
        if months_remaining <= 0 or self.balance <= 0:
            return 0.0

        r = self.monthly_interest_rate
        if r == 0:
            return round(self.balance / months_remaining, 2)

        n = months_remaining
        payment = self.balance * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        return round(payment, 2)

    @property
    def monthly_payment(self) -> float:
        """Alias for calculate_minimum_payment."""
        return self.calculate_minimum_payment()

    # ── Transactions ──────────────────────────────────────────────────

    def make_draw(self, amount: float, description: str = "HELOC Draw", transaction_date: date = None) -> None:
        """
        Draw funds from the HELOC (increases balance).
        Only allowed during the draw period, evaluated on transaction_date
        (default today).
        """
        as_of = transaction_date or date.today()
        if amount <= 0:
            raise ValueError("Draw amount must be positive.")
        if not self.is_draw_period(as_of):
            raise ValueError("Cannot draw funds — draw period has ended.")
        available = self.get_available_credit(as_of)
        if amount > available:
            raise ValueError(
                f"Draw exceeds available credit. Available: ${available:.2f}, Requested: ${amount:.2f}"
            )

        self.balance += amount
        self._record_transaction("DRAW", amount, description, transaction_date)

    def make_payment(
        self,
        amount: float,
        source_bank=None,
        source_account=None,
        description: str = "HELOC Payment",
        transaction_date: date = None,
    ) -> None:
        """
        Make a payment toward the HELOC balance.
        Optionally withdraws from a source bank account.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        if amount > self.balance:
            raise ValueError(
                f"Payment exceeds balance. Balance: ${self.balance:.2f}, Requested: ${amount:.2f}"
            )

        # Withdraw from source if provided
        if source_account is not None and source_bank is not None:
            if source_account not in source_bank.accounts:
                raise ValueError(f"Account '{source_account}' does not exist in the bank.")
            source_bank.accounts[source_account].withdraw(
                amount,
                description=f"Payment to {self.account_name}",
                transaction_date=transaction_date,
            )

        self.balance -= amount
        # Payments cover accrued interest first
        self.unpaid_interest = max(0.0, getattr(self, 'unpaid_interest', 0.0) - amount)
        self._record_transaction("PAYMENT", -amount, description, transaction_date)

        self.payment_history.append({
            "date": transaction_date or date.today(),
            "amount": amount,
            "balance_after": self.balance,
        })

    def accrue_interest(self, current_date: date = None) -> float:
        """
        Accrue monthly interest on the outstanding balance.
        Returns the interest amount added.
        """
        current_date = current_date or date.today()
        if self.interest_rate <= 0 or self.balance <= 0:
            return 0.0

        interest = self.current_monthly_interest
        self.balance += interest
        self.unpaid_interest = getattr(self, 'unpaid_interest', 0.0) + interest
        self._record_transaction("INTEREST", interest, "Interest accrual", current_date)
        return interest

    def accrue_interest_if_due(self, current_date: date) -> float:
        """Accrue interest if the statement date has passed."""
        # Simple: accrue once per month cycle (handled by simulator)
        return self.accrue_interest(current_date)

    # ── Schedule & projections ────────────────────────────────────────

    def get_amortization_schedule(self, months: int = None) -> list[dict]:
        """
        Generate a repayment amortization schedule.
        Shows how the balance will be paid off once repayment begins.
        """
        if self.balance <= 0:
            return []

        phase = self.current_phase
        schedule = []
        principal = self.balance
        r = self.monthly_interest_rate
        current = date.today()

        if phase == HELOCPhase.DRAW:
            # Show interest-only payments until draw period ends
            draw_months_left = max(0, (self.draw_end_date.year - current.year) * 12
                                   + (self.draw_end_date.month - current.month))
            for m in range(1, draw_months_left + 1):
                interest = round(principal * r, 2)
                try:
                    pay_year, pay_month = add_months(current.year, current.month, m)
                    payment_date = clamped_date(pay_year, pay_month, self.payment_due_date)
                except ValueError:
                    payment_date = current + timedelta(days=30 * m)

                schedule.append({
                    "month": m,
                    "date": payment_date,
                    "payment": interest,
                    "principal": 0.0,
                    "interest": interest,
                    "phase": "draw",
                    "principal_remaining": principal,
                })

            # Then repayment
            offset = draw_months_left
            repay_months = self.repayment_period_months
        else:
            offset = 0
            repay_months = months or self.remaining_repayment_months

        payment = self._amortized_payment(repay_months if phase == HELOCPhase.DRAW else self.remaining_repayment_months)

        for m in range(1, (months or repay_months) + 1):
            if principal <= 0:
                break
            interest = round(principal * r, 2)
            principal_payment = min(round(payment - interest, 2), principal)
            principal = max(0, principal - principal_payment)

            try:
                pay_year, pay_month = add_months(current.year, current.month, offset + m)
                payment_date = clamped_date(pay_year, pay_month, self.payment_due_date)
            except ValueError:
                payment_date = current + timedelta(days=30 * (offset + m))

            schedule.append({
                "month": offset + m,
                "date": payment_date,
                "payment": round(payment, 2),
                "principal": principal_payment,
                "interest": interest,
                "phase": "repayment",
                "principal_remaining": max(0, principal),
            })

        return schedule

    # ── Utility ───────────────────────────────────────────────────────

    def get_next_due_date(self, reference_date: date) -> date:
        """Calculate the next payment due date relative to a reference date."""
        return next_by_months(reference_date.year, reference_date.month,
                              self.payment_due_date, 1, reference_date)

    def reset_period(self):
        """Reset the paid status for the next period."""
        self.is_paid_this_period = False

    def get_balance(self) -> float:
        """Return current balance owed."""
        return self.balance

    def _record_transaction(self, trans_type: str, amount: float, description: str, trans_date: date = None):
        """Record a transaction in history."""
        self.transaction_history.append({
            "type": trans_type,
            "amount": amount,
            "description": description,
            "date": trans_date or date.today(),
            "balance_after": self.balance,
        })

    def copy(self):
        """Create a deep copy of this account."""
        return deepcopy(self)

    def __repr__(self):
        phase = self.current_phase.value
        return (
            f"HELOCAccount({self.account_name}, "
            f"limit=${self.credit_limit:,.2f}, "
            f"balance=${self.balance:,.2f}, "
            f"phase={phase})"
        )

