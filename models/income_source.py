from datetime import date
from enum import Enum
from copy import deepcopy
from typing import Optional

from models.types import DistributionType, DistributionEnumType


class IncomeFrequency(Enum):
    ONCE = "once"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    SEMIMONTHLY = "semimonthly"  # Twice a month
    BIMONTHLY = "bimonthly" # Every two months
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class IncomeSource:
    """Represents a source of income with flexible distribution across accounts."""

    def __init__(
        self,
        source_name: str,
        amount: float,
        frequency: IncomeFrequency = IncomeFrequency.MONTHLY,
        pay_date: list[int] = None,  # Day(s) of month (1-31)
        distribution: dict = None  # {account_name: amount or "remainder"} or {account_name: percentage}
    ):
        """
        Args:
            source_name: Name of income source
            amount: Amount of income per period
            frequency: 'monthly', 'weekly', 'biweekly', etc.
            pay_date: Day of month when paid (1-31), or None for custom
            distribution: How to distribute income across accounts
                Example: {"checking": 1000, "savings": "remainder"}
                Example: {"checking": 0.8, "savings": 0.2}  # percentages
        """
        if amount <= 0:
            raise ValueError("Income amount must be positive.")

        self.source_name = source_name
        self.amount = amount

        if isinstance(frequency, str):
            frequency = IncomeFrequency[frequency.upper()]
        self.frequency = frequency

        self.pay_date = pay_date  # Day of month (1-31)
        self.distribution = DistributionType.__fromdict__(dist_dict=distribution)

        # Tracking
        self.deposit_history: list[dict] = []
        self.last_deposited_date: Optional[date] = None

    def validate_distribution(self, bank) -> bool:
        """Validate that distribution accounts exist in the bank."""

        for account_name in self.distribution.__todict__().keys():
            if account_name not in bank.accounts:
                raise ValueError(f"Account '{account_name}' does not exist in the bank ({bank}).")
        return True

    def deposit_to_bank(
        self,
        bank,
        override_distribution: dict = None,
        deposit_date: date = None
    ) -> dict:
        """
        Deposit income to the bank's accounts according to distribution.

        Args:
            bank: Bank instance to deposit to
            override_distribution: Override the default distribution
            deposit_date: Date of deposit (default: today)

        Returns:
            Dictionary of {account_name: amount_deposited}
        """
        distribution_obj: DistributionType = DistributionType.__fromdict__(override_distribution) or self.distribution
        distribution = distribution_obj.__todict__()
        deposit_date = deposit_date or date.today()
        deposits = {}

        if not distribution:
            # Default: deposit all to the first account
            account_name = next(iter(bank.accounts))
            bank.accounts[account_name].deposit(
                self.amount,
                description=f"Income: {self.source_name}",
                transaction_date=deposit_date
            )
            deposits[account_name] = self.amount
            self.last_deposited_date = deposit_date
            self._record_deposit(account_name, self.amount, deposit_date)
            return deposits

        # Check if using percentages (sum to ~1.0) or fixed amounts
        is_percentage = all(0 <= v <= 1 for v in distribution.values() if isinstance(v, (int, float)))

        total_fixed = 0.0
        remainder_account = None

        for account_name, value, distribution_type in distribution.items():
            if value is None and distribution_type == DistributionEnumType.REMAINDER:
                if remainder_account is not None:
                    raise ValueError("Only one account can be set as 'remainder'.")
                remainder_account = account_name
            elif isinstance(value, (int, float)):
                if is_percentage and value > 0:
                    # Treat as percentage
                    amount = self.amount * value
                else:
                    # Treat as fixed amount
                    amount = value
                    total_fixed += amount

                if account_name not in bank.accounts:
                    raise ValueError(f"Account '{account_name}' does not exist in the bank.")

                bank.accounts[account_name].deposit(
                    amount,
                    description=f"Income: {self.source_name}",
                    transaction_date=deposit_date
                )
                deposits[account_name] = amount
                self._record_deposit(account_name, amount, deposit_date)

        # Handle remainder
        if remainder_account:
            if is_percentage:
                remainder = self.amount - sum(
                    self.amount * v for v in distribution.values()
                    if isinstance(v, (int, float)) and v != "remainder"
                )
            else:
                remainder = self.amount - total_fixed

            if remainder < -1e-6:
                raise ValueError(f"Distributed amounts exceed total income. Deficit: {-remainder:.2f}")

            if remainder > 1e-6:
                if remainder_account not in bank.accounts:
                    raise ValueError(f"Account '{remainder_account}' does not exist in the bank.")

                bank.accounts[remainder_account].deposit(
                    remainder,
                    description=f"Income: {self.source_name} (remainder)",
                    transaction_date=deposit_date
                )
                deposits[remainder_account] = remainder
                self._record_deposit(remainder_account, remainder, deposit_date)

        elif not is_percentage:
            # Fixed amounts and no remainder specified
            if abs(total_fixed - self.amount) > 1e-6:
                raise ValueError(
                    f"Distributed amounts ({total_fixed:.2f}) do not sum to total income ({self.amount:.2f}) "
                    "and no remainder account specified."
                )

        self.last_deposited_date = deposit_date
        return deposits

    def _record_deposit(self, account_name: str, amount: float, deposit_date: date):
        """Record a deposit in history."""
        self.deposit_history.append({
            "date": deposit_date,
            "account_name": account_name,
            "amount": amount
        })

    def get_next_pay_date(self, reference_date: date) -> date:
        """Calculate the next pay date relative to a reference date."""
        year = reference_date.year
        month = reference_date.month

        if self.pay_date is None:
            # No specific pay date, assume same day of month
            try:
                next_pay = date(year, month, reference_date.day)
            except ValueError:
                next_pay = date(year, month, 28)
        else:
            try:
                for day in sorted(self.pay_date):
                    check_pay = date(year, month, day)
                    if check_pay < reference_date:
                        continue
                    next_pay = check_pay
                    break
                else:
                    next_pay = date(year, month, sorted(self.pay_date)[0])

            except ValueError:
                # Handle month-end edge cases
                next_pay = date(year, month, min(sorted(self.pay_date)[0], 28))

        if next_pay <= reference_date:
            # Pay date has passed this month, move to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

            try:
                next_pay = date(year, month, self.pay_date)
            except ValueError:
                next_pay = date(year, month, min(self.pay_date, 28))

        return next_pay

    def copy(self):
        """Create a deep copy of this income source."""
        return deepcopy(self)

    def __repr__(self):
        return f"IncomeSource({self.source_name}, ${self.amount:.2f}, {self.frequency.value})"
