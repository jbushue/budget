from datetime import date, timedelta
from copy import deepcopy

from .types import CreditAccountStatus


class PromoOffer:
    """Represents a promotional interest-free offer on a credit card."""

    def __init__(
        self,
        promo_name: str,
        months_interest_free: int,
        purchase_limit: float = None,
        start_date: date = None
    ):
        """
        Args:
            promo_name: Name of the promotion (e.g., "Intro 0% APR")
            months_interest_free: Number of months with 0% interest
            purchase_limit: Maximum amount eligible for promo (None = unlimited)
            start_date: When the promo starts (None = today)
        """
        self.promo_name = promo_name
        self.months_interest_free = months_interest_free
        self.purchase_limit = purchase_limit
        self.start_date = start_date or date.today()
        self.end_date = start_date + timedelta(days=30 * months_interest_free) if start_date else date.today() + timedelta(days=30 * months_interest_free)
        self.amount_used = 0.0
        self.is_active = True
        self.interest_charged = False  # Track if interest has been charged at end of promo

    def is_valid_for_purchase(self, amount: float) -> bool:
        """Check if purchase is eligible for this promo."""
        if not self.is_active or date.today() > self.end_date:
            return False
        if self.purchase_limit and self.amount_used + amount > self.purchase_limit:
            return False
        return True

    def apply_to_purchase(self, amount: float) -> bool:
        """Apply promo to a purchase. Returns True if applied."""
        if self.is_valid_for_purchase(amount):
            self.amount_used += amount
            return True
        return False

    def has_expired(self) -> bool:
        """Check if the promotional period has ended."""
        return date.today() > self.end_date

    def __repr__(self):
        return f"PromoOffer({self.promo_name}, {self.months_interest_free} months, expires {self.end_date})"


