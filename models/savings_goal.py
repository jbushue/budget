"""Savings Goals - Track progress toward financial targets."""

from dataclasses import dataclass
from datetime import date
from copy import deepcopy


@dataclass
class SavingsGoal:
    """A named savings target linked to an account."""
    name: str
    target_amount: float
    linked_bank: str
    linked_account: str
    target_date: str | None = None  # ISO date string
    notes: str = ""

    @property
    def current_amount(self) -> float:
        """Current amount is set externally from account balance."""
        return getattr(self, '_current_amount', 0.0)

    @current_amount.setter
    def current_amount(self, value: float):
        self._current_amount = value

    @property
    def progress_pct(self) -> float:
        if self.target_amount <= 0:
            return 100.0
        return min(100.0, (self.current_amount / self.target_amount) * 100)

    @property
    def remaining(self) -> float:
        return max(0.0, self.target_amount - self.current_amount)

    def monthly_contribution_needed(self) -> float | None:
        """Calculate monthly contribution needed to reach goal by target date."""
        if not self.target_date or self.remaining <= 0:
            return None
        try:
            target = date.fromisoformat(self.target_date)
            today = date.today()
            months_left = (target.year - today.year) * 12 + (target.month - today.month)
            if months_left <= 0:
                return self.remaining
            return round(self.remaining / months_left, 2)
        except Exception:
            return None

    def copy(self):
        return deepcopy(self)

