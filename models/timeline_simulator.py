from datetime import date, timedelta
from dataclasses import dataclass

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource


@dataclass
class TimelineEvent:
    """Represents a single financial event on a specific date."""
    event_date: date
    event_type: str  # 'INCOME', 'BILL_PAYMENT', 'INTEREST', 'CREDIT_PAYMENT'
    amount: float
    description: str
    account_name: str = None
    bank_name: str = None

    def __lt__(self, other):
        """Enable sorting by date."""
        return self.event_date < other.event_date


class TimelineSimulator:
    """
    Simulates account balances and transactions over a date range.
    This enables "what-if" analysis and projection of cash flow.
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill]):
        self.banks = [b.copy() for b in banks]
        self.income_sources = [i.copy() for i in income_sources]
        self.bills = [b.copy() for b in bills]
        self.events: list[TimelineEvent] = []

    def build_timeline(
        self,
        start_date: date,
        end_date: date,
        include_interest: bool = True
    ) -> list[TimelineEvent]:
        """
        Build a chronological timeline of events (income, bills, interest) between start and end dates.

        Args:
            start_date: Simulation start date
            end_date: Simulation end date
            include_interest: Whether to include interest accrual events

        Returns:
            List of TimelineEvent objects sorted by date
        """
        self.events = []
        current_date = start_date

        while current_date <= end_date:
            # Check for income deposits on this day
            for income in self.income_sources:
                next_pay_date = income.get_next_pay_date(current_date - timedelta(days=1))
                if next_pay_date == current_date:
                    self.events.append(TimelineEvent(
                        event_date=current_date,
                        event_type="INCOME",
                        amount=income.amount,
                        description=f"Income: {income.source_name}",
                        account_name="(distributed)",
                        bank_name="(multiple)"
                    ))

            # Check for bill payments on this day
            for bill in self.bills:
                next_due = bill.get_next_due_date(current_date - timedelta(days=1))
                if next_due == current_date:
                    self.events.append(TimelineEvent(
                        event_date=current_date,
                        event_type="BILL_DUE",
                        amount=bill.amount,
                        description=f"Bill: {bill.bill_name}",
                        account_name=bill.preferred_source_account or "(unassigned)",
                        bank_name=bill.preferred_source_bank or "(unassigned)"
                    ))

            # Check for interest accrual on this day
            if include_interest:
                for bank in self.banks:
                    for account in bank.get_all_accounts():
                        if account.interest_accrual_date == current_date.day and account.interest_rate > 0:
                            monthly_rate = account.interest_rate / 12 / 100
                            interest = account.balance * monthly_rate
                            if interest > 0:
                                self.events.append(TimelineEvent(
                                    event_date=current_date,
                                    event_type="INTEREST",
                                    amount=interest,
                                    description=f"Interest accrued on {account.account_name}",
                                    account_name=account.account_name,
                                    bank_name=bank.name
                                ))

                    for credit_account in bank.get_all_credit_accounts():
                        if credit_account.statement_date == current_date.day and credit_account.interest_rate > 0 and credit_account.balance > 0:
                            monthly_rate = credit_account.interest_rate / 12 / 100
                            interest = credit_account.balance * monthly_rate
                            self.events.append(TimelineEvent(
                                event_date=current_date,
                                event_type="INTEREST",
                                amount=interest,
                                description=f"Interest accrued on {credit_account.account_name}",
                                account_name=credit_account.account_name,
                                bank_name=bank.name
                            ))

            current_date += timedelta(days=1)

        # Sort events by date
        self.events.sort()
        return self.events

    def project_balances(
        self,
        start_date: date,
        end_date: date,
        payment_strategy: dict = None
    ) -> dict:
        """
        Project account balances from start_date to end_date.

        Args:
            start_date: Simulation start date
            end_date: Simulation end date
            payment_strategy: Optional custom payment routing
                Format: {bill_name: {bank: name, account: name}}

        Returns:
            Dictionary with:
            - 'snapshots': List of balance snapshots by date
            - 'final_balances': Final balance for each account
            - 'cash_flow': List of all transactions
        """
        # Build timeline of all events
        self.build_timeline(start_date, end_date, include_interest=True)

        # Process events chronologically
        snapshots = []
        cash_flow = []

        current_date = start_date
        while current_date <= end_date:
            # Get events for this date
            day_events = [e for e in self.events if e.event_date == current_date]

            for event in sorted(day_events, key=lambda e: e.event_type):
                if event.event_type == "INCOME":
                    # Distribute income
                    for income in self.income_sources:
                        next_pay = income.get_next_pay_date(current_date - timedelta(days=1))
                        if next_pay == current_date:
                            # Distribute income across accounts (which may be in different banks)
                            if not income.distribution:
                                # Default: deposit all to the first account of first bank
                                target_bank = self.banks[0]
                                account_name = next(iter(target_bank.accounts))
                                target_bank.accounts[account_name].deposit(
                                    income.amount,
                                    description=f"Income: {income.source_name}",
                                    transaction_date=current_date
                                )
                                cash_flow.append({
                                    "date": current_date,
                                    "type": "INCOME",
                                    "description": f"{income.source_name}",
                                    "amount": income.amount,
                                    "account": account_name
                                })
                            else:
                                # Distribute according to specification
                                total_fixed = 0.0
                                remainder_account = None
                                remainder_bank = None

                                # First pass: deposit fixed amounts
                                for account_name, value in income.distribution.items():
                                    if value == "remainder":
                                        remainder_account = account_name
                                    elif isinstance(value, (int, float)) and value > 0:
                                        # Find which bank has this account
                                        target_bank = self._find_bank_with_account(account_name)
                                        if target_bank:
                                            target_bank.accounts[account_name].deposit(
                                                value,
                                                description=f"Income: {income.source_name}",
                                                transaction_date=current_date
                                            )
                                            total_fixed += value
                                            cash_flow.append({
                                                "date": current_date,
                                                "type": "INCOME",
                                                "description": f"{income.source_name}",
                                                "amount": value,
                                                "account": account_name
                                            })

                                # Second pass: handle remainder
                                if remainder_account:
                                    remainder = income.amount - total_fixed
                                    if remainder > 1e-6:
                                        target_bank = self._find_bank_with_account(remainder_account)
                                        if target_bank:
                                            target_bank.accounts[remainder_account].deposit(
                                                remainder,
                                                description=f"Income: {income.source_name} (remainder)",
                                                transaction_date=current_date
                                            )
                                            cash_flow.append({
                                                "date": current_date,
                                                "type": "INCOME",
                                                "description": f"{income.source_name} (remainder)",
                                                "amount": remainder,
                                                "account": remainder_account
                                            })

                elif event.event_type == "BILL_DUE":
                    # Find matching bill and pay it
                    for bill in self.bills:
                        next_due = bill.get_next_due_date(current_date - timedelta(days=1))
                        if next_due == current_date and event.description == f"Bill: {bill.bill_name}":
                            # Choose account to pay from
                            source_bank, source_account = self._choose_payment_account(
                                bill,
                                payment_strategy
                            )

                            if source_bank and source_account:
                                try:
                                    source_bank.accounts[source_account].withdraw(
                                        bill.amount,
                                        description=f"Payment: {bill.bill_name}",
                                        transaction_date=current_date
                                    )
                                    bill.mark_paid(source_bank.name, source_account, bill.amount, current_date)
                                    cash_flow.append({
                                        "date": current_date,
                                        "type": "BILL_PAYMENT",
                                        "description": bill.bill_name,
                                        "amount": -bill.amount,
                                        "account": source_account,
                                        "bank": source_bank.name
                                    })
                                except ValueError as e:
                                    # Insufficient funds - defer or flag
                                    cash_flow.append({
                                        "date": current_date,
                                        "type": "BILL_DEFERRED",
                                        "description": f"{bill.bill_name} (insufficient funds)",
                                        "amount": -bill.amount,
                                        "account": source_account,
                                        "bank": source_bank.name,
                                        "error": str(e)
                                    })

                elif event.event_type == "INTEREST":
                    # Process interest accrual
                    bank = self._get_bank_by_name(event.bank_name)
                    if bank:
                        interest = 0.0
                        if event.account_name in bank.accounts:
                            interest = bank.accounts[event.account_name].accrue_interest(current_date)
                        elif event.account_name in bank.credit_accounts:
                            interest = bank.credit_accounts[event.account_name].accrue_interest(current_date)

                        if interest > 0:
                            cash_flow.append({
                                "date": current_date,
                                "type": "INTEREST",
                                "description": f"Interest: {event.account_name}",
                                "amount": interest,
                                "account": event.account_name,
                                "bank": event.bank_name
                            })

            # Create snapshot for this date
            snapshot = {"date": current_date, "balances": {}}
            for bank in self.banks:
                for account in bank.get_all_accounts():
                    key = f"{bank.name}:{account.account_name}"
                    snapshot["balances"][key] = account.balance

            snapshots.append(snapshot)
            current_date += timedelta(days=1)

        # Compile final balances
        final_balances = {}
        for bank in self.banks:
            for account in bank.get_all_accounts():
                key = f"{bank.name}:{account.account_name}"
                final_balances[key] = account.balance

        return {
            "start_date": start_date,
            "end_date": end_date,
            "snapshots": snapshots,
            "final_balances": final_balances,
            "cash_flow": cash_flow,
            "events": self.events
        }

    def _get_bank_by_name(self, bank_name: str) -> Bank | None:
        """Get a bank by name."""
        for bank in self.banks:
            if bank.name == bank_name:
                return bank
        return None if bank_name else self.banks[0]

    def _find_bank_with_account(self, account_name: str) -> Bank | None:
        """Find which bank contains a specific account."""
        for bank in self.banks:
            if account_name in bank.accounts:
                return bank
        return None

    def _choose_payment_account(
        self,
        bill: Bill,
        payment_strategy: dict = None
    ) -> tuple[Bank, str] | tuple[None, None]:
        """
        Choose which account to pay a bill from.
        Priority: explicit assignment > preferred > best available.
        """
        if payment_strategy and bill.bill_name in payment_strategy:
            strat = payment_strategy[bill.bill_name]
            bank = self._get_bank_by_name(strat.get("bank"))
            account = strat.get("account")
            if bank and account and account in bank.accounts:
                return bank, account

        # Try preferred account
        if bill.preferred_source_bank and bill.preferred_source_account:
            bank = self._get_bank_by_name(bill.preferred_source_bank)
            if bank and bill.preferred_source_account in bank.accounts:
                if bank.accounts[bill.preferred_source_account].balance >= bill.amount:
                    return bank, bill.preferred_source_account

        # Choose best available account with sufficient funds
        return self._get_best_account_for_payment(bill.amount)

    def _get_best_account_for_payment(self, amount: float) -> tuple[Bank, str] | tuple[None, None]:
        """Find the best account with sufficient funds for a payment."""
        candidates = []
        for bank in self.banks:
            for name, acc in bank.accounts.items():
                if acc.balance >= amount:
                    candidates.append((bank, name, acc.balance))

        if not candidates:
            return None, None

        # Choose account with highest balance (to preserve liquidity)
        best = max(candidates, key=lambda x: x[2])
        return best[0], best[1]

