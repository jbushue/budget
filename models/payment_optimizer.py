from datetime import date, timedelta
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator


@dataclass
class PromoPayoffPriority:
    """Represents a promotional offer that needs to be paid off before expiration."""
    credit_account_name: str
    bank_name: str
    promo_name: str
    balance_owed: float
    end_date: date
    days_remaining: int
    required_monthly_payment: float  # Amount needed per month to pay off in time
    interest_rate_after: float  # APR that will apply if not paid off
    priority_score: float  # Higher = more urgent (based on time and amount)

    def __lt__(self, other):
        # Sort by priority score descending (higher priority first)
        return self.priority_score > other.priority_score


@dataclass
class SavingsTransfer:
    """Represents a recommended transfer between checking and savings to maximize interest."""
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount: float
    transfer_date: date
    reason: str  # 'maximize_interest' or 'fund_upcoming_bills'
    estimated_interest_gain: float = 0.0  # Estimated additional interest earned

    def __repr__(self):
        return f"Transfer ${self.amount:,.2f} from {self.from_account} to {self.to_account} on {self.transfer_date}"


@dataclass
class PaymentPlan:
    """Represents an optimized payment plan for bills and mortgages."""
    strategy: dict  # {bill_name: {bank: name, account: name, date: date}}
    total_interest_paid: float
    total_fees: float
    final_discretionary: float  # Cash available after all obligations
    violations: list[str]  # Any constraint violations
    extra_credit_payments: list[dict] = field(default_factory=list)  # Extra payments to credit accounts
    target_credit_payoff: Optional[str] = None  # Target credit account for payoff goal
    promo_payoff_schedule: list[dict] = field(default_factory=list)  # Scheduled promo payoff payments
    promo_priorities: list[PromoPayoffPriority] = field(default_factory=list)  # Promos needing payoff
    mortgage_payments: list[dict] = field(default_factory=list)  # Scheduled mortgage payments
    total_mortgage_principal: float = 0.0  # Total principal paid in period
    total_mortgage_interest: float = 0.0  # Total mortgage interest paid in period
    transfer_recommendations: list[SavingsTransfer] = field(default_factory=list)  # Recommended transfers
    estimated_interest_earned: float = 0.0  # Estimated interest earned from savings optimization

    def __repr__(self):
        return (
            f"PaymentPlan(interest=${self.total_interest_paid:.2f}, "
            f"discretionary=${self.final_discretionary:.2f}, "
            f"violations={len(self.violations)}, "
            f"extra_credit_payments={len(self.extra_credit_payments)}, "
            f"promo_payoffs={len(self.promo_payoff_schedule)}, "
            f"mortgage_payments={len(self.mortgage_payments)}, "
            f"transfers={len(self.transfer_recommendations)})"
        )


@dataclass
class CashFlowEvent:
    """Represents a cash flow event for planning."""
    event_date: date
    event_type: str  # 'INCOME', 'BILL', 'CREDIT_PAYMENT'
    amount: float
    description: str
    source_name: Optional[str] = None  # Income source or bill name
    
    def __lt__(self, other):
        return self.event_date < other.event_date


