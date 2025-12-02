class BankAccount:

    def __init__(self, account_type: str, account_name: str, balance: float = 0.0):
        allowed_types = ['savings', 'checking']
        if account_type not in allowed_types:
            raise ValueError(f"Invalid account type: {account_type}. Allowed types are: {allowed_types}")
        self.account_type = account_type
        self.account_name = account_name
        if balance < 0:
            raise ValueError("Starting balance cannot be negative. If it is... you're in trouble! ;)")
        self.balance = balance

    def deposit(self, amount: float):
        if amount < 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance += amount

    def withdraw(self, amount: float):
        if amount < 0:
            raise ValueError("Withdrawal amount must be positive.")
        if self.balance < amount:
            raise ValueError("Insufficient funds.")
        self.balance -= amount

    def calculate_interest(self, annual_rate: float, months: int):
        if self.account_type != 'savings':
            raise ValueError("Interest can only be calculated for savings accounts.")
        if annual_rate < 0 or months < 0:
            raise ValueError("Annual rate and months must be non-negative.")
        monthly_rate = annual_rate / 12 / 100
        interest = self.balance * monthly_rate * months
        self.balance += interest
        return interest