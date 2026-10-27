"""
Bill Group model for bundling multiple credit/loan accounts into a single payment.

Use case: Student loans where a servicer collects one lump payment and distributes
it across individual sub-loans. Also works for any bundled-payment scenario.
"""

from datetime import date, timedelta
from copy import deepcopy
from dataclasses import dataclass, field

from .types import AllocationMethod, BillFrequency
from .date_utils import next_by_months


@dataclass
class BillGroupMember:
    """A single account that belongs to a bill group."""
    bank_name: str
    account_name: str
    allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL
    fixed_amount: float = 0.0  # Only used when allocation_method == FIXED

    def to_dict(self) -> dict:
        return {
            "bank_name": self.bank_name,
            "account_name": self.account_name,
            "allocation_method": self.allocation_method.value,
            "fixed_amount": self.fixed_amount,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BillGroupMember":
        return cls(
            bank_name=data["bank_name"],
            account_name=data["account_name"],
            allocation_method=AllocationMethod(data.get("allocation_method", "proportional")),
            fixed_amount=data.get("fixed_amount", 0.0),
        )


class BillGroup:
    """
    Groups multiple credit/loan accounts into a single bundled payment.

    The group tracks:
    - A human-readable name (e.g. "Federal Student Loans")
    - A total payment amount (the single lump-sum payment you make)
    - A due date (day of month) + frequency
    - A list of member accounts with allocation rules
    - A preferred source account (where the lump payment comes from)
    """

    def __init__(
        self,
        group_name: str,
        total_payment: float,
        due_date: int,
        frequency: BillFrequency = BillFrequency.MONTHLY,
        group_type: str = "student_loan",
        preferred_source_bank: str = None,
        preferred_source_account: str = None,
        members: list[BillGroupMember] = None,
    ):
        if total_payment < 0:
            raise ValueError("Total payment cannot be negative.")
        if not (1 <= due_date <= 31):
            raise ValueError("Due date must be between 1 and 31.")

        self.group_name = group_name
        self.total_payment = total_payment
        self.due_date = due_date
        self.frequency = frequency if isinstance(frequency, BillFrequency) else BillFrequency(frequency)
        self.group_type = group_type  # "student_loan", "bundled_bill", etc.
        self.preferred_source_bank = preferred_source_bank
        self.preferred_source_account = preferred_source_account
        self.created_on: date = date.today()  # restored from the database on load
        self.members: list[BillGroupMember] = members or []
        self.is_paid_this_period: bool = False
        self.payment_history: list[dict] = []

    # ── Member management ──

    def add_member(
        self,
        bank_name: str,
        account_name: str,
        allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL,
        fixed_amount: float = 0.0,
    ) -> BillGroupMember:
        """Add a credit/loan account to this group."""
        # Prevent duplicate membership
        for m in self.members:
            if m.bank_name == bank_name and m.account_name == account_name:
                raise ValueError(
                    f"Account '{account_name}' at '{bank_name}' is already a member of group '{self.group_name}'."
                )
        member = BillGroupMember(
            bank_name=bank_name,
            account_name=account_name,
            allocation_method=allocation_method,
            fixed_amount=fixed_amount,
        )
        self.members.append(member)
        return member

    def remove_member(self, bank_name: str, account_name: str) -> bool:
        """Remove a member account. Returns True if found and removed."""
        for i, m in enumerate(self.members):
            if m.bank_name == bank_name and m.account_name == account_name:
                self.members.pop(i)
                return True
        return False

    # ── Balance helpers ──

    def get_total_balance(self, banks: list) -> float:
        """Sum current balance across all member accounts."""
        total = 0.0
        for member in self.members:
            acc = self._resolve_account(member, banks)
            if acc:
                total += acc.balance
        return total

    def get_member_details(self, banks: list) -> list[dict]:
        """Return per-member details including current balance."""
        details = []
        for member in self.members:
            acc = self._resolve_account(member, banks)
            details.append({
                "bank_name": member.bank_name,
                "account_name": member.account_name,
                "balance": acc.balance if acc else 0.0,
                "interest_rate": acc.interest_rate if acc else 0.0,
                "allocation_method": member.allocation_method.value,
                "fixed_amount": member.fixed_amount,
            })
        return details

    # ── Payment distribution ──

    def distribute_payment(self, payment_amount: float, banks: list, payment_date: date = None) -> list[dict]:
        """
        Distribute a lump payment across member accounts.

        The full ``payment_amount`` is applied whenever the members' combined
        balance allows it: allocations are capped at each member's balance and
        any excess (or any amount left unallocated, e.g. fixed amounts summing
        to less than the payment) is redistributed to members that still owe,
        proportional to their remaining balance. The sum of the returned
        sub-payment amounts is what was actually applied.

        Returns a list of dicts describing each sub-payment:
            [{"bank_name", "account_name", "amount", "balance_after"}, ...]
        """
        payment_date = payment_date or date.today()
        results = []

        # Resolve accounts and compute allocations
        resolved = []
        for member in self.members:
            acc = self._resolve_account(member, banks)
            if acc and acc.balance > 0:
                resolved.append((member, acc))

        if not resolved:
            return results

        planned = self.plan_amounts(resolved, payment_amount)

        for (member, acc), amount in zip(resolved, planned):
            # Round to cents but never exceed the member's balance
            actual = min(round(amount, 2), acc.balance)
            if actual > 0:
                acc.make_payment(actual, transaction_date=payment_date)
                results.append({
                    "bank_name": member.bank_name,
                    "account_name": member.account_name,
                    "amount": round(actual, 2),
                    "balance_after": round(acc.balance, 2),
                })

        return results

    def plan_amounts(self, resolved: list[tuple], payment_amount: float) -> list[float]:
        """
        How much of ``payment_amount`` each (member, account) in ``resolved``
        receives, after capping at member balances and redistributing any
        excess. Pure: moves no money (used by distribute_payment and by the
        payment insights analyzer to preview splits).
        """
        allocations = self._compute_allocations(resolved, payment_amount)

        # Cap each allocation at the member's balance
        balances = [acc.balance for _, acc in resolved]
        planned = [max(0.0, min(amount, bal)) for amount, bal in zip(allocations, balances)]

        # Redistribute whatever was not applied to members with room left
        leftover = payment_amount - sum(planned)
        if leftover > 0.005:
            room = [bal - amt for amt, bal in zip(planned, balances)]
            total_room = sum(r for r in room if r > 0)
            if total_room > 0:
                if leftover >= total_room:
                    planned = list(balances)
                else:
                    planned = [
                        amt + (leftover * r / total_room if r > 0 else 0.0)
                        for amt, r in zip(planned, room)
                    ]
        return planned

    def _compute_allocations(
        self,
        resolved: list[tuple],
        payment_amount: float,
    ) -> list[float]:
        """
        Compute how much each member gets from the lump payment (before
        capping at member balances — see distribute_payment).

        FIXED members are paid first, scaled down proportionally if their sum
        exceeds the payment. The remainder is split among the non-fixed
        members: equally if they all use EQUAL, otherwise proportionally by
        balance. ``resolved`` only contains members with a balance, so EQUAL
        never allocates to zero-balance members. (Mirrored by the web UI's
        "Est. Payment" column.)
        """
        payment_amount = max(0.0, payment_amount)
        allocations = [0.0] * len(resolved)

        fixed_idx = [i for i, (m, _) in enumerate(resolved)
                     if m.allocation_method == AllocationMethod.FIXED]
        other_idx = [i for i, (m, _) in enumerate(resolved)
                     if m.allocation_method != AllocationMethod.FIXED]

        # Fixed amounts can never exceed the payment
        fixed_total = sum(max(0.0, resolved[i][0].fixed_amount) for i in fixed_idx)
        fixed_scale = 1.0
        if fixed_total > payment_amount and fixed_total > 0:
            fixed_scale = payment_amount / fixed_total
        for i in fixed_idx:
            allocations[i] = max(0.0, resolved[i][0].fixed_amount) * fixed_scale

        remaining = max(0.0, payment_amount - fixed_total * fixed_scale)
        if not other_idx or remaining <= 0:
            return allocations

        all_equal = all(resolved[i][0].allocation_method == AllocationMethod.EQUAL for i in other_idx)
        if all_equal:
            per_member = remaining / len(other_idx)
            for i in other_idx:
                allocations[i] = per_member
            return allocations

        total_bal = sum(max(0.0, resolved[i][1].balance) for i in other_idx)
        for i in other_idx:
            if total_bal > 0:
                allocations[i] = (max(0.0, resolved[i][1].balance) / total_bal) * remaining
            else:
                allocations[i] = remaining / len(other_idx)
        return allocations

    # ── Due-date helpers ──

    def get_next_due_date(self, reference_date: date) -> date:
        """Calculate next monthly due date after reference_date (day clamped to month length)."""
        return next_by_months(reference_date.year, reference_date.month, self.due_date, 1, reference_date)

    def mark_paid(self, payment_date: date = None):
        """Mark this group payment as paid for the current period."""
        self.is_paid_this_period = True
        self.payment_history.append({
            "date": payment_date or date.today(),
            "amount": self.total_payment,
        })

    def reset_period(self):
        """Reset paid status for next billing period."""
        self.is_paid_this_period = False

    @property
    def last_paid_date(self):
        """Date of the most recent group payment, or None."""
        if not self.payment_history:
            return None
        return self.payment_history[-1].get("date")

    # ── Utility ──

    def _resolve_account(self, member: BillGroupMember, banks: list):
        """Find the CreditAccount for a member."""
        for bank in banks:
            if bank.name == member.bank_name:
                return bank.credit_accounts.get(member.account_name)
        return None

    def get_grouped_account_keys(self) -> set[tuple[str, str]]:
        """Return a set of (bank_name, account_name) tuples for all members."""
        return {(m.bank_name, m.account_name) for m in self.members}

    def copy(self):
        """Create a deep copy for simulation."""
        return deepcopy(self)

    def __repr__(self):
        return (
            f"BillGroup({self.group_name}, ${self.total_payment:.2f}, "
            f"{len(self.members)} members, due day {self.due_date})"
        )

