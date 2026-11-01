from datetime import date
from enum import Enum
from copy import deepcopy
from .types import AccountType, account_kind


class BankAccount:
    """
    A cash-type account: checking, savings, money market, CD, cash, prepaid,
    payment app, EBT, HSA/FSA, brokerage, retirement or other (see
    models.types.ACCOUNT_KINDS for how each kind is treated).

    Optional extras, used by the projection:
      refill_amount / refill_day  money added on a day each month (EBT benefits,
                                  HSA contributions) without coming from checking
      weekly_spending             spent from this account each week (e.g. groceries on EBT)
      offsets_everyday            that spending replaces part of your everyday
                                  spending (so it doesn't also come out of checking)
    """

    def __init__(
        self,
        account_type: str | AccountType,
        account_name: str,
        balance: float = 0.0,
        interest_rate: float = 0.0,
        interest_accrual_date: int = None,
        refill_amount: float = 0.0,
        refill_day: int | None = None,
        weekly_spending: float = 0.0,
        offsets_everyday: bool = False,
    ):
        """
        Args:
            account_type: 'checking', 'savings', or AccountType enum
            account_name: Human-readable name for the account
            balance: Starting balance (must be >= 0)
            interest_rate: Annual percentage rate (APR) for savings accounts
            interest_accrual_date: Day of month (1-31) when interest is paid, or None for the end of each month
        """
        if isinstance(account_type, str):
            try:
                account_type = AccountType(account_type.lower())
            except ValueError:
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
        if (refill_amount or 0) < 0 or (weekly_spending or 0) < 0:
            raise ValueError("Refill and weekly spending can't be negative.")
        if refill_day is not None and not (1 <= int(refill_day) <= 31):
            raise ValueError("Refill day must be between 1 and 31.")
        self.refill_amount = float(refill_amount or 0.0)
        self.refill_day = int(refill_day) if refill_day else None
        self.weekly_spending = float(weekly_spending or 0.0)
        self.offsets_everyday = bool(offsets_everyday)
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

    def accrue_interest(self, current_date: date = None, average_balance: float = None) -> float:
        """
        Accrue interest on the account balance.
        Applies to kinds that earn (savings, money market, CD, HSA,
        investments — for those the rate is the expected yearly growth).

        ``average_balance``: the average daily balance over the month, when
        known (the timeline simulation tracks it); otherwise today's balance.
        Returns the interest amount accrued.
        """
        if not account_kind(self)["earns"]:
            return 0.0

        if self.interest_rate <= 0:
            return 0.0

        current_date = current_date or date.today()

        # Monthly accrual by default
        monthly_rate = self.interest_rate / 12 / 100
        base = self.balance if average_balance is None else average_balance
        interest = max(0.0, base) * monthly_rate
        self.balance += interest

        self._record_transaction("INTEREST", interest, "Interest accrual", current_date)
        return interest

    def copy(self):
        """Create a deep copy of this account."""
        return deepcopy(self)

    def __repr__(self):
        return f"BankAccount({self.account_name}, {self.account_type.value}, balance=${self.balance:.2f})"
