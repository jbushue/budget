from datetime import date, timedelta
from enum import Enum
from copy import deepcopy
from typing import Optional

from models.types import DistributionType, DistributionEnumType
from models.date_utils import add_months, clamped_date, next_by_days, next_by_months


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
        pay_date: list[int] | int = None,  # Day(s) of month (1-31)
        distribution: dict = None,  # {account_name: amount or "remainder"} or {account_name: percentage}
        start_date: date | None = None,
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
            start_date: Optional anchor (first pay date) for weekly, biweekly,
                bimonthly, quarterly, yearly and one-time income. Ignored for
                monthly/semimonthly income, which use the pay_date list.
        """
        if amount <= 0:
            raise ValueError("Income amount must be positive.")

        self.source_name = source_name
        self.amount = amount

        if isinstance(frequency, str):
            frequency = IncomeFrequency[frequency.upper()]
        self.frequency = frequency

        if isinstance(pay_date, int):
            pay_date = [pay_date]
        self.pay_date = pay_date  # Day(s) of month (1-31)
        self.distribution = DistributionType.__fromdict__(dist_dict=distribution)
        self.start_date = start_date  # Anchor for non-monthly frequencies

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

    # Step sizes for anchored frequencies
    _DAY_STEPS = {
        IncomeFrequency.WEEKLY: 7,
        IncomeFrequency.BIWEEKLY: 14,
    }
    _MONTH_STEPS = {
        IncomeFrequency.BIMONTHLY: 2,
        IncomeFrequency.QUARTERLY: 3,
        IncomeFrequency.YEARLY: 12,
    }
    # Weekend adjustment moves a pay date back at most this many days
    _MAX_WEEKEND_SHIFT = 2

    def _first_pay_day(self, fallback: int) -> int:
        """First configured pay day of month, or ``fallback`` when none is set."""
        if self.pay_date:
            return sorted(self.pay_date)[0]
        return fallback

    def _get_implicit_anchor(self, reference_date: date) -> date:
        """
        Fallback anchor (unadjusted first pay date) used when no ``start_date``
        is given for an anchored frequency (weekly, biweekly, bimonthly,
        quarterly, yearly, once).

        The anchor is the first date strictly after the *first* reference date
        this income is asked about that falls on the first ``pay_date`` day
        (clamped to month length); with no ``pay_date`` it is the day after
        that reference date. It is remembered on the instance so later lookups
        stay on the same cycle — e.g. a simulation starting Jan 1 anchors a
        biweekly paycheck with pay_date=[2] at Jan 2 and repeats every 14 days.
        """
        anchor = getattr(self, '_implicit_anchor', None)
        if anchor is None:
            if not self.pay_date:
                anchor = reference_date + timedelta(days=1)
            else:
                day = self._first_pay_day(reference_date.day)
                anchor = clamped_date(reference_date.year, reference_date.month, day)
                if anchor <= reference_date:
                    y, m = add_months(reference_date.year, reference_date.month, 1)
                    anchor = clamped_date(y, m, day)
            self._implicit_anchor = anchor
        return anchor

    def _raw_pay_dates(self, start_date: date, end_date: date) -> list[date]:
        """
        Unadjusted (pre-weekend-shift) pay dates in (start_date, end_date],
        according to the income frequency.
        """
        raw = []
        frequency = self.frequency
        anchor = getattr(self, 'start_date', None)

        if frequency == IncomeFrequency.ONCE:
            occurrence = anchor or self._get_implicit_anchor(start_date)
            if start_date < occurrence <= end_date:
                raw.append(occurrence)
            return raw

        if frequency in self._DAY_STEPS:
            step = self._DAY_STEPS[frequency]
            if anchor is None:
                anchor = self._get_implicit_anchor(start_date)
            current = next_by_days(anchor, step, start_date, allow_before=False)
            while current <= end_date:
                raw.append(current)
                current += timedelta(days=step)
            return raw

        if frequency in self._MONTH_STEPS:
            step = self._MONTH_STEPS[frequency]
            if anchor is not None:
                a_year, a_month, day, allow_before = anchor.year, anchor.month, anchor.day, False
            else:
                implicit = self._get_implicit_anchor(start_date)
                a_year, a_month, allow_before = implicit.year, implicit.month, True
                day = self._first_pay_day(implicit.day)
            current = next_by_months(a_year, a_month, day, step, start_date, allow_before)
            while current <= end_date:
                raw.append(current)
                current = next_by_months(a_year, a_month, day, step, current, allow_before)
            return raw

        # MONTHLY / SEMIMONTHLY: every configured pay day of every month
        if self.pay_date is None or len(self.pay_date) == 0:
            # No specific pay dates, use the start_date's day as the pay day
            pay_date_list = [start_date.day]
        else:
            pay_date_list = sorted(self.pay_date)

        year, month = start_date.year, start_date.month
        while date(year, month, 1) <= end_date:
            for pay_day in pay_date_list:
                # Handle month-end edge cases (e.g., 31st in February)
                candidate = clamped_date(year, month, pay_day)
                if start_date < candidate <= end_date:
                    raw.append(candidate)
            year, month = add_months(year, month, 1)
        return raw

    def get_pay_dates_in_range(self, start_date: date, end_date: date) -> list[date]:
        """
        Get all pay dates that fall within a date range.

        Monthly/semimonthly income returns every configured ``pay_date`` day
        (e.g. both the 15th and the 31st, clamped to month length). Weekly,
        biweekly, bimonthly, quarterly, yearly and one-time income follow
        their frequency from ``start_date`` (or the implicit anchor, see
        ``_get_implicit_anchor``). Pay dates that fall on weekends are
        adjusted to the Friday before — including a paycheck whose raw date is
        just past ``end_date`` but shifts back into the range.

        Args:
            start_date: Start of the date range (exclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of dates when income is received within the range
        """
        # Look a couple of days past end_date: a Saturday/Sunday pay date
        # right after the window shifts back to the Friday inside it.
        lookahead_end = end_date + timedelta(days=self._MAX_WEEKEND_SHIFT)
        pay_dates = set()
        for raw_pay_date in self._raw_pay_dates(start_date, lookahead_end):
            adjusted_pay_date = self._adjust_for_weekend(raw_pay_date)
            if start_date < adjusted_pay_date <= end_date:
                pay_dates.add(adjusted_pay_date)
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
        distribution_obj: DistributionType = DistributionType.__fromdict__(override_distribution) if isinstance(override_distribution, dict) else None
        distribution_obj = distribution_obj or self.distribution
        deposits = {}
        if distribution_obj is None:
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
        
        distribution = distribution_obj.__todict__()
        deposit_date = deposit_date or date.today()

        # Check if using percentages (sum to ~1.0) or fixed amounts
        is_percentage = all(0 <= v <= 1 for v in distribution.values() if isinstance(v, (int, float)))

        total_fixed = 0.0
        remainder_account = None

        for account_name, value in distribution.items():
            distribution_type = distribution_obj.get_distribution_type(account_name)
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
        Calculate the next pay date strictly after a reference date.

        Honors the income frequency (see ``get_pay_dates_in_range``), handles
        multiple pay days per month for semimonthly income (e.g. [15, 31]),
        and adjusts weekend pay dates to the Friday before. Returns
        ``date.max`` for one-time income whose pay date has already passed.
        """
        window_days = 400  # covers every frequency, including yearly
        window_start = reference_date
        for _ in range(3):
            window_end = window_start + timedelta(days=window_days)
            upcoming = self.get_pay_dates_in_range(window_start, window_end)
            if upcoming:
                return upcoming[0]
            if self.frequency == IncomeFrequency.ONCE:
                break
            window_start = window_end
        return date.max

    def copy(self):
        """Create a deep copy of this income source."""
        return deepcopy(self)

    def __repr__(self):
        return f"IncomeSource({self.source_name}, ${self.amount:.2f}, {self.frequency.value})"
