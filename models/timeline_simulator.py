from datetime import date, timedelta
from dataclasses import dataclass

from models.bank import Bank
from models.fixed_bill import Bill, AccountLinkedBill, GroupLinkedBill
from models.bill_group import BillGroup
from models.income_source import IncomeSource
from models.date_utils import is_clamped_day


@dataclass
class TimelineEvent:
    """Represents a single financial event on a specific date."""
    event_date: date
    event_type: str  # 'INCOME', 'BILL_DUE', 'INTEREST', 'BILL_GROUP_PAYMENT',
                     # 'SAVINGS_SWEEP', 'SAVINGS_RECALL', 'EXTRA_CREDIT_PAYMENT',
                     # 'PROMO_PAYOFF', 'HELOC_PARK', 'HELOC_RECALL'
    amount: float
    description: str
    account_name: str = None
    bank_name: str = None
    # Extended fields for optimization events
    from_bank: str = None
    from_account: str = None
    to_bank: str = None
    to_account: str = None
    # PROMO_PAYOFF: name of the promotional balance being paid off
    promo_name: str = None
    # INTEREST: 'bank', 'credit', or 'heloc' (which account collection)
    account_kind: str = None

    def __lt__(self, other):
        """Enable sorting by date."""
        return self.event_date < other.event_date


