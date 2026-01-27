from datetime import date
from enum import Enum
from copy import deepcopy
from .types import AccountType


class BankAccount:
    """Base class for traditional bank accounts (checking, savings)."""

    def __init__(
        self,
        account_type: str | AccountType,
        account_name: str,
        balance: float = 0.0,
        interest_rate: float = 0.0,
        interest_accrual_date: int = None
    ):
        """
        Args:
            account_type: 'checking', 'savings', or AccountType enum
            account_name: Human-readable name for the account
            balance: Starting balance (must be >= 0)
            interest_rate: Annual percentage rate (APR) for savings accounts
            interest_accrual_date: Day of month (1-31) when interest accrues, or None for no accrual
        """
        if isinstance(account_type, str):
            try:
                account_type = AccountType[account_type.upper()]
            except KeyError:
                raise ValueError(f"Invalid account type: {account_type}. Allowed types are: {[t.value for t in AccountType]}")

        self.account_type = account_type
        self.account_name = account_name

        if balance < 0:
            raise ValueError("Starting balance cannot be negative.")
        self.balance = balance

        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative.")
        self.interest_rate = interest_rate  # Annual percentage rate

        self.interest_accrual_date = interest_accrual_date  # Day of month for interest accrual
        self.transaction_history: list[dict] = []

    def deposit(self, amount: float, description: str = "Deposit", transaction_date: date = None):
        if amount < 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance += amount
        self._record_transaction("DEPOSIT", amount, description, transaction_date)

    def withdraw(self, amount: float, description: str = "Withdrawal", transaction_date: date = None):
        if amount < 0:
            raise ValueError("Withdrawal amount must be positive.")
        if self.balance < amount:
            raise ValueError(f"Insufficient funds. Balance: {self.balance}, Requested: {amount}")
        self.balance -= amount
        self._record_transaction("WITHDRAWAL", -amount, description, transaction_date)

    def _record_transaction(self, trans_type: str, amount: float, description: str, trans_date: date = None):
        """Record a transaction in history."""
        self.transaction_history.append({
            "type": trans_type,
            "amount": amount,
            "description": description,
            "date": trans_date or date.today(),
            "balance_after": self.balance
        })

    def accrue_interest(self, current_date: date = None) -> float:
        """
        Accrue interest on the account balance.
        Only applies to savings accounts.
        Returns the interest amount accrued.
        """
        if self.account_type != AccountType.SAVINGS:
            return 0.0

        if self.interest_rate <= 0:
            return 0.0

        current_date = current_date or date.today()

        # Monthly accrual by default
        monthly_rate = self.interest_rate / 12 / 100
        interest = self.balance * monthly_rate
        self.balance += interest

        self._record_transaction("INTEREST", interest, "Interest accrual", current_date)
        return interest

    def copy(self):
        """Create a deep copy of this account."""
        return deepcopy(self)

    def __repr__(self):
        return f"BankAccount({self.account_name}, {self.account_type.value}, balance=${self.balance:.2f})"
