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

    @staticmethod
    def _adjust_for_weekend(pay_date: date) -> date:
        """
        Adjust a pay date that falls on a weekend to the Friday before.
        
        Args:
            pay_date: The original pay date
            
        Returns:
            The adjusted pay date (Friday if original was Saturday/Sunday)
        """
        from datetime import timedelta
        
        weekday = pay_date.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
        if weekday == 5:  # Saturday
            return pay_date - timedelta(days=1)  # Move to Friday
        elif weekday == 6:  # Sunday
            return pay_date - timedelta(days=2)  # Move to Friday
        return pay_date

    def get_pay_dates_in_range(self, start_date: date, end_date: date) -> list[date]:
        """
        Get all pay dates that fall within a date range.
        
        For semimonthly income, this returns all pay dates (e.g., both 15th and 31st)
        that fall within the range. Pay dates that fall on weekends are adjusted
        to the Friday before.
        
        Args:
            start_date: Start of the date range (exclusive)
            end_date: End of the date range (inclusive)
            
        Returns:
            List of dates when income is received within the range
        """
        import calendar
        
        pay_dates = []
        
        if self.pay_date is None or len(self.pay_date) == 0:
            # No specific pay dates, use the start_date's day as the pay day
            pay_day = start_date.day
            pay_date_list = [pay_day]
        else:
            pay_date_list = sorted(self.pay_date)
        
        # Iterate through each month in the range
        current_year = start_date.year
        current_month = start_date.month
        
        while True:
            for pay_day in pay_date_list:
                # Handle month-end edge cases (e.g., 31st in February)
                last_day_of_month = calendar.monthrange(current_year, current_month)[1]
                actual_day = min(pay_day, last_day_of_month)
                
                try:
                    raw_pay_date = date(current_year, current_month, actual_day)
                    # Adjust for weekends - move to Friday before
                    adjusted_pay_date = self._adjust_for_weekend(raw_pay_date)
                    if start_date < adjusted_pay_date <= end_date:
                        pay_dates.append(adjusted_pay_date)
                except ValueError:
                    continue
            
            # Move to next month
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1
            
            # Stop if we've passed the end date
            if date(current_year, current_month, 1) > end_date:
                break
        
        return sorted(pay_dates)

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
        """
        Calculate the next pay date relative to a reference date.
        
        For semimonthly income, this handles multiple pay dates per month
        (e.g., [15, 31] for 15th and last day of month).
        
        Pay dates that fall on weekends are adjusted to the Friday before.
        """
        year = reference_date.year
        month = reference_date.month

        if self.pay_date is None or len(self.pay_date) == 0:
            # No specific pay date, assume same day of month
            try:
                next_pay = date(year, month, reference_date.day)
            except ValueError:
                next_pay = date(year, month, 28)
            
            # Adjust for weekends
            next_pay = self._adjust_for_weekend(next_pay)
            
            if next_pay <= reference_date:
                # Pay date has passed this month, move to next month
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                try:
                    next_pay = date(year, month, reference_date.day)
                except ValueError:
                    next_pay = date(year, month, 28)
                next_pay = self._adjust_for_weekend(next_pay)
            return next_pay

        # Handle list of pay dates (e.g., [15, 31] for semimonthly)
        sorted_pay_dates = sorted(self.pay_date)
        
        # Helper function to get valid date (handles month-end edge cases like 31st in Feb)
        def get_valid_date(y: int, m: int, day: int) -> date:
            import calendar
            last_day_of_month = calendar.monthrange(y, m)[1]
            actual_day = min(day, last_day_of_month)
            return date(y, m, actual_day)
        
        # Look for next pay date in current month
        for day in sorted_pay_dates:
            try:
                raw_date = get_valid_date(year, month, day)
                # Adjust for weekends
                check_date = self._adjust_for_weekend(raw_date)
                if check_date > reference_date:
                    return check_date
            except ValueError:
                continue
        
        # No valid pay date found in current month, move to next month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        
        # Return first pay date of next month (adjusted for weekends)
        raw_date = get_valid_date(year, month, sorted_pay_dates[0])
        return self._adjust_for_weekend(raw_date)

    def copy(self):
        """Create a deep copy of this income source."""
        return deepcopy(self)

    def __repr__(self):
        return f"IncomeSource({self.source_name}, ${self.amount:.2f}, {self.frequency.value})"