class TimelineSimulator:
    """
    Simulates account balances and transactions over a date range.
    This enables "what-if" analysis and projection of cash flow.
    
    All account payments (credit, mortgage, HELOC) are now represented as
    AccountLinkedBill objects in self.bills, so they are processed uniformly
    through the BILL_DUE event type.
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill], bill_groups: list[BillGroup] = None):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills
        self.bill_groups = bill_groups or []
        self.events: list[TimelineEvent] = []

        # Pre-compute grouped account keys so we can suppress individual linked bill events
        self._grouped_account_keys: set[tuple[str, str]] = set()
        for group in self.bill_groups:
            self._grouped_account_keys.update(group.get_grouped_account_keys())

        # Ensure every bill group has a GroupLinkedBill in self.bills
        existing_group_keys = set()
        for bill in self.bills:
            if isinstance(bill, GroupLinkedBill):
                existing_group_keys.add(bill.group_link_key)
        for group in self.bill_groups:
            key = f"group:{group.group_name}"
            if key not in existing_group_keys:
                self.bills.append(GroupLinkedBill(linked_group=group))


    def build_timeline(
        self,
        start_date: date,
        end_date: date,
        include_interest: bool = True
    ) -> list[TimelineEvent]:
        """
        Build a chronological timeline of events between start and end dates.
        
        All payment types (regular bills, credit cards, mortgages, HELOCs) are
        now unified through self.bills and generate BILL_DUE events.

        Args:
            start_date: Simulation start date
            end_date: Simulation end date
            include_interest: Whether to include interest accrual events

        Returns:
            List of TimelineEvent objects sorted by date
        """
        self.events = []
        
        # Pre-calculate all income pay dates in the range using get_pay_dates_in_range
        income_pay_dates = {}
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            income_pay_dates[income.source_name] = set(pay_dates)
        
        current_date = start_date

        while current_date <= end_date:
            # Check for income deposits on this day
            for income in self.income_sources:
                if current_date in income_pay_dates.get(income.source_name, set()):
                    self.events.append(TimelineEvent(
                        event_date=current_date,
                        event_type="INCOME",
                        amount=income.amount,
                        description=f"Income: {income.source_name}",
                        account_name="(distributed)",
                        bank_name="(multiple)"
                    ))

            # Check for bill payments on this day — covers ALL bill types
            # including AccountLinkedBill for credit/mortgage/HELOC
            # and GroupLinkedBill for bill groups
            for bill in self.bills:
                # Skip linked credit bills whose account is in a bill group
                if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'credit':
                    if (bill.linked_bank_name, bill.linked_account.account_name) in self._grouped_account_keys:
                        continue
                    # Skip zero-balance credit cards
                    if bill.linked_account.balance <= 0 and bill.amount_on(current_date) <= 0:
                        continue

                # Skip linked HELOC bills with zero balance
                if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'heloc':
                    if bill.linked_account.balance <= 0 and bill.amount_on(current_date) <= 0:
                        continue

                next_due = bill.get_next_due_date(current_date - timedelta(days=1))
                if next_due == current_date:
                    # Use BILL_GROUP_PAYMENT event type for group-linked bills
                    event_type = "BILL_GROUP_PAYMENT" if isinstance(bill, GroupLinkedBill) else "BILL_DUE"
                    self.events.append(TimelineEvent(
                        event_date=current_date,
                        event_type=event_type,
                        # Resolve dynamic (linked) amounts as of the simulated date
                        amount=bill.amount_on(current_date),
                        description=f"Bill: {bill.bill_name}",
                        account_name=bill.preferred_source_account or "(unassigned)",
                        bank_name=bill.preferred_source_bank or "(unassigned)"
                    ))


            # Check for interest accrual on this day
            # Accrual days are clamped to the month length (day 31 accrues on
            # Feb 28, Apr 30, ...) so short months are not skipped.
            if include_interest:
                for bank in self.banks:
                    for account in bank.get_all_accounts():
                        if (account.interest_accrual_date
                                and is_clamped_day(current_date, account.interest_accrual_date)
                                and account.interest_rate > 0):
                            # Balance-independent: the actual amount is computed when the
                            # event is processed (money may be swept in mid-simulation);
                            # zero-interest events are dropped from the processed list.
                            monthly_rate = account.interest_rate / 12 / 100
                            interest = max(0.0, account.balance * monthly_rate)
                            self.events.append(TimelineEvent(
                                event_date=current_date,
                                event_type="INTEREST",
                                amount=interest,
                                description=f"Interest accrued on {account.account_name}",
                                account_name=account.account_name,
                                bank_name=bank.name,
                                account_kind="bank",
                            ))

                    for credit_account in bank.get_all_credit_accounts():
                        if (credit_account.statement_date
                                and is_clamped_day(current_date, credit_account.statement_date)
                                and credit_account.interest_rate > 0):
                            monthly_rate = credit_account.interest_rate / 12 / 100
                            interest = credit_account.balance * monthly_rate
                            self.events.append(TimelineEvent(
                                event_date=current_date,
                                event_type="INTEREST",
                                amount=interest,
                                description=f"Interest accrued on {credit_account.account_name}",
                                account_name=credit_account.account_name,
                                bank_name=bank.name,
                                account_kind="credit",
                            ))

                    # HELOC interest accrues monthly on the payment due day and
                    # is processed before that day's bills, so the payment
                    # (interest-only during the draw period) covers it.
                    for heloc in bank.get_all_heloc_accounts():
                        if (is_clamped_day(current_date, heloc.payment_due_date)
                                and heloc.interest_rate > 0):
                            self.events.append(TimelineEvent(
                                event_date=current_date,
                                event_type="INTEREST",
                                amount=heloc.current_monthly_interest,
                                description=f"Interest accrued on {heloc.account_name}",
                                account_name=heloc.account_name,
                                bank_name=bank.name,
                                account_kind="heloc",
                            ))

            current_date += timedelta(days=1)

        # Sort events by date
        self.events.sort()
        return self.events

    def project_balances(
        self,
        start_date: date,
        end_date: date,
        payment_strategy: dict = None,
        injected_events: dict = None,
    ) -> dict:
        """
        Project account balances from start_date to end_date.
        
        All payment types are now unified through BILL_DUE events.
        Optimization events (savings sweeps, promo payoffs, etc.) can be
        injected via injected_events so they are processed as part of the
        same day-by-day loop.

        Args:
            start_date: Simulation start date
            end_date: Simulation end date
            payment_strategy: Optional custom payment routing
            injected_events: Optional dict of {date: [TimelineEvent, ...]}
                             produced by the PaymentOptimizer

        Returns:
            Dictionary with snapshots, final balances, cash flow, events
        """
        # Build timeline of all events
        self.build_timeline(start_date, end_date, include_interest=True)

        # Index events by date for O(1) lookup
        from collections import defaultdict
        events_by_date = defaultdict(list)
        for e in self.events:
            events_by_date[e.event_date].append(e)

        # Merge injected optimization events into the lookup
        injected_events = injected_events or {}
        for evt_date, evt_list in injected_events.items():
            events_by_date[evt_date].extend(evt_list)

        # Pre-calculate all income pay dates
        income_pay_dates = {}
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            income_pay_dates[income.source_name] = set(pay_dates)

        # Process events chronologically
        snapshots = []
        cash_flow = []

        # A bill's real-world "paid this period" flag only applies to its
        # FIRST occurrence in the window (the current period). Payments made
        # inside the simulation set the flag too, but must not suppress the
        # following period, so later occurrences ignore it.
        first_occurrence_seen: set[int] = set()

        current_date = start_date
        while current_date <= end_date:
            day_events = events_by_date.get(current_date, [])

            for event in sorted(day_events, key=self._event_sort_key):
                if event.event_type == "INCOME":
                    # Distribute income - find the matching income source for this event
                    for income in self.income_sources:
                        if event.description == f"Income: {income.source_name}":
                            if not income.distribution:
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
                                    "account": account_name,
                                    "bank": target_bank.name
                                })
                            else:
                                total_fixed = 0.0
                                remainder_account = None

                                for account_name, value in income.distribution.items():
                                    if value is None or value == "remainder":
                                        remainder_account = account_name
                                    elif isinstance(value, (int, float)) and value > 0:
                                        if 0 < value <= 1 and hasattr(income.distribution, 'get_distribution_type'):
                                            from models.types import DistributionEnumType
                                            dist_type = income.distribution.get_distribution_type(account_name)
                                            if dist_type == DistributionEnumType.PERCENTAGE:
                                                deposit_amount = income.amount * value
                                            else:
                                                deposit_amount = value
                                        else:
                                            deposit_amount = value
                                        target_bank = self._find_bank_with_account(account_name)
                                        if target_bank:
                                            target_bank.accounts[account_name].deposit(
                                                deposit_amount,
                                                description=f"Income: {income.source_name}",
                                                transaction_date=current_date
                                            )
                                            total_fixed += deposit_amount
                                            cash_flow.append({
                                                "date": current_date,
                                                "type": "INCOME",
                                                "description": f"{income.source_name}",
                                                "amount": deposit_amount,
                                                "account": account_name,
                                                "bank": target_bank.name
                                            })

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
                                                "account": remainder_account,
                                                "bank": target_bank.name
                                            })
                            break

                elif event.event_type == "BILL_DUE":
                    # Find matching bill and pay it — handles all bill types uniformly
                    for bill in self.bills:
                        next_due = bill.get_next_due_date(current_date - timedelta(days=1))
                        if next_due == current_date and event.description == f"Bill: {bill.bill_name}":
                            # Skip if already paid this period (first occurrence only)
                            is_first = id(bill) not in first_occurrence_seen
                            first_occurrence_seen.add(id(bill))
                            if is_first and bill.is_paid_this_period:
                                bill.is_paid_this_period = False
                                cash_flow.append({
                                    "date": current_date,
                                    "type": "BILL_ALREADY_PAID",
                                    "description": f"{bill.bill_name} (already paid)",
                                    "amount": 0,
                                    "account": bill.preferred_source_account or "",
                                    "bank": bill.preferred_source_bank or ""
                                })
                                break

                            # Get the actual current amount as of the simulated date
                            # (dynamic for linked bills: promo payoff math, HELOC phase)
                            bill_amount = bill.amount_on(current_date)

                            # Skip zero-amount bills (e.g. zero-balance credit card)
                            if bill_amount <= 0:
                                break

                            # For linked bills, cap payment at what is actually owed
                            if isinstance(bill, AccountLinkedBill):
                                bill_amount = min(bill_amount, self._linked_bill_payoff_amount(bill))
                                if bill_amount <= 0:
                                    break

                            # Choose account to pay from
                            source_bank, source_account = self._choose_payment_account(
                                bill, payment_strategy, bill_amount, current_date
                            )

                            if not (source_bank and source_account):
                                # No account can cover this bill — record it as deferred
                                cash_flow.append({
                                    "date": current_date,
                                    "type": self._deferred_type(bill),
                                    "description": f"{bill.bill_name} (insufficient funds)",
                                    "amount": -bill_amount,
                                    "account": None,
                                    "bank": None,
                                    "error": "No account has sufficient funds",
                                    **self._linked_bill_names(bill),
                                })
                                break

                            try:
                                # For linked bills, the mark_paid will call the account's
                                # make_payment internally. We just need to withdraw from source.
                                if isinstance(bill, AccountLinkedBill):
                                    # Withdraw from source checking account
                                    source_bank.accounts[source_account].withdraw(
                                        bill_amount,
                                        description=f"Payment: {bill.bill_name}",
                                        transaction_date=current_date
                                    )
                                    # mark_paid calls linked_account.make_payment()
                                    bill.mark_paid(source_bank.name, source_account, bill_amount, current_date)

                                    # Determine cash flow type based on account type
                                    cf_type = "BILL_PAYMENT"
                                    if bill.linked_account_type == 'credit':
                                        cf_type = "CREDIT_PAYMENT"
                                    elif bill.linked_account_type == 'mortgage':
                                        cf_type = "MORTGAGE_PAYMENT"
                                    elif bill.linked_account_type == 'heloc':
                                        cf_type = "HELOC_PAYMENT"

                                    cf_entry = {
                                        "date": current_date,
                                        "type": cf_type,
                                        "description": bill.bill_name,
                                        "amount": -bill_amount,
                                        "account": source_account,
                                        "bank": source_bank.name,
                                        **self._linked_bill_names(bill),
                                    }

                                    # Add type-specific info
                                    if bill.linked_account_type == 'credit':
                                        cf_entry["minimum_due"] = bill_amount
                                        cf_entry["credit_balance_after"] = bill.linked_account.balance
                                    elif bill.linked_account_type == 'mortgage':
                                        # Use the actual breakdown of this payment
                                        mortgage = bill.linked_account
                                        record = mortgage.payment_history[-1] if mortgage.payment_history else {}
                                        cf_entry["principal"] = record.get("principal", 0.0)
                                        cf_entry["interest"] = record.get("interest", 0.0)
                                        cf_entry["escrow"] = record.get("escrow", 0.0)
                                        cf_entry["principal_after"] = mortgage.current_principal
                                    elif bill.linked_account_type == 'heloc':
                                        cf_entry["heloc_balance_after"] = bill.linked_account.balance
                                        cf_entry["phase"] = bill.linked_account.get_phase_on_date(current_date).value

                                    cash_flow.append(cf_entry)
                                else:
                                    # Regular bill — same as before
                                    source_bank.accounts[source_account].withdraw(
                                        bill_amount,
                                        description=f"Payment: {bill.bill_name}",
                                        transaction_date=current_date
                                    )
                                    bill.mark_paid(source_bank.name, source_account, bill_amount, current_date)
                                    cash_flow.append({
                                        "date": current_date,
                                        "type": "BILL_PAYMENT",
                                        "description": bill.bill_name,
                                        "amount": -bill_amount,
                                        "account": source_account,
                                        "bank": source_bank.name
                                    })
                            except ValueError as e:
                                cash_flow.append({
                                    "date": current_date,
                                    "type": self._deferred_type(bill),
                                    "description": f"{bill.bill_name} (insufficient funds)",
                                    "amount": -bill_amount,
                                    "account": source_account,
                                    "bank": source_bank.name,
                                    "error": str(e),
                                    **self._linked_bill_names(bill),
                                })
                            break

                elif event.event_type == "INTEREST":
                    bank = self._get_bank_by_name(event.bank_name)
                    if bank:
                        interest = 0.0
                        kind = event.account_kind
                        if kind == "heloc" or (kind is None and event.account_name in bank.heloc_accounts
                                               and event.account_name not in bank.accounts
                                               and event.account_name not in bank.credit_accounts):
                            kind = "heloc"
                            interest = bank.heloc_accounts[event.account_name].accrue_interest(current_date)
                        elif kind != "credit" and event.account_name in bank.accounts:
                            kind = "bank"
                            interest = bank.accounts[event.account_name].accrue_interest(current_date)
                        elif event.account_name in bank.credit_accounts:
                            kind = "credit"
                            interest = bank.credit_accounts[event.account_name].accrue_interest(current_date)

                        if interest > 0:
                            cash_flow.append({
                                "date": current_date,
                                "type": "INTEREST",
                                "description": f"Interest: {event.account_name}",
                                "amount": interest,
                                "account": event.account_name,
                                "bank": event.bank_name,
                                # 'bank' = earned; 'credit'/'heloc' = charged
                                "account_kind": kind,
                            })

                elif event.event_type == "BILL_GROUP_PAYMENT":
                    # Find the matching GroupLinkedBill from self.bills
                    for bill in self.bills:
                        if not isinstance(bill, GroupLinkedBill):
                            continue
                        next_due = bill.get_next_due_date(current_date - timedelta(days=1))
                        if next_due == current_date and event.description == f"Bill: {bill.bill_name}":
                            group = bill.linked_group
                            # Real-world paid flag applies to the first occurrence only
                            is_first = id(bill) not in first_occurrence_seen
                            first_occurrence_seen.add(id(bill))
                            if is_first and bill.is_paid_this_period:
                                bill.is_paid_this_period = False
                                cash_flow.append({
                                    "date": current_date,
                                    "type": "BILL_GROUP_ALREADY_PAID",
                                    "description": f"{group.group_name} (already paid)",
                                    "amount": 0,
                                    "account": bill.preferred_source_account or "",
                                    "bank": bill.preferred_source_bank or ""
                                })
                                break

                            bill_amount = bill.amount_on(current_date)
                            # Never withdraw more than the members still owe
                            bill_amount = min(bill_amount, round(group.get_total_balance(self.banks), 2))
                            if bill_amount <= 0:
                                break

                            source_bank = None
                            source_account_name = bill.preferred_source_account
                            if bill.preferred_source_bank:
                                source_bank = self._get_bank_by_name(bill.preferred_source_bank)

                            if not source_bank or not source_account_name:
                                source_bank, source_account_name = self._get_best_account_for_payment(bill_amount)

                            if source_bank and source_account_name and source_account_name in source_bank.accounts:
                                try:
                                    source_account_obj = source_bank.accounts[source_account_name]
                                    source_account_obj.withdraw(
                                        bill_amount,
                                        description=f"Group Payment: {group.group_name}",
                                        transaction_date=current_date
                                    )
                                    sub_payments = bill.mark_paid(
                                        source_bank.name, source_account_name,
                                        bill_amount, current_date,
                                        banks=self.banks
                                    )
                                    # Only what was actually applied to members leaves
                                    # checking; refund any (rounding) difference.
                                    applied = round(sum(sp["amount"] for sp in sub_payments), 2)
                                    unapplied = round(bill_amount - applied, 2)
                                    if unapplied > 0:
                                        source_account_obj.deposit(
                                            unapplied,
                                            description=f"Group Payment refund (unapplied): {group.group_name}",
                                            transaction_date=current_date
                                        )
                                        bill_amount = applied

                                    cash_flow.append({
                                        "date": current_date,
                                        "type": "BILL_GROUP_PAYMENT",
                                        "description": group.group_name,
                                        "amount": -bill_amount,
                                        "account": source_account_name,
                                        "bank": source_bank.name,
                                        "sub_payments": sub_payments
                                    })
                                except ValueError as e:
                                    cash_flow.append({
                                        "date": current_date,
                                        "type": "BILL_GROUP_DEFERRED",
                                        "description": f"{group.group_name} (insufficient funds)",
                                        "amount": -bill_amount,
                                        "account": source_account_name,
                                        "bank": source_bank.name if source_bank else "(none)",
                                        "error": str(e)
                                    })
                            else:
                                cash_flow.append({
                                    "date": current_date,
                                    "type": "BILL_GROUP_DEFERRED",
                                    "description": f"{group.group_name} (insufficient funds)",
                                    "amount": -bill_amount,
                                    "account": source_account_name,
                                    "bank": source_bank.name if source_bank else "(none)",
                                    "error": "No account has sufficient funds",
                                })
                            break

                # ── Optimization event processing ────────────────────────────
                elif event.event_type in ("SAVINGS_SWEEP", "SAVINGS_RECALL",
                                          "HELOC_PARK", "HELOC_RECALL",
                                          "EXTRA_CREDIT_PAYMENT", "PROMO_PAYOFF"):
                    self._process_optimization_event(event, current_date, cash_flow)

            # Create snapshot for this date
            snapshot = {"date": current_date, "balances": {}, "credit_balances": {}, "mortgage_balances": {}, "heloc_balances": {}}
            for bank in self.banks:
                for account in bank.get_all_accounts():
                    key = f"{bank.name}:{account.account_name}"
                    snapshot["balances"][key] = account.balance
                for credit in bank.get_all_credit_accounts():
                    key = f"{bank.name}:{credit.account_name}"
                    snapshot["credit_balances"][key] = credit.balance
                for mortgage in bank.get_all_mortgage_accounts():
                    key = f"{bank.name}:{mortgage.account_name}"
                    snapshot["mortgage_balances"][key] = mortgage.current_principal
                for heloc in bank.get_all_heloc_accounts():
                    key = f"{bank.name}:{heloc.account_name}"
                    snapshot["heloc_balances"][key] = heloc.balance

            snapshots.append(snapshot)
            current_date += timedelta(days=1)

        # Compile final balances
        final_balances = {}
        credit_final_balances = {}
        mortgage_final_balances = {}
        heloc_final_balances = {}
        for bank in self.banks:
            for account in bank.get_all_accounts():
                key = f"{bank.name}:{account.account_name}"
                final_balances[key] = account.balance
            for credit in bank.get_all_credit_accounts():
                key = f"{bank.name}:{credit.account_name}"
                credit_final_balances[key] = credit.balance
            for mortgage in bank.get_all_mortgage_accounts():
                key = f"{bank.name}:{mortgage.account_name}"
                mortgage_final_balances[key] = mortgage.current_principal
            for heloc in bank.get_all_heloc_accounts():
                key = f"{bank.name}:{heloc.account_name}"
                heloc_final_balances[key] = heloc.balance

        # Promo balances still unpaid at the end of the window, with the
        # deferred interest they would trigger if still unpaid at expiry
        # (same formula as CreditCardAccount.process_expired_promos).
        promo_final = {}
        for bank in self.banks:
            for credit in bank.get_all_credit_accounts():
                monthly_rate = credit.interest_rate / 12 / 100
                for promo in credit.active_promos:
                    remaining = credit.promo_balance.get(promo.promo_name, 0.0)
                    if remaining > 0.005 and not promo.interest_charged:
                        promo_final[f"{bank.name}:{credit.account_name}:{promo.promo_name}"] = {
                            "remaining": remaining,
                            "end_date": promo.end_date,
                            "deferred_interest": remaining * ((1 + monthly_rate) ** promo.months_interest_free - 1),
                        }

        # Build processed events list — replace pre-built event amounts with
        # actual values from the simulation.
        credit_payments_actual = {}
        interest_actual = {}
        for cf in cash_flow:
            if cf["type"] == "CREDIT_PAYMENT":
                key = (cf["date"], f"Bill: {cf['description']}")
                credit_payments_actual[key] = abs(cf["amount"])
            elif cf["type"] == "INTEREST":
                acct = cf.get("account", "")
                key = (cf["date"], acct)
                interest_actual[key] = cf["amount"]

        processed_events = []
        for event in self.events:
            if event.event_type == "BILL_DUE":
                # Check if this was a credit payment that we have actual data for
                cf_key = (event.event_date, event.description)
                actual_amount = credit_payments_actual.get(cf_key)
                if actual_amount is not None:
                    if actual_amount > 0:
                        processed_events.append(TimelineEvent(
                            event_date=event.event_date,
                            event_type=event.event_type,
                            amount=actual_amount,
                            description=event.description,
                            account_name=event.account_name,
                            bank_name=event.bank_name
                        ))
                    # else: balance was zero — omit the event
                else:
                    processed_events.append(event)
            elif event.event_type == "INTEREST":
                int_key = (event.event_date, event.account_name)
                actual_interest = interest_actual.get(int_key)
                if actual_interest is not None and actual_interest > 0:
                    processed_events.append(TimelineEvent(
                        event_date=event.event_date,
                        event_type=event.event_type,
                        amount=actual_interest,
                        description=event.description,
                        account_name=event.account_name,
                        bank_name=event.bank_name
                    ))
            else:
                processed_events.append(event)

        # Append injected optimization events to the processed events list
        for evt_date, evt_list in injected_events.items():
            for evt in evt_list:
                # Only include events that actually executed (check cash_flow)
                processed_events.append(evt)
        # Re-sort by date
        processed_events.sort(key=lambda e: (e.event_date, self._event_processing_order(e.event_type)))

        return {
            "start_date": start_date,
            "end_date": end_date,
            "snapshots": snapshots,
            "final_balances": final_balances,
            "credit_final_balances": credit_final_balances,
            "mortgage_final_balances": mortgage_final_balances,
            "heloc_final_balances": heloc_final_balances,
            "promo_final": promo_final,
            "cash_flow": cash_flow,
            "events": processed_events
        }

    def _get_bank_by_name(self, bank_name: str) -> Bank | None:
        """Get a bank by name."""
        for bank in self.banks:
            if bank.name == bank_name:
                return bank
        return None if bank_name else self.banks[0]

    @staticmethod
    def _event_processing_order(event_type: str) -> int:
        """
        Define the order in which events should be processed within a single day.

        Income must come first so funds are available for bills.
        Recalls (savings / HELOC -> checking) come next so recalled money is
        available for bills due the same day.
        Bills come next (includes all payment types now).
        Bill groups come after individual bills.
        Other optimization events come after all bills are paid but before interest.
        Interest comes last because it depends on end-of-day balances
        (HELOC interest is the exception, see _event_sort_key).
        """
        order = {
            "INCOME": 0,
            # Recalls fund the same day's bills
            "SAVINGS_RECALL": 1,
            "HELOC_RECALL": 2,
            "BILL_DUE": 4,
            "BILL_GROUP_PAYMENT": 5,
            # Optimization events — after bills, before interest
            "PROMO_PAYOFF": 6,
            "EXTRA_CREDIT_PAYMENT": 7,
            "HELOC_PARK": 8,
            "SAVINGS_SWEEP": 9,
            "INTEREST": 10,
        }
        return order.get(event_type, 10)

    @classmethod
    def _event_sort_key(cls, event: TimelineEvent) -> int:
        """
        Same-day processing order for an event. HELOC interest accrues on the
        payment due day *before* bills, so that day's payment covers it
        (interest-only payments then keep a draw-period balance flat).
        """
        if event.event_type == "INTEREST" and event.account_kind == "heloc":
            return 3
        return cls._event_processing_order(event.event_type)

    @staticmethod
    def _deferred_type(bill: Bill) -> str:
        """Cash-flow type for a bill that could not be paid."""
        if isinstance(bill, AccountLinkedBill):
            if bill.linked_account_type == 'credit':
                return "CREDIT_PAYMENT_DEFERRED"
            if bill.linked_account_type == 'mortgage':
                return "MORTGAGE_DEFERRED"
            if bill.linked_account_type == 'heloc':
                return "HELOC_PAYMENT_DEFERRED"
        return "BILL_DEFERRED"

    @staticmethod
    def _linked_bill_names(bill: Bill) -> dict:
        """Extra cash-flow keys identifying the account behind a linked bill."""
        if isinstance(bill, AccountLinkedBill):
            name = bill.linked_account.account_name
            extra = {"linked_account": name, "linked_bank": bill.linked_bank_name}
            if bill.linked_account_type == 'mortgage':
                extra["mortgage_name"] = name
            elif bill.linked_account_type == 'credit':
                extra["credit_name"] = name
            elif bill.linked_account_type == 'heloc':
                extra["heloc_name"] = name
            return extra
        return {}

    @staticmethod
    def _linked_bill_payoff_amount(bill: AccountLinkedBill) -> float:
        """
        Most that can be paid on a linked bill this period. For a mortgage
        this is principal + this month's interest + escrow (a near-payoff
        payment still has to cover interest and escrow); for credit/HELOC it
        is the balance owed.
        """
        if bill.linked_account_type == 'mortgage':
            mortgage = bill.linked_account
            if mortgage.current_principal <= 0:
                return 0.0
            return round(
                mortgage.current_principal
                + mortgage.current_monthly_interest
                + mortgage.escrow.total_monthly,
                2,
            )
        return bill.linked_account_balance

    def _find_bank_with_account(self, account_name: str) -> Bank | None:
        """Find which bank contains a specific account."""
        for bank in self.banks:
            if account_name in bank.accounts:
                return bank
        return None

    def _choose_payment_account(
        self,
        bill: Bill,
        payment_strategy: dict = None,
        amount: float = None,
        current_date: date = None,
    ) -> tuple[Bank, str] | tuple[None, None]:
        """
        Choose which account to pay a bill from.
        Priority: explicit assignment > preferred > best available.

        Strategy entries are looked up by "{bill_name}_{due_date ISO}" (the
        per-occurrence keys produced by PaymentOptimizer) and then by plain
        bill_name (one routing for every occurrence).
        """
        if amount is None:
            amount = bill.amount_on(current_date)

        if payment_strategy:
            strat = None
            if current_date is not None:
                strat = payment_strategy.get(f"{bill.bill_name}_{current_date.isoformat()}")
            if strat is None:
                strat = payment_strategy.get(bill.bill_name)
            if isinstance(strat, dict):
                bank = self._get_bank_by_name(strat.get("bank"))
                account = strat.get("account")
                if bank and account and account in bank.accounts:
                    if bank.accounts[account].balance >= amount:
                        return bank, account
                    # The planned account can't cover it on the day (plans are
                    # estimates) — fall back to preferred / best available
                    # rather than deferring a payable bill.

        # Try preferred account
        if bill.preferred_source_bank and bill.preferred_source_account:
            bank = self._get_bank_by_name(bill.preferred_source_bank)
            if bank and bill.preferred_source_account in bank.accounts:
                if bank.accounts[bill.preferred_source_account].balance >= amount:
                    return bank, bill.preferred_source_account

        # Choose best available account with sufficient funds
        return self._get_best_account_for_payment(amount)

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

    def _process_optimization_event(
        self,
        event: TimelineEvent,
        current_date: date,
        cash_flow: list[dict],
    ):
        """
        Process an optimizer-injected event (savings sweep, promo payoff, etc.).
        Mutates bank/account balances in the same way normal events do.
        """
        from_bank = self._get_bank_by_name(event.from_bank)
        to_bank = self._get_bank_by_name(event.to_bank)
        amount = event.amount

        if amount <= 0:
            return

        if event.event_type == "SAVINGS_SWEEP":
            # Transfer from checking to savings
            if from_bank and event.from_account in from_bank.accounts:
                if to_bank and event.to_account in to_bank.accounts:
                    src = from_bank.accounts[event.from_account]
                    dst = to_bank.accounts[event.to_account]
                    actual = min(amount, src.balance)
                    if actual > 0:
                        src.withdraw(actual, description=event.description, transaction_date=current_date)
                        dst.deposit(actual, description=event.description, transaction_date=current_date)
                        cash_flow.append({
                            "date": current_date, "type": "SAVINGS_SWEEP",
                            "description": event.description, "amount": actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                        })

        elif event.event_type == "SAVINGS_RECALL":
            # Transfer from savings back to checking
            if from_bank and event.from_account in from_bank.accounts:
                if to_bank and event.to_account in to_bank.accounts:
                    src = from_bank.accounts[event.from_account]
                    dst = to_bank.accounts[event.to_account]
                    actual = min(amount, src.balance)
                    if actual > 0:
                        src.withdraw(actual, description=event.description, transaction_date=current_date)
                        dst.deposit(actual, description=event.description, transaction_date=current_date)
                        cash_flow.append({
                            "date": current_date, "type": "SAVINGS_RECALL",
                            "description": event.description, "amount": actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                        })

        elif event.event_type == "HELOC_PARK":
            # Park excess cash into HELOC (make_payment to reduce balance → less interest)
            if from_bank and event.from_account in from_bank.accounts:
                if to_bank and event.to_account in to_bank.heloc_accounts:
                    src = from_bank.accounts[event.from_account]
                    heloc = to_bank.heloc_accounts[event.to_account]
                    actual = min(amount, src.balance, heloc.balance)
                    if actual > 0:
                        src.withdraw(actual, description=event.description, transaction_date=current_date)
                        heloc.make_payment(actual, description=event.description, transaction_date=current_date)
                        cash_flow.append({
                            "date": current_date, "type": "HELOC_PARK",
                            "description": event.description, "amount": actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                            "heloc_balance_after": heloc.balance,
                        })

        elif event.event_type == "HELOC_RECALL":
            # Draw cash back from HELOC (make_draw increases balance)
            if from_bank and event.from_account in from_bank.heloc_accounts:
                if to_bank and event.to_account in to_bank.accounts:
                    heloc = from_bank.heloc_accounts[event.from_account]
                    dst = to_bank.accounts[event.to_account]
                    actual = min(amount, heloc.get_available_credit(current_date))
                    if actual > 0:
                        heloc.make_draw(actual, description=event.description, transaction_date=current_date)
                        dst.deposit(actual, description=event.description, transaction_date=current_date)
                        cash_flow.append({
                            "date": current_date, "type": "HELOC_RECALL",
                            "description": event.description, "amount": actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                            "heloc_balance_after": heloc.balance,
                        })

        elif event.event_type == "EXTRA_CREDIT_PAYMENT":
            # Extra payment toward a credit card from checking
            if from_bank and event.from_account in from_bank.accounts:
                if to_bank and event.to_account in to_bank.credit_accounts:
                    src = from_bank.accounts[event.from_account]
                    credit = to_bank.credit_accounts[event.to_account]
                    actual = min(amount, src.balance, credit.balance)
                    if actual > 0:
                        src.withdraw(actual, description=event.description, transaction_date=current_date)
                        credit.make_payment(actual, description=event.description, transaction_date=current_date)
                        cash_flow.append({
                            "date": current_date, "type": "EXTRA_CREDIT_PAYMENT",
                            "description": event.description, "amount": -actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                            "credit_balance_after": credit.balance,
                        })

        elif event.event_type == "PROMO_PAYOFF":
            # Extra payment toward a promo balance on a credit card
            if from_bank and event.from_account in from_bank.accounts:
                if to_bank and event.to_account in to_bank.credit_accounts:
                    src = from_bank.accounts[event.from_account]
                    credit = to_bank.credit_accounts[event.to_account]
                    actual = min(amount, src.balance, credit.balance)
                    if actual > 0:
                        promo_name = self._resolve_promo_name(event, credit)
                        src.withdraw(actual, description=event.description, transaction_date=current_date)
                        # Apply to the promotional balance first (not regular balance)
                        credit.make_payment(actual, description=event.description,
                                            transaction_date=current_date, promo_name=promo_name)
                        cash_flow.append({
                            "date": current_date, "type": "PROMO_PAYOFF",
                            "promo_name": promo_name,
                            "description": event.description, "amount": -actual,
                            "from_bank": event.from_bank, "from_account": event.from_account,
                            "to_bank": event.to_bank, "to_account": event.to_account,
                            "credit_balance_after": credit.balance,
                        })

    @staticmethod
    def _resolve_promo_name(event: TimelineEvent, credit) -> str | None:
        """
        Determine which promo a PROMO_PAYOFF event targets: the event's
        promo_name, else a promo named in the description
        ("Promo payoff: <name> on <card>"), else the soonest-expiring promo
        that still has a balance.
        """
        balances = getattr(credit, 'promo_balance', {}) or {}
        if event.promo_name and event.promo_name in balances:
            return event.promo_name
        description = event.description or ""
        if ":" in description:
            tail = description.split(":", 1)[1].strip()
            for name in sorted(balances, key=len, reverse=True):
                if tail == name or tail.startswith(f"{name} on "):
                    return name
        open_promos = [
            p for p in getattr(credit, 'active_promos', [])
            if balances.get(p.promo_name, 0.0) > 0 and not p.interest_charged
        ]
        if open_promos:
            return min(open_promos, key=lambda p: p.end_date).promo_name
        return None
