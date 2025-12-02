from datetime import date


class CreditAccount:
    def __init__(self, account_name: str, credit_limit: float, interest_rate: float, payment_due_date: date = None):
        if credit_limit <= 0:
            raise ValueError("Credit limit must be positive.")
        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative.")
        self.account_name: str = account_name
        self.credit_limit: float = credit_limit
        self.interest_rate: float = interest_rate  # annual percentage rate (APR)
        self.balance: float = 0.0  # Amount owed
        self.spending_limit: float = credit_limit  # Default to the credit limit
        self.payment_due_date: date = payment_due_date

    def set_payment_due_date(self, due_date: date) -> None:
        self.payment_due_date = due_date

    def get_payment_due_date(self) -> date:
        return self.payment_due_date

    def set_spending_limit(self, limit: float) -> None:
        if limit <= 0 or limit > self.credit_limit:
            raise ValueError("Spending limit must be positive and not exceed the credit limit.")
        self.spending_limit = limit

    def get_spending_limit(self) -> float:
        return self.spending_limit

    def make_purchase(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Purchase amount must be positive.")
        if amount > self.spending_limit:
            raise ValueError("Purchase exceeds the spending limit.")
        if self.balance + amount > self.credit_limit:
            raise ValueError("Purchase would exceed credit limit.")
        self.balance += amount

    def make_payment(self, amount: float, account_name: str, bank) -> None:
        """
        Withdraws `amount` from the specified account in `bank` and applies it to the credit card balance.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        if account_name not in bank.accounts:
            raise ValueError(f"Account '{account_name}' does not exist in the bank.")
        if bank.accounts[account_name].balance < amount:
            raise ValueError("Insufficient funds in the specified bank account.")
        bank.accounts[account_name].balance -= amount
        self.balance -= amount
        if self.balance < 0:
            self.balance = 0.0

    def accrue_interest_if_due(self, current_date: date) -> float:
        """
        Accrues interest if current_date is after the payment due date.
        Returns the interest accrued, or 0 if not accrued.
        """
        if self.payment_due_date and current_date > self.payment_due_date:
            return self.accrue_interest()
        return 0.0

    def accrue_interest(self, months: int = 1) -> float:
        if months < 0:
            raise ValueError("Months must be non-negative.")
        monthly_rate = self.interest_rate / 12 / 100
        interest = self.balance * monthly_rate * months
        self.balance += interest
        return interest

    def available_credit(self) -> float:
        return self.credit_limit - self.balance

    def get_balance(self) -> float:
        return self.balance

    def calculate_minimum_payment(self, percent: float = 0.02, fixed: float = 25.0) -> float:
        """
        Calculates the minimum payment due (2% of balance or $25, whichever is greater, but not more than the balance).
        """
        if self.balance == 0:
            return 0.0
        min_payment = max(percent * self.balance, fixed)
        return min(min_payment, self.balance)

    def calculate_monthly_payment(self, months: int) -> float:
        """
        Calculates the fixed monthly payment required to pay off the balance (with interest) in the given number of months.
        Uses the standard amortization formula.
        """
        if months <= 0:
            raise ValueError("Months must be positive.")
        if self.balance == 0:
            return 0.0
        monthly_rate = self.interest_rate / 12 / 100
        if monthly_rate == 0:
            return self.balance / months
        payment = self.balance * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        return payment