class CreditAccount:
    """Represents a credit card or line of credit account."""

    def __init__(
        self,
        account_name: str,
        credit_limit: float,
        interest_rate: float,
        payment_due_date: int = None,
        statement_date: int = None,
        status: str | CreditAccountStatus = "active"
    ):
        """
        Args:
            account_name: Name of the credit account
            credit_limit: Maximum credit available
            interest_rate: Annual percentage rate (APR)
            payment_due_date: Day of month (1-31) when payment is due
            statement_date: Day of month (1-31) when statement closes/interest accrues
            status: Account status (active, closed, frozen)
        """
        if credit_limit <= 0:
            raise ValueError("Credit limit must be positive.")
        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative.")

        self.account_name = account_name
        self.credit_limit = credit_limit
        self.interest_rate = interest_rate  # Annual percentage rate (APR)
        self.balance = 0.0  # Amount owed
        self.payment_due_date = payment_due_date  # Day of month for payment due
        self.statement_date = statement_date  # Day of month for statement close

        if isinstance(status, str):
            status = CreditAccountStatus[status.upper()]
        self.status = status

        self.minimum_payment = 0.0
        self.transaction_history: list[dict] = []
        self.payment_history: list[dict] = []

        # Promotional tracking
        self.active_promos: list[PromoOffer] = []
        self.promo_balance: dict[str, float] = {}  # {promo_name: amount}
        self.regular_balance: float = 0.0  # Balance not on promo

    def make_purchase(self, amount: float, description: str = "Purchase", transaction_date: date = None, promo_name: str = None) -> None:
        """Record a purchase (increases balance owed).

        Args:
            amount: Purchase amount
            description: Purchase description
            transaction_date: Date of purchase
            promo_name: If specified, allocate to this promotional offer
        """
        if amount <= 0:
            raise ValueError("Purchase amount must be positive.")
        if amount > self.available_credit():
            raise ValueError(f"Purchase exceeds available credit. Available: {self.available_credit():.2f}, Requested: {amount:.2f}")

        self.balance += amount

        # Allocate to promotional offer if specified
        if promo_name:
            promo = next((p for p in self.active_promos if p.promo_name == promo_name), None)
            if promo and promo.apply_to_purchase(amount):
                if promo_name not in self.promo_balance:
                    self.promo_balance[promo_name] = 0.0
                self.promo_balance[promo_name] += amount
            else:
                # Fall back to regular balance if promo not applicable
                self.regular_balance += amount
        else:
            self.regular_balance += amount

        self._record_transaction("PURCHASE", amount, description, transaction_date)

    def make_payment(
        self,
        amount: float,
        source_account=None,
        source_bank=None,
        description: str = "Payment",
        transaction_date: date = None
    ) -> None:
        """
        Record a payment to this credit account.
        Optionally withdraws from a source bank account.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")

        if amount > self.balance:
            raise ValueError(f"Payment exceeds balance owed. Balance: {self.balance:.2f}, Requested: {amount:.2f}")

        # If source account provided, withdraw from it
        if source_account is not None and source_bank is not None:
            if source_account not in source_bank.accounts:
                raise ValueError(f"Account '{source_account}' does not exist in the bank.")
            source_bank.accounts[source_account].withdraw(
                amount,
                description=f"Payment to {self.account_name}",
                transaction_date=transaction_date
            )

        self.balance -= amount
        self._record_transaction("PAYMENT", -amount, description, transaction_date)

        self.payment_history.append({
            "date": transaction_date or date.today(),
            "amount": amount,
            "balance_after": self.balance
        })

    def _record_transaction(self, trans_type: str, amount: float, description: str, trans_date: date = None):
        """Record a transaction in history."""
        self.transaction_history.append({
            "type": trans_type,
            "amount": amount,
            "description": description,
            "date": trans_date or date.today(),
            "balance_after": self.balance
        })

    def accrue_interest_if_due(self, current_date: date) -> float:
        """
        Accrue interest if we're past the statement date.
        Returns the interest amount accrued, or 0 if not accrued.
        """
        if self.statement_date is None:
            return self.accrue_interest(current_date)

        if current_date.day >= self.statement_date:
            return self.accrue_interest(current_date)
        return 0.0

    def calculate_minimum_payment(self) -> float:
        """
        Calculate minimum payment due.
        Typical credit card formula: 2% of balance or $25, whichever is greater (but not more than balance).
        """
        if self.balance <= 0:
            return 0.0
        min_payment = max(0.02 * self.balance, 25.0)
        return min(min_payment, self.balance)

    def calculate_monthly_payment(self, months: int) -> float:
        """
        Calculate fixed monthly payment to pay off balance in given months using amortization formula.
        """
        if months <= 0:
            raise ValueError("Months must be positive.")
        if self.balance <= 0:
            return 0.0

        monthly_rate = self.interest_rate / 12 / 100
        if monthly_rate == 0:
            return self.balance / months

        # Standard amortization formula
        payment = self.balance * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        return payment

    def available_credit(self) -> float:
        """Return available credit."""
        available = self.credit_limit - self.balance
        return max(0.0, available)

    def add_promotional_offer(
        self,
        promo_name: str,
        months_interest_free: int,
        purchase_limit: float = None,
        start_date: date = None
    ) -> PromoOffer:
        """Add a promotional interest-free offer."""
        promo = PromoOffer(promo_name, months_interest_free, purchase_limit, start_date)
        self.active_promos.append(promo)
        self.promo_balance[promo_name] = 0.0
        return promo

    def get_promo_status(self) -> dict:
        """Get status of all active promotional offers."""
        status = {}
        for promo in self.active_promos:
            if date.today() <= promo.end_date:
                status[promo.promo_name] = {
                    "amount_used": promo.amount_used,
                    "purchase_limit": promo.purchase_limit,
                    "months_remaining": max(0, (promo.end_date - date.today()).days // 30),
                    "expires": promo.end_date.strftime("%Y-%m-%d")
                }
        return status

    def process_expired_promos(self, current_date: date = None) -> float:
        """
        Check for expired promotional offers and charge interest on remaining balances.
        When a promo expires with remaining balance, retroactive interest is charged
        as if the promo never existed.

        Returns: Total interest charged from expired promos
        """
        current_date = current_date or date.today()
        total_interest_charged = 0.0

        for promo in self.active_promos:
            # Check if promo has expired and still has balance
            if promo.has_expired() and not promo.interest_charged:
                remaining_balance = self.promo_balance.get(promo.promo_name, 0.0)

                if remaining_balance > 0:
                    # Calculate interest that would have accrued from promo start to expiration
                    months_elapsed = promo.months_interest_free
                    monthly_rate = self.interest_rate / 12 / 100

                    # Calculate compound interest over the promotional period
                    # Interest = Principal * [(1 + rate)^n - 1]
                    interest = remaining_balance * (((1 + monthly_rate) ** months_elapsed) - 1)

                    # Add interest to balance and record it
                    self.balance += interest
                    self.regular_balance += interest
                    self.promo_balance[promo.promo_name] = remaining_balance + interest

                    total_interest_charged += interest

                    # Record transaction
                    self._record_transaction(
                        "PROMO_INTEREST",
                        interest,
                        f"Retroactive interest on expired promo '{promo.promo_name}'",
                        current_date
                    )

                # Mark promo as having had interest charged
                promo.interest_charged = True

        return total_interest_charged

    def accrue_interest(self, current_date: date = None) -> float:
        """
        Accrue interest on the credit card balance.

        Process:
        1. Check for expired promos and charge retroactive interest
        2. Charge interest only on regular (non-promotional) balance

        Promotional purchases do NOT accrue interest while promo is active.
        When promo expires with remaining balance, interest is charged retroactively.

        Returns the interest amount accrued.
        """
        current_date = current_date or date.today()
        total_interest = 0.0

        # First, process any expired promos and charge retroactive interest
        promo_interest = self.process_expired_promos(current_date)
        total_interest += promo_interest

        # Then charge regular interest on non-promotional balance
        if self.interest_rate <= 0 or self.regular_balance <= 0:
            return total_interest

        # Monthly interest accrual (typical for credit cards) - only on regular balance
        monthly_rate = self.interest_rate / 12 / 100
        interest = self.regular_balance * monthly_rate
        self.balance += interest
        self.regular_balance += interest

        self._record_transaction("INTEREST", interest, "Interest accrual", current_date)
        return total_interest + interest

    def get_balance(self) -> float:
        """Return current balance owed."""
        return self.balance

    def copy(self):
        """Create a deep copy of this account."""
        return deepcopy(self)

    def __repr__(self):
        return f"CreditAccount({self.account_name}, limit=${self.credit_limit:.2f}, balance=${self.balance:.2f})"