class PaymentOptimizer:
    """
    Optimizes which accounts to pay bills from to maximize discretionary funds
    while ensuring all bills are paid on time.

    Strategy:
    - Pay bills from accounts with lowest opportunity cost (checking before savings)
    - Time payments close to due date to maximize float
    - For credit payoff goal, maximize extra payments to target credit account
    """

    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[Bill]):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills

    def optimize_payment_schedule(
        self,
        start_date: date,
        end_date: date,
        optimization_goal: str = "maximize_discretionary",
        target_credit_account: str = None
    ) -> PaymentPlan:
        """
        Optimize payment schedule between start and end dates.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            optimization_goal:
                - 'maximize_discretionary': Maximize cash on hand
                - 'minimize_interest': Minimize interest charges
                - 'payoff_credit_account': Maximize payments to target credit account
            target_credit_account: Required when optimization_goal is 'payoff_credit_account'

        Returns:
            PaymentPlan with optimized strategy
        """
        if optimization_goal == "payoff_credit_account" and not target_credit_account:
            raise ValueError("target_credit_account is required for 'payoff_credit_account' goal")

        # Build complete cash flow timeline
        cash_flow_events = self._build_cash_flow_timeline(start_date, end_date)
        
        # Get all income dates using the new efficient method
        income_dates = self._find_income_dates(start_date, end_date)
        
        # Build bill schedule with due dates
        bill_schedule = self._build_bill_schedule(start_date, end_date)
        
        # Build mortgage payment schedule
        mortgage_schedule = self._build_mortgage_schedule(start_date, end_date)

        # PRIORITY: Find all promotional offers that need to be paid off
        promo_priorities = self._find_promo_payoff_priorities(start_date, end_date)
        
        # Calculate promo payoff schedule (these take priority over discretionary spending)
        promo_payoff_schedule = self._calculate_promo_payoff_schedule(
            start_date,
            end_date,
            income_dates,
            bill_schedule,
            promo_priorities
        )

        # Create optimized payment strategy (includes bills and mortgages)
        strategy = self._create_payment_strategy(
            start_date,
            end_date,
            income_dates,
            bill_schedule,
            optimization_goal,
            mortgage_schedule
        )

        # Calculate extra credit payments if goal is payoff (after promo payments)
        extra_credit_payments = []
        if optimization_goal == "payoff_credit_account":
            extra_credit_payments = self._calculate_extra_credit_payments(
                start_date,
                end_date,
                income_dates,
                bill_schedule,
                target_credit_account,
                strategy,
                promo_payoff_schedule  # Pass promo schedule to avoid double-counting
            )

        # Simulate with optimized strategy to calculate results
        simulator = TimelineSimulator(
            deepcopy(self.banks),
            deepcopy(self.income_sources),
            deepcopy(self.bills)
        )

        result = simulator.project_balances(start_date, end_date, strategy)

        # Calculate total interest from simulation (includes mortgage interest)
        total_interest = sum(
            cf['amount'] for cf in result['cash_flow']
            if cf.get('type') == 'INTEREST' and cf['amount'] > 0
        )
        
        # Extract mortgage payment info from simulation
        mortgage_payments = [
            cf for cf in result['cash_flow']
            if cf.get('type') == 'MORTGAGE_PAYMENT'
        ]
        total_mortgage_principal = sum(
            cf.get('principal', 0) for cf in mortgage_payments
        )
        total_mortgage_interest = sum(
            cf.get('interest', 0) for cf in mortgage_payments
        )

        # Calculate discretionary funds (total after all obligations)
        final_discretionary = sum(
            balance for balance in result["final_balances"].values()
        )

        # Adjust discretionary for planned promo payoff payments
        for payment in promo_payoff_schedule:
            final_discretionary -= payment['amount']

        # Adjust discretionary for planned extra credit payments
        for payment in extra_credit_payments:
            final_discretionary -= payment['amount']

        violations = self._check_constraints(result, bill_schedule, mortgage_schedule)
        
        # Add warnings for promos that can't be fully paid off
        for promo in promo_priorities:
            total_scheduled = sum(
                p['amount'] for p in promo_payoff_schedule
                if p['promo_name'] == promo.promo_name
            )
            if total_scheduled < promo.balance_owed:
                shortfall = promo.balance_owed - total_scheduled
                violations.append(
                    f"WARNING: Promo '{promo.promo_name}' on {promo.credit_account_name} "
                    f"may not be fully paid off before {promo.end_date}. "
                    f"Shortfall: ${shortfall:.2f}. Deferred interest may apply."
                )

        # Calculate savings optimization transfers to maximize interest earned
        transfer_recommendations, estimated_interest = self._calculate_savings_transfers(
            start_date,
            end_date,
            income_dates,
            bill_schedule,
            mortgage_schedule,
            promo_payoff_schedule,
            extra_credit_payments
        )

        return PaymentPlan(
            strategy=strategy,
            total_interest_paid=total_interest,
            total_fees=0.0,
            final_discretionary=final_discretionary,
            violations=violations,
            extra_credit_payments=extra_credit_payments,
            target_credit_payoff=target_credit_account,
            promo_payoff_schedule=promo_payoff_schedule,
            promo_priorities=promo_priorities,
            mortgage_payments=mortgage_payments,
            total_mortgage_principal=total_mortgage_principal,
            total_mortgage_interest=total_mortgage_interest,
            transfer_recommendations=transfer_recommendations,
            estimated_interest_earned=estimated_interest
        )

    def _find_promo_payoff_priorities(self, start_date: date, end_date: date) -> list[PromoPayoffPriority]:
        """
        Find all promotional offers that need to be paid off before expiration.
        
        Returns a prioritized list of promos, sorted by urgency (expiring soonest first,
        then by amount owed).
        """
        promo_priorities = []
        today = start_date
        
        for bank in self.banks:
            for credit_name, credit_account in bank.credit_accounts.items():
                for promo in credit_account.active_promos:
                    # Skip inactive or already expired promos
                    if not promo.is_active:
                        continue
                    
                    # Check if promo expires within our planning window
                    if promo.end_date > end_date:
                        # Promo doesn't expire in this window, but we should still
                        # track it if it has a balance
                        pass
                    
                    # Get the balance on this promo
                    promo_balance = credit_account.promo_balance.get(promo.promo_name, 0.0)
                    
                    if promo_balance <= 0:
                        continue  # No balance to pay off
                    
                    # Calculate days remaining until promo expires
                    days_remaining = (promo.end_date - today).days
                    
                    if days_remaining <= 0:
                        # Already expired - this is urgent!
                        days_remaining = 1
                    
                    # Calculate required monthly payment to pay off in time
                    months_remaining = max(days_remaining / 30, 0.5)  # At least half a month
                    required_monthly = promo_balance / months_remaining
                    
                    # Calculate priority score
                    # Higher score = more urgent
                    # Factors: less time remaining, higher balance, higher interest rate after
                    time_urgency = 1000 / max(days_remaining, 1)  # More urgent as deadline approaches
                    balance_factor = promo_balance / 1000  # Scale by thousands
                    interest_factor = credit_account.interest_rate / 10  # APR impact
                    
                    priority_score = time_urgency * 2 + balance_factor + interest_factor
                    
                    promo_priorities.append(PromoPayoffPriority(
                        credit_account_name=credit_name,
                        bank_name=bank.name,
                        promo_name=promo.promo_name,
                        balance_owed=promo_balance,
                        end_date=promo.end_date,
                        days_remaining=days_remaining,
                        required_monthly_payment=required_monthly,
                        interest_rate_after=credit_account.interest_rate,
                        priority_score=priority_score
                    ))
        
        # Sort by priority (highest first, which means most urgent)
        return sorted(promo_priorities)

    def _calculate_promo_payoff_schedule(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        promo_priorities: list[PromoPayoffPriority]
    ) -> list[dict]:
        """
        Calculate a schedule of payments to pay off promotional balances before expiration.
        
        These payments take priority over other discretionary spending because failing
        to pay off promos before expiration results in deferred interest charges.
        """
        promo_payments = []
        
        if not promo_priorities:
            return []
        
        # Calculate available funds after bills for each income period
        # Start with current bank balances
        running_balance = sum(
            account.balance
            for bank in self.banks
            for account in bank.accounts.values()
        )
        
        # Safety buffer - keep some money for emergencies
        safety_buffer = 300.0
        
        # Track remaining balance for each promo
        remaining_promo_balances = {
            f"{p.bank_name}:{p.credit_account_name}:{p.promo_name}": p.balance_owed
            for p in promo_priorities
        }
        
        # Process each income period
        for i, income_date in enumerate(income_dates):
            # Get income amount for this date
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )
            
            running_balance += income_amount
            
            # Find next income date or end of period
            next_income = income_dates[i + 1] if i + 1 < len(income_dates) else end_date + timedelta(days=1)
            
            # Subtract bills due between this income and next
            bills_in_period = sum(
                b['amount'] for b in bill_schedule
                if income_date <= b['due_date'] < next_income
            )
            
            running_balance -= bills_in_period
            
            # Calculate available funds for promo payments
            available_for_promos = max(0, running_balance - safety_buffer)
            
            if available_for_promos <= 0:
                continue
            
            # Allocate funds to promos in priority order
            for promo in promo_priorities:
                promo_key = f"{promo.bank_name}:{promo.credit_account_name}:{promo.promo_name}"
                remaining = remaining_promo_balances.get(promo_key, 0)
                
                if remaining <= 0:
                    continue  # Already paid off
                
                # Check if this promo expires before or during this period
                promo_expires_soon = promo.end_date <= next_income
                
                if promo_expires_soon:
                    # URGENT: Try to pay off entire remaining balance
                    payment_amount = min(remaining, available_for_promos)
                else:
                    # Pay at least the required monthly amount, or what we can afford
                    target_payment = promo.required_monthly_payment
                    payment_amount = min(target_payment, remaining, available_for_promos)
                
                if payment_amount >= 25:  # Minimum payment threshold
                    # Round to nearest $25 for practical payments
                    payment_amount = (payment_amount // 25) * 25
                    
                    # Schedule payment a few days after income arrives
                    payment_date = income_date + timedelta(days=3)
                    
                    # But make sure it's before promo expires
                    if payment_date >= promo.end_date:
                        payment_date = promo.end_date - timedelta(days=1)
                    
                    if payment_date < start_date:
                        payment_date = start_date
                    
                    promo_payments.append({
                        'credit_account': promo.credit_account_name,
                        'bank': promo.bank_name,
                        'promo_name': promo.promo_name,
                        'amount': payment_amount,
                        'date': payment_date,
                        'description': f"Promo payoff: {promo.promo_name} on {promo.credit_account_name}",
                        'is_urgent': promo_expires_soon,
                        'promo_end_date': promo.end_date
                    })
                    
                    # Update tracking
                    remaining_promo_balances[promo_key] -= payment_amount
                    available_for_promos -= payment_amount
                    running_balance -= payment_amount
                
                if available_for_promos <= 0:
                    break  # No more funds available this period
        
        return promo_payments

    def _find_income_dates(self, start_date: date, end_date: date) -> list[date]:
        """Find all income deposit dates in the period using efficient method."""
        all_income_dates = []
        
        for income in self.income_sources:
            # Use the new get_pay_dates_in_range method for efficiency
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                if pay_date not in all_income_dates:
                    all_income_dates.append(pay_date)
        
        return sorted(all_income_dates)

    def _build_bill_schedule(self, start_date: date, end_date: date) -> list[dict]:
        """Build a schedule of all bills due in the period with amounts and due dates."""
        bill_schedule = []
        
        for bill in self.bills:
            current = start_date
            while current <= end_date:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due > end_date:
                    break
                if next_due >= start_date:
                    bill_schedule.append({
                        'bill': bill,
                        'bill_name': bill.bill_name,
                        'amount': bill.amount,
                        'due_date': next_due,
                        'preferred_bank': bill.preferred_source_bank,
                        'preferred_account': bill.preferred_source_account
                    })
                current = next_due + timedelta(days=1)
        
        return sorted(bill_schedule, key=lambda x: x['due_date'])

    def _build_mortgage_schedule(self, start_date: date, end_date: date) -> list[dict]:
        """Build a schedule of all mortgage payments due in the period."""
        mortgage_schedule = []
        
        for bank in self.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                current = start_date
                while current <= end_date:
                    next_due = mortgage.get_next_due_date(current - timedelta(days=1))
                    if next_due > end_date:
                        break
                    if next_due >= start_date:
                        mortgage_schedule.append({
                            'mortgage': mortgage,
                            'mortgage_name': mortgage.account_name,
                            'bank_name': bank.name,
                            'total_payment': mortgage.total_monthly_payment,
                            'principal': mortgage.current_monthly_principal,
                            'interest': mortgage.current_monthly_interest,
                            'escrow': mortgage.escrow.total_monthly,
                            'due_date': next_due,
                            'preferred_bank': mortgage.preferred_source_bank,
                            'preferred_account': mortgage.preferred_source_account
                        })
                    current = next_due + timedelta(days=1)
        
        return sorted(mortgage_schedule, key=lambda x: x['due_date'])

    def _build_cash_flow_timeline(self, start_date: date, end_date: date) -> list[CashFlowEvent]:
        """Build a complete timeline of cash flow events."""
        events = []
        
        # Add income events
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                events.append(CashFlowEvent(
                    event_date=pay_date,
                    event_type='INCOME',
                    amount=income.amount,
                    description=f"Income: {income.source_name}",
                    source_name=income.source_name
                ))
        
        # Add bill events
        for bill in self.bills:
            current = start_date
            while current <= end_date:
                next_due = bill.get_next_due_date(current - timedelta(days=1))
                if next_due > end_date:
                    break
                if next_due >= start_date:
                    events.append(CashFlowEvent(
                        event_date=next_due,
                        event_type='BILL',
                        amount=-bill.amount,
                        description=f"Bill: {bill.bill_name}",
                        source_name=bill.bill_name
                    ))
                current = next_due + timedelta(days=1)
        
        # Add mortgage events
        for bank in self.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                current = start_date
                while current <= end_date:
                    next_due = mortgage.get_next_due_date(current - timedelta(days=1))
                    if next_due > end_date:
                        break
                    if next_due >= start_date:
                        events.append(CashFlowEvent(
                            event_date=next_due,
                            event_type='MORTGAGE',
                            amount=-mortgage.total_monthly_payment,
                            description=f"Mortgage: {mortgage.account_name}",
                            source_name=mortgage.account_name
                        ))
                    current = next_due + timedelta(days=1)
        
        return sorted(events)

    def _create_payment_strategy(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        optimization_goal: str,
        mortgage_schedule: list[dict] = None
    ) -> dict:
        """
        Create an optimized payment strategy for all bills and mortgages.
        
        Strategy rules:
        1. Always pay bills and mortgages on or before due date
        2. Pay from checking accounts before savings (lower opportunity cost)
        3. Consider timing relative to income to avoid overdraft
        4. For minimize_interest: Pay credit card bills as early as possible
        """
        strategy = {}
        mortgage_schedule = mortgage_schedule or []
        
        # Create a working copy of balances to track available funds
        working_balances = {}
        for bank in self.banks:
            for name, account in bank.accounts.items():
                working_balances[f"{bank.name}:{name}"] = account.balance

        # Track income by date to know when funds arrive
        income_by_date = {}
        for income in self.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date - timedelta(days=1), end_date)
            for pay_date in pay_dates:
                if pay_date not in income_by_date:
                    income_by_date[pay_date] = 0.0
                income_by_date[pay_date] += income.amount

        # Process bills in chronological order
        for bill_info in bill_schedule:
            bill = bill_info['bill']
            due_date = bill_info['due_date']
            amount = bill_info['amount']
            
            # Determine optimal payment date
            payment_date = self._determine_payment_date(
                due_date,
                income_dates,
                optimization_goal
            )
            
            # Add any income that arrives before payment date to working balances
            for inc_date, inc_amount in income_by_date.items():
                if inc_date <= payment_date:
                    # Distribute income to first checking account (simplified)
                    for bank in self.banks:
                        for name, account in bank.accounts.items():
                            if account.account_type.value == "checking":
                                key = f"{bank.name}:{name}"
                                if key not in working_balances:
                                    working_balances[key] = 0.0
                                working_balances[key] += inc_amount
                                break
                        break
            
            # Select best account to pay from
            best_bank, best_account = self._select_payment_account_smart(
                bill,
                amount,
                working_balances,
                optimization_goal
            )
            
            if best_bank and best_account:
                # Update working balance
                key = f"{best_bank}:{best_account}"
                if key in working_balances:
                    working_balances[key] -= amount
                
                strategy[bill.bill_name] = {
                    "bank": best_bank,
                    "account": best_account,
                    "date": payment_date,
                    "amount": amount
                }
        
        # Process mortgages in chronological order
        for mortgage_info in mortgage_schedule:
            mortgage = mortgage_info['mortgage']
            due_date = mortgage_info['due_date']
            amount = mortgage_info['total_payment']
            
            # Mortgages are always paid on due date
            payment_date = due_date
            
            # Add any income that arrives before payment date to working balances
            for inc_date, inc_amount in list(income_by_date.items()):
                if inc_date <= payment_date:
                    for bank in self.banks:
                        for name, account in bank.accounts.items():
                            if account.account_type.value == "checking":
                                key = f"{bank.name}:{name}"
                                if key not in working_balances:
                                    working_balances[key] = 0.0
                                working_balances[key] += inc_amount
                                break
                        break
                    # Remove processed income
                    del income_by_date[inc_date]
            
            # Select best account to pay mortgage from
            best_bank, best_account = self._select_mortgage_payment_account(
                mortgage,
                amount,
                working_balances
            )
            
            if best_bank and best_account:
                # Update working balance
                key = f"{best_bank}:{best_account}"
                if key in working_balances:
                    working_balances[key] -= amount
                
                # Add to strategy with mortgage prefix
                strategy[f"Mortgage: {mortgage.account_name}"] = {
                    "bank": best_bank,
                    "account": best_account,
                    "date": payment_date,
                    "amount": amount,
                    "type": "mortgage"
                }
        
        return strategy

    def _select_mortgage_payment_account(
        self,
        mortgage,
        amount: float,
        working_balances: dict
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Select the best account to pay a mortgage from.
        
        Priority:
        1. Preferred account (if has funds)
        2. Checking accounts with sufficient funds
        """
        # Check preferred account first
        if mortgage.preferred_source_bank and mortgage.preferred_source_account:
            key = f"{mortgage.preferred_source_bank}:{mortgage.preferred_source_account}"
            if key in working_balances and working_balances[key] >= amount:
                return mortgage.preferred_source_bank, mortgage.preferred_source_account
        
        # Find any checking account with sufficient funds
        for bank in self.banks:
            for name, account in bank.accounts.items():
                if account.account_type.value == "checking":
                    key = f"{bank.name}:{name}"
                    balance = working_balances.get(key, account.balance)
                    if balance >= amount:
                        return bank.name, name
        
        # Last resort: any account with funds
        for bank in self.banks:
            for name, account in bank.accounts.items():
                key = f"{bank.name}:{name}"
                balance = working_balances.get(key, account.balance)
                if balance >= amount:
                    return bank.name, name
        
        return None, None

    def _determine_payment_date(
        self,
        due_date: date,
        income_dates: list[date],
        optimization_goal: str
    ) -> date:
        """
        Determine the optimal payment date for a bill.
        
        - For maximize_discretionary: Pay on due date to maximize float
        - For minimize_interest: Pay as early as possible after income
        - For payoff_credit_account: Pay on due date to free up cash for credit
        """
        if optimization_goal == "minimize_interest":
            # Pay right after receiving income
            for income_date in income_dates:
                if income_date <= due_date:
                    return max(income_date, due_date - timedelta(days=3))
            return due_date
        else:
            # Pay on due date to maximize float
            return due_date

    def _select_payment_account_smart(
        self,
        bill: Bill,
        amount: float,
        working_balances: dict,
        optimization_goal: str
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Select the best account to pay a bill from using smart selection.
        
        Priority:
        1. Preferred account (if has funds)
        2. Checking accounts with sufficient funds (ordered by balance, lowest first to preserve larger buffers)
        3. Savings accounts with sufficient funds (last resort)
        """
        candidates = []
        
        # Check preferred account first
        if bill.preferred_source_bank and bill.preferred_source_account:
            key = f"{bill.preferred_source_bank}:{bill.preferred_source_account}"
            if key in working_balances and working_balances[key] >= amount:
                return bill.preferred_source_bank, bill.preferred_source_account
        
        # Collect all viable accounts
        for bank in self.banks:
            for name, account in bank.accounts.items():
                key = f"{bank.name}:{name}"
                balance = working_balances.get(key, account.balance)
                
                if balance >= amount:
                    candidates.append({
                        'bank': bank.name,
                        'account': name,
                        'balance': balance,
                        'type': account.account_type.value,
                        'interest_rate': account.interest_rate
                    })
        
        if not candidates:
            return None, None
        
        # Sort candidates by preference
        def sort_key(c):
            # Prefer checking over savings
            type_priority = 0 if c['type'] == 'checking' else 1
            # Within same type, prefer lower balance (preserve larger buffer in other accounts)
            # But ensure we still have enough
            balance_priority = c['balance']
            return (type_priority, balance_priority)
        
        candidates.sort(key=sort_key)
        
        best = candidates[0]
        return best['bank'], best['account']

    def _calculate_extra_credit_payments(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        target_credit_account: str,
        strategy: dict,
        promo_payoff_schedule: list[dict] = None
    ) -> list[dict]:
        """
        Calculate extra payments that can be made to the target credit account
        after all mandatory bills and promo payoffs are paid.
        
        Strategy:
        - After each income and bill cycle, calculate excess funds
        - Recommend extra payment to credit account while maintaining safety buffer
        - Promo payoffs are already accounted for, so subtract those from available funds
        """
        extra_payments = []
        safety_buffer = 500.0  # Keep at least $500 as buffer
        promo_payoff_schedule = promo_payoff_schedule or []
        
        # Find the target credit account
        target_credit = None
        target_bank_name = None
        for bank in self.banks:
            for name, credit in bank.credit_accounts.items():
                if name == target_credit_account:
                    target_credit = credit
                    target_bank_name = bank.name
                    break
            if target_credit:
                break
        
        if not target_credit:
            return []
        
        # Calculate running balance after each income cycle
        running_balance = sum(
            account.balance
            for bank in self.banks
            for account in bank.accounts.values()
        )
        
        remaining_credit_balance = target_credit.balance
        
        # Subtract any promo balances that are being paid separately
        # (to avoid double-counting if target has promos)
        for promo_payment in promo_payoff_schedule:
            if promo_payment['credit_account'] == target_credit_account:
                remaining_credit_balance -= promo_payment['amount']
        
        # Group bills by the income period they fall into
        for i, income_date in enumerate(income_dates):
            # Get income amount for this date
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )
            
            running_balance += income_amount
            
            # Find next income date or end of period
            next_income = income_dates[i + 1] if i + 1 < len(income_dates) else end_date + timedelta(days=1)
            
            # Subtract bills due between this income and next
            bills_in_period = sum(
                b['amount'] for b in bill_schedule
                if income_date <= b['due_date'] < next_income
            )
            
            running_balance -= bills_in_period
            
            # Subtract promo payoffs scheduled in this period
            promos_in_period = sum(
                p['amount'] for p in promo_payoff_schedule
                if income_date <= p['date'] < next_income
            )
            
            running_balance -= promos_in_period
            
            # Calculate extra payment (excess over safety buffer)
            excess = running_balance - safety_buffer
            
            if excess > 0 and remaining_credit_balance > 0:
                # Don't pay more than what's owed
                payment_amount = min(excess, remaining_credit_balance)
                
                # Round down to nearest $50 for practical payment amounts
                payment_amount = (payment_amount // 50) * 50
                
                if payment_amount >= 50:  # Minimum extra payment
                    # Schedule payment for a few days after income
                    payment_date = income_date + timedelta(days=2)
                    if payment_date > end_date:
                        payment_date = end_date
                    
                    extra_payments.append({
                        'credit_account': target_credit_account,
                        'bank': target_bank_name,
                        'amount': payment_amount,
                        'date': payment_date,
                        'description': f"Extra payment to {target_credit_account}"
                    })
                    
                    running_balance -= payment_amount
                    remaining_credit_balance -= payment_amount
        
        return extra_payments

    def _check_constraints(self, simulation_result: dict, bill_schedule: list[dict], mortgage_schedule: list[dict] = None) -> list[str]:
        """
        Check for constraint violations in the simulation.
        
        Args:
            simulation_result: Result from timeline simulation
            bill_schedule: List of scheduled bills with due dates
            mortgage_schedule: List of scheduled mortgage payments
            
        Returns:
            List of violation/warning messages
        """
        violations = []
        mortgage_schedule = mortgage_schedule or []

        # Check for negative balances at any point
        for snapshot in simulation_result.get('snapshots', []):
            for account_name, balance in snapshot.get('balances', {}).items():
                if balance < -0.01:  # Allow small floating point errors
                    violations.append(
                        f"Account {account_name} would overdraft on {snapshot['date']}: ${balance:.2f}"
                    )

        # Check for deferred/unpaid bills
        for cf_item in simulation_result["cash_flow"]:
            if cf_item.get("type") == "BILL_DEFERRED":
                violations.append(f"Bill could not be paid: {cf_item['description']}")

        # Check that all bills have a payment strategy
        paid_bills = set()
        for cf_item in simulation_result["cash_flow"]:
            if cf_item.get("type") == "BILL_PAYMENT":
                paid_bills.add(cf_item.get("description", ""))
        
        for bill_info in bill_schedule:
            if bill_info['bill_name'] not in paid_bills:
                violations.append(f"No payment scheduled for: {bill_info['bill_name']} due {bill_info['due_date']}")

        # Check mortgage payments
        if mortgage_schedule:
            paid_mortgages = set()
            for cf_item in simulation_result["cash_flow"]:
                if cf_item.get("type") == "MORTGAGE_PAYMENT":
                    paid_mortgages.add(cf_item.get("mortgage_name", cf_item.get("description", "")))
            
            for mortgage_info in mortgage_schedule:
                mortgage_name = mortgage_info.get('mortgage_name', mortgage_info.get('account_name', ''))
                due_date = mortgage_info.get('due_date')
                total_payment = mortgage_info.get('total_payment', 0)
                
                # Check if mortgage payment was made
                if mortgage_name and mortgage_name not in paid_mortgages:
                    violations.append(
                        f"Mortgage payment not scheduled: {mortgage_name} "
                        f"(${total_payment:,.2f} due {due_date})"
                    )
                
                # Check if there are sufficient funds on the due date
                for snapshot in simulation_result.get('snapshots', []):
                    if snapshot['date'] == due_date:
                        # Find the source account balance
                        source_bank = mortgage_info.get('source_bank')
                        source_account = mortgage_info.get('source_account')
                        
                        if source_bank and source_account:
                            account_key = f"{source_bank}:{source_account}"
                            balance = snapshot.get('balances', {}).get(account_key, 0)
                            
                            if balance < total_payment:
                                shortfall = total_payment - balance
                                violations.append(
                                    f"Insufficient funds for {mortgage_name} on {due_date}: "
                                    f"need ${total_payment:,.2f}, have ${balance:,.2f} "
                                    f"(shortfall: ${shortfall:,.2f})"
                                )
                        break

        # Check for low balance warnings (not overdraft, but concerning)
        low_balance_threshold = 100.0
        for snapshot in simulation_result.get('snapshots', []):
            for account_name, balance in snapshot.get('balances', {}).items():
                if 0 <= balance < low_balance_threshold:
                    # Only warn once per account
                    warning = f"Low balance warning: {account_name} drops to ${balance:.2f} on {snapshot['date']}"
                    if warning not in violations:
                        violations.append(warning)

        return violations

    def generate_multiple_strategies(
        self,
        start_date: date,
        end_date: date,
        num_strategies: int = 3,
        target_credit_account: str = None
    ) -> list[PaymentPlan]:
        """
        Generate multiple payment strategies with different optimization goals.
        Allows comparison of trade-offs.
        """
        strategies = []

        goals = ["maximize_discretionary", "minimize_interest"]
        
        # Add credit payoff goal if target specified
        if target_credit_account:
            goals.append("payoff_credit_account")

        for goal in goals[:num_strategies]:
            try:
                if goal == "payoff_credit_account":
                    plan = self.optimize_payment_schedule(
                        start_date, end_date, goal, target_credit_account
                    )
                else:
                    plan = self.optimize_payment_schedule(start_date, end_date, goal)
                strategies.append(plan)
            except Exception as e:
                # Skip goals that fail
                continue

        return sorted(strategies, key=lambda p: p.final_discretionary, reverse=True)

    def get_credit_payoff_plan(
        self,
        target_credit_account: str,
        months: int = 12,
        start_date: date = None
    ) -> PaymentPlan:
        """
        Generate a plan specifically focused on paying off a credit account.
        
        Args:
            target_credit_account: Name of the credit account to pay off
            months: Number of months for the payoff plan
            start_date: Start date (default: today)
            
        Returns:
            PaymentPlan with strategy and extra credit payments
        """
        start_date = start_date or date.today()
        end_date = start_date + timedelta(days=30 * months)
        
        return self.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="payoff_credit_account",
            target_credit_account=target_credit_account
        )

    def _calculate_savings_transfers(
        self,
        start_date: date,
        end_date: date,
        income_dates: list[date],
        bill_schedule: list[dict],
        mortgage_schedule: list[dict],
        promo_payoff_schedule: list[dict],
        extra_credit_payments: list[dict]
    ) -> tuple[list[SavingsTransfer], float]:
        """
        Calculate optimal transfers between checking and savings accounts to maximize interest.
        
        Strategy:
        1. After income arrives and bills are accounted for, identify excess funds in checking
        2. Transfer excess to savings accounts with higher APY (within same bank for easy transfers)
        3. Before bills are due, transfer back from savings to checking as needed
        4. Prioritize high-yield savings accounts
        
        Args:
            start_date: Start of planning period
            end_date: End of planning period
            income_dates: List of dates when income arrives
            bill_schedule: List of bills with due dates
            mortgage_schedule: List of mortgage payments
            promo_payoff_schedule: Scheduled promo payoff payments
            extra_credit_payments: Scheduled extra credit payments
            
        Returns:
            Tuple of (list of transfer recommendations, estimated interest gained)
        """
        transfers = []
        total_estimated_interest = 0.0
        
        # Minimum buffer to keep in checking at all times
        checking_buffer = 500.0
        
        # Minimum transfer amount (not worth transferring tiny amounts)
        min_transfer_amount = 100.0
        
        # Find all checking/savings pairs within each bank
        bank_account_pairs = []
        for bank in self.banks:
            checking_accounts = []
            savings_accounts = []
            
            for name, account in bank.accounts.items():
                if account.account_type.value == "checking":
                    checking_accounts.append({
                        'name': name,
                        'account': account,
                        'balance': account.balance,
                        'apy': account.interest_rate
                    })
                elif account.account_type.value == "savings":
                    savings_accounts.append({
                        'name': name,
                        'account': account,
                        'balance': account.balance,
                        'apy': account.interest_rate
                    })
            
            # Sort savings by APY (highest first)
            savings_accounts.sort(key=lambda x: x['apy'], reverse=True)
            
            if checking_accounts and savings_accounts:
                bank_account_pairs.append({
                    'bank': bank,
                    'bank_name': bank.name,
                    'checking': checking_accounts,
                    'savings': savings_accounts
                })
        
        if not bank_account_pairs:
            return [], 0.0  # No checking/savings pairs available
        
        # Build a timeline of cash needs
        cash_events = []
        
        # Add income events (positive)
        for income_date in income_dates:
            income_amount = sum(
                inc.amount for inc in self.income_sources
                if income_date in inc.get_pay_dates_in_range(income_date - timedelta(days=1), income_date)
            )
            if income_amount > 0:
                cash_events.append({
                    'date': income_date,
                    'type': 'income',
                    'amount': income_amount
                })
        
        # Add bill events (negative)
        for bill in bill_schedule:
            cash_events.append({
                'date': bill['due_date'],
                'type': 'bill',
                'amount': -bill['amount']
            })
        
        # Add mortgage events (negative)
        for mortgage in mortgage_schedule:
            cash_events.append({
                'date': mortgage['due_date'],
                'type': 'mortgage',
                'amount': -mortgage['total_payment']
            })
        
        # Add promo payoff events (negative)
        for promo in promo_payoff_schedule:
            cash_events.append({
                'date': promo['date'],
                'type': 'promo_payment',
                'amount': -promo['amount']
            })
        
        # Add extra credit payments (negative)
        for payment in extra_credit_payments:
            cash_events.append({
                'date': payment['date'],
                'type': 'credit_payment',
                'amount': -payment['amount']
            })
        
        # Sort events by date
        cash_events.sort(key=lambda x: x['date'])
        
        # Process each bank's accounts
        for pair in bank_account_pairs:
            bank_name = pair['bank_name']
            primary_checking = pair['checking'][0]  # Use first checking account
            best_savings = pair['savings'][0]  # Highest APY savings
            
            # Skip if savings APY is 0 or negligible
            if best_savings['apy'] <= 0.01:
                continue
            
            # Calculate monthly interest rate
            monthly_rate = best_savings['apy'] / 100 / 12
            
            # Track running balances
            checking_balance = primary_checking['balance']
            savings_balance = best_savings['balance']
            
            # Track amounts we've moved to savings that need to come back
            pending_return_from_savings = 0.0
            
            # Process timeline to find optimal transfer points
            for i, event in enumerate(cash_events):
                event_date = event['date']
                
                if event_date < start_date or event_date > end_date:
                    continue
                
                # Apply event to checking balance (simplified - assumes all from checking)
                if event['type'] == 'income':
                    checking_balance += event['amount']
                else:
                    checking_balance += event['amount']  # amount is negative for expenses
                
                # After income: check if we can move excess to savings
                if event['type'] == 'income':
                    # Look ahead to see what we need before next income
                    next_income_idx = None
                    for j in range(i + 1, len(cash_events)):
                        if cash_events[j]['type'] == 'income':
                            next_income_idx = j
                            break
                    
                    # Calculate total outflows before next income
                    outflows_before_next_income = 0.0
                    if next_income_idx:
                        for j in range(i + 1, next_income_idx):
                            if cash_events[j]['amount'] < 0:
                                outflows_before_next_income += abs(cash_events[j]['amount'])
                    else:
                        # No more income - need to cover remaining expenses
                        for j in range(i + 1, len(cash_events)):
                            if cash_events[j]['amount'] < 0:
                                outflows_before_next_income += abs(cash_events[j]['amount'])
                    
                    # Calculate how much we can safely move to savings
                    required_in_checking = outflows_before_next_income + checking_buffer
                    excess = checking_balance - required_in_checking
                    
                    if excess >= min_transfer_amount:
                        # Round to nearest $100
                        transfer_amount = (excess // 100) * 100
                        
                        if transfer_amount >= min_transfer_amount:
                            # Calculate estimated interest earned
                            # Estimate days until we need the money back
                            if next_income_idx:
                                days_in_savings = (cash_events[next_income_idx]['date'] - event_date).days
                            else:
                                days_in_savings = (end_date - event_date).days
                            
                            # Daily interest rate
                            daily_rate = best_savings['apy'] / 100 / 365
                            interest_earned = transfer_amount * daily_rate * days_in_savings
                            
                            transfers.append(SavingsTransfer(
                                from_bank=bank_name,
                                from_account=primary_checking['name'],
                                to_bank=bank_name,
                                to_account=best_savings['name'],
                                amount=transfer_amount,
                                transfer_date=event_date + timedelta(days=1),  # Day after income
                                reason='maximize_interest',
                                estimated_interest_gain=interest_earned
                            ))
                            
                            checking_balance -= transfer_amount
                            savings_balance += transfer_amount
                            pending_return_from_savings += transfer_amount
                            total_estimated_interest += interest_earned
                
                # Before large outflows: check if we need to transfer back from savings
                if event['amount'] < 0:
                    shortfall = checking_buffer - checking_balance
                    
                    if shortfall > 0 and pending_return_from_savings > 0:
                        # Need to bring money back from savings
                        return_amount = min(shortfall + checking_buffer, pending_return_from_savings, savings_balance)
                        
                        if return_amount >= min_transfer_amount:
                            return_amount = (return_amount // 100) * 100
                            
                            transfers.append(SavingsTransfer(
                                from_bank=bank_name,
                                from_account=best_savings['name'],
                                to_bank=bank_name,
                                to_account=primary_checking['name'],
                                amount=return_amount,
                                transfer_date=event_date - timedelta(days=1),  # Day before bill
                                reason='fund_upcoming_bills',
                                estimated_interest_gain=0.0
                            ))
                            
                            savings_balance -= return_amount
                            checking_balance += return_amount
                            pending_return_from_savings -= return_amount
        
        # Sort transfers by date
        transfers.sort(key=lambda x: x.transfer_date)
        
        # Consolidate transfers on the same date between the same accounts
        consolidated = []
        for transfer in transfers:
            # Check if we can merge with an existing transfer
            merged = False
            for existing in consolidated:
                if (existing.transfer_date == transfer.transfer_date and
                    existing.from_bank == transfer.from_bank and
                    existing.from_account == transfer.from_account and
                    existing.to_account == transfer.to_account and
                    existing.reason == transfer.reason):
                    # Merge
                    existing.amount += transfer.amount
                    existing.estimated_interest_gain += transfer.estimated_interest_gain
                    merged = True
                    break
            
            if not merged:
                consolidated.append(transfer)
        
        return consolidated, total_estimated_interest

