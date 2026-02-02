"""
Mortgage Account model for tracking home loans with escrow support.
"""

from datetime import date, timedelta
from copy import deepcopy
from dataclasses import dataclass


@dataclass
class EscrowBreakdown:
    """Breakdown of escrow components."""
    property_tax_monthly: float = 0.0
    homeowners_insurance_monthly: float = 0.0
    pmi_monthly: float = 0.0  # Private Mortgage Insurance
    hoa_monthly: float = 0.0  # Homeowners Association fees
    other_monthly: float = 0.0
    
    @property
    def total_monthly(self) -> float:
        """Total monthly escrow amount."""
        return (
            self.property_tax_monthly +
            self.homeowners_insurance_monthly +
            self.pmi_monthly +
            self.hoa_monthly +
            self.other_monthly
        )


class MortgageAccount:
    """
    Represents a mortgage loan account with principal, interest, and escrow tracking.
    
    Features:
    - Tracks principal balance and payoff progress
    - Calculates amortization schedule
    - Manages escrow account for taxes, insurance, PMI
    - Supports extra principal payments
    - Tracks payment history
    """

    def __init__(
        self,
        account_name: str,
        original_principal: float,
        current_principal: float,
        interest_rate: float,  # Annual interest rate (APR) as percentage
        loan_term_months: int,  # Total loan term in months (e.g., 360 for 30-year)
        payment_due_date: int = 1,  # Day of month (1-31)
        start_date: date = None,
        escrow: EscrowBreakdown = None,
        preferred_source_bank: str = None,
        preferred_source_account: str = None
    ):
        """
        Args:
            account_name: Name of the mortgage account (e.g., "Primary Home Mortgage")
            original_principal: Original loan amount
            current_principal: Current principal balance
            interest_rate: Annual interest rate as percentage (e.g., 6.5 for 6.5%)
            loan_term_months: Total loan term in months
            payment_due_date: Day of month when payment is due
            start_date: When the loan started (for amortization tracking)
            escrow: Escrow breakdown for taxes, insurance, etc.
            preferred_source_bank: Preferred bank to make payments from
            preferred_source_account: Preferred account to make payments from
        """
        if original_principal <= 0:
            raise ValueError("Original principal must be positive.")
        if current_principal < 0:
            raise ValueError("Current principal cannot be negative.")
        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative.")
        if loan_term_months <= 0:
            raise ValueError("Loan term must be positive.")
        if not (1 <= payment_due_date <= 31):
            raise ValueError("Payment due date must be between 1 and 31.")

        self.account_name = account_name
        self.original_principal = original_principal
        self.current_principal = current_principal
        self.interest_rate = interest_rate
        self.loan_term_months = loan_term_months
        self.payment_due_date = payment_due_date
        self.start_date = start_date or date.today()
        self.escrow = escrow or EscrowBreakdown()
        
        # Payment source preferences
        self.preferred_source_bank = preferred_source_bank
        self.preferred_source_account = preferred_source_account
        
        # Tracking
        self.payment_history: list[dict] = []
        self.extra_principal_payments: list[dict] = []
        self.escrow_balance: float = 0.0  # Current escrow account balance
        self.is_paid_this_period = False

    @property
    def monthly_interest_rate(self) -> float:
        """Monthly interest rate as decimal."""
        return self.interest_rate / 100 / 12

    @property
    def base_monthly_payment(self) -> float:
        """
        Calculate the base monthly payment (principal + interest only).
        Uses standard amortization formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
        """
        if self.current_principal <= 0:
            return 0.0
        
        r = self.monthly_interest_rate
        if r == 0:
            # No interest - simple division
            return self.current_principal / self.remaining_months
        
        n = self.loan_term_months
        payment = self.original_principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        return round(payment, 2)

    @property
    def total_monthly_payment(self) -> float:
        """Total monthly payment including escrow."""
        return self.base_monthly_payment + self.escrow.total_monthly

    @property
    def current_monthly_interest(self) -> float:
        """Calculate interest portion of current month's payment."""
        return round(self.current_principal * self.monthly_interest_rate, 2)

    @property
    def current_monthly_principal(self) -> float:
        """Calculate principal portion of current month's payment."""
        return round(self.base_monthly_payment - self.current_monthly_interest, 2)

    @property
    def remaining_months(self) -> int:
        """Estimate remaining months based on current principal and payment."""
        if self.current_principal <= 0:
            return 0
        if self.base_monthly_payment <= self.current_monthly_interest:
            return 999  # Effectively infinite if payment doesn't cover interest
        
        # Use logarithm to calculate remaining months
        import math
        r = self.monthly_interest_rate
        if r == 0:
            return int(self.current_principal / self.base_monthly_payment) + 1
        
        payment = self.base_monthly_payment
        remaining = math.log(payment / (payment - r * self.current_principal)) / math.log(1 + r)
        return max(1, int(remaining) + 1)

    @property
    def payoff_date(self) -> date:
        """Estimated payoff date based on current payment schedule."""
        return date.today() + timedelta(days=30 * self.remaining_months)

    @property
    def total_interest_remaining(self) -> float:
        """Estimate total interest remaining over life of loan."""
        total_payments = self.base_monthly_payment * self.remaining_months
        return max(0, total_payments - self.current_principal)

    @property
    def equity(self) -> float:
        """Current equity (original principal - current principal)."""
        return self.original_principal - self.current_principal

    @property
    def loan_to_value_ratio(self) -> float:
        """Current LTV ratio (current principal / original principal)."""
        if self.original_principal == 0:
            return 0.0
        return self.current_principal / self.original_principal

    def make_payment(
        self,
        amount: float = None,
        extra_principal: float = 0.0,
        source_bank: str = None,
        source_account: str = None,
        payment_date: date = None
    ) -> dict:
        """
        Make a mortgage payment.
        
        Args:
            amount: Payment amount (defaults to total_monthly_payment)
            extra_principal: Additional principal payment
            source_bank: Bank the payment came from
            source_account: Account the payment came from
            payment_date: Date of payment
            
        Returns:
            Dictionary with payment breakdown
        """
        payment_date = payment_date or date.today()
        amount = amount or self.total_monthly_payment
        
        # Calculate payment breakdown
        interest_portion = self.current_monthly_interest
        escrow_portion = self.escrow.total_monthly
        
        # Principal is what's left after interest and escrow
        base_principal = amount - interest_portion - escrow_portion
        total_principal = base_principal + extra_principal
        
        # Update balances
        self.current_principal = max(0, self.current_principal - total_principal)
        self.escrow_balance += escrow_portion
        
        # Record payment
        payment_record = {
            "date": payment_date,
            "total_amount": amount + extra_principal,
            "principal": total_principal,
            "interest": interest_portion,
            "escrow": escrow_portion,
            "extra_principal": extra_principal,
            "source_bank": source_bank or self.preferred_source_bank,
            "source_account": source_account or self.preferred_source_account,
            "principal_after": self.current_principal
        }
        
        self.payment_history.append(payment_record)
        
        if extra_principal > 0:
            self.extra_principal_payments.append({
                "date": payment_date,
                "amount": extra_principal,
                "principal_after": self.current_principal
            })
        
        self.is_paid_this_period = True
        
        return payment_record

    def make_extra_principal_payment(
        self,
        amount: float,
        source_bank: str = None,
        source_account: str = None,
        payment_date: date = None
    ) -> dict:
        """
        Make an extra principal-only payment.
        
        Args:
            amount: Amount to apply to principal
            source_bank: Bank the payment came from
            source_account: Account the payment came from
            payment_date: Date of payment
            
        Returns:
            Dictionary with payment details
        """
        payment_date = payment_date or date.today()
        
        if amount <= 0:
            raise ValueError("Extra principal amount must be positive.")
        if amount > self.current_principal:
            amount = self.current_principal  # Cap at remaining principal
        
        self.current_principal -= amount
        
        payment_record = {
            "date": payment_date,
            "amount": amount,
            "type": "EXTRA_PRINCIPAL",
            "source_bank": source_bank or self.preferred_source_bank,
            "source_account": source_account or self.preferred_source_account,
            "principal_after": self.current_principal
        }
        
        self.extra_principal_payments.append(payment_record)
        self.payment_history.append(payment_record)
        
        return payment_record

    def disburse_escrow(self, amount: float, description: str, disbursement_date: date = None) -> dict:
        """
        Disburse funds from escrow account (e.g., pay property taxes).
        
        Args:
            amount: Amount to disburse
            description: What the disbursement is for
            disbursement_date: Date of disbursement
            
        Returns:
            Dictionary with disbursement details
        """
        disbursement_date = disbursement_date or date.today()
        
        if amount > self.escrow_balance:
            raise ValueError(f"Insufficient escrow balance. Available: ${self.escrow_balance:.2f}")
        
        self.escrow_balance -= amount
        
        return {
            "date": disbursement_date,
            "amount": amount,
            "description": description,
            "escrow_balance_after": self.escrow_balance
        }

    def get_amortization_schedule(self, months: int = None) -> list[dict]:
        """
        Generate an amortization schedule.
        
        Args:
            months: Number of months to generate (defaults to remaining months)
            
        Returns:
            List of monthly payment breakdowns
        """
        months = months or min(self.remaining_months, 360)
        schedule = []
        
        principal = self.current_principal
        payment = self.base_monthly_payment
        r = self.monthly_interest_rate
        
        current_date = date.today()
        
        for month in range(1, months + 1):
            if principal <= 0:
                break
            
            interest = round(principal * r, 2)
            principal_payment = min(round(payment - interest, 2), principal)
            principal -= principal_payment
            
            # Calculate payment date
            try:
                payment_date = date(
                    current_date.year + (current_date.month + month - 1) // 12,
                    (current_date.month + month - 1) % 12 + 1,
                    self.payment_due_date
                )
            except ValueError:
                # Handle month-end edge cases
                payment_date = date(
                    current_date.year + (current_date.month + month - 1) // 12,
                    (current_date.month + month - 1) % 12 + 1,
                    28
                )
            
            schedule.append({
                "month": month,
                "date": payment_date,
                "payment": payment + self.escrow.total_monthly,
                "principal": principal_payment,
                "interest": interest,
                "escrow": self.escrow.total_monthly,
                "principal_remaining": max(0, principal)
            })
        
        return schedule

    def calculate_payoff_with_extra(self, extra_monthly: float) -> dict:
        """
        Calculate payoff scenario with extra monthly payments.
        
        Args:
            extra_monthly: Extra amount to pay toward principal each month
            
        Returns:
            Dictionary with payoff analysis
        """
        principal = self.current_principal
        payment = self.base_monthly_payment
        r = self.monthly_interest_rate
        
        months_without_extra = self.remaining_months
        
        # Calculate with extra payments
        months_with_extra = 0
        total_interest_with_extra = 0.0
        
        while principal > 0 and months_with_extra < 600:  # Cap at 50 years
            interest = principal * r
            total_interest_with_extra += interest
            principal_payment = payment - interest + extra_monthly
            principal = max(0, principal - principal_payment)
            months_with_extra += 1
        
        # Calculate interest without extra payments
        total_interest_without_extra = self.total_interest_remaining
        
        return {
            "months_saved": months_without_extra - months_with_extra,
            "years_saved": (months_without_extra - months_with_extra) / 12,
            "interest_saved": total_interest_without_extra - total_interest_with_extra,
            "new_payoff_months": months_with_extra,
            "new_payoff_date": date.today() + timedelta(days=30 * months_with_extra),
            "extra_monthly": extra_monthly
        }

    def get_next_due_date(self, reference_date: date) -> date:
        """Calculate the next payment due date relative to a reference date."""
        year = reference_date.year
        month = reference_date.month

        try:
            next_due = date(year, month, self.payment_due_date)
        except ValueError:
            next_due = date(year, month, min(self.payment_due_date, 28))

        if next_due <= reference_date:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

            try:
                next_due = date(year, month, self.payment_due_date)
            except ValueError:
                next_due = date(year, month, min(self.payment_due_date, 28))

        return next_due

    def reset_period(self):
        """Reset the paid status for the next period."""
        self.is_paid_this_period = False

    def copy(self):
        """Create a deep copy of this mortgage."""
        return deepcopy(self)

    def __repr__(self):
        return (
            f"MortgageAccount({self.account_name}, "
            f"principal=${self.current_principal:,.2f}, "
            f"rate={self.interest_rate}%, "
            f"payment=${self.total_monthly_payment:,.2f}/mo)"
        )
