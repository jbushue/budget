from models.bank_account import BankAccount
from models.credit_card_account import CreditAccount

class Bank:
    def __init__(self, name: str, address: str):
        self.name: str = name
        self.address: str = address
        self.accounts: dict[str, BankAccount] = {}
        self.credit_accounts: dict[str, CreditAccount] = {}

    def add_account(self, account_type: str, account_name: str, starting_balance: float = 0.0) -> None:
        if account_name in self.accounts:
            raise ValueError("Account with this name already exists.")
        self.accounts[account_name] = BankAccount(account_type, account_name, starting_balance)

    def add_credit_account(self, account_name: str, credit_limit: float, interest_rate: float) -> None:
        if account_name in self.credit_accounts:
            raise ValueError("Credit account with this name already exists.")
        self.credit_accounts[account_name] = CreditAccount(account_name, credit_limit, interest_rate)

    def make_purchase(self, account_name: str, amount: float) -> None:
        if account_name not in self.credit_accounts:
            raise ValueError("Credit account does not exist.")
        self.credit_accounts[account_name].make_purchase(amount)

    def make_payment(self, account_name: str, amount: float) -> None:
        if account_name not in self.credit_accounts:
            raise ValueError("Credit account does not exist.")
        self.credit_accounts[account_name].make_payment(amount)

    def accrue_credit_interest(self, account_name: str, months: int = 1) -> float:
        if account_name not in self.credit_accounts:
            raise ValueError("Credit account does not exist.")
        return self.credit_accounts[account_name].accrue_interest(months)

    def get_credit_balance(self, account_name: str) -> float:
        if account_name not in self.credit_accounts:
            raise ValueError("Credit account does not exist.")
        return self.credit_accounts[account_name].get_balance()

    def get_available_credit(self, account_name: str) -> float:
        if account_name not in self.credit_accounts:
            raise ValueError("Credit account does not exist.")
        return self.credit_accounts[account_name].available_credit()