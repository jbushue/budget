from copy import deepcopy
from models.bank_account import BankAccount
from models.credit_card_account import CreditAccount
from models.mortgage_account import MortgageAccount, EscrowBreakdown


class Bank:
    """Represents a financial institution holding bank, credit, and/or mortgage accounts."""

    def __init__(self, name: str, bank_type: str = "traditional"):
        """
        Args:
            name: Name of the bank
            bank_type: 'traditional' for regular bank, 'credit_issuer' for credit card companies,
                       'mortgage_lender' for mortgage companies
        """
        self.name = name
        self.bank_type = bank_type  # 'traditional', 'credit_issuer', 'mortgage_lender', etc.
        self.accounts: dict[str, BankAccount] = {}  # Traditional bank accounts
        self.credit_accounts: dict[str, CreditAccount] = {}  # Credit card accounts
        self.mortgage_accounts: dict[str, MortgageAccount] = {}  # Mortgage accounts

    def add_account(
        self,
        account_type: str,
        account_name: str,
        starting_balance: float = 0.0,
        interest_rate: float = 0.0,
        interest_accrual_date: int = None
    ) -> BankAccount:
        """Add a traditional bank account (checking/savings)."""
        if account_name in self.accounts:
            raise ValueError(f"Account '{account_name}' already exists in {self.name}.")

        account = BankAccount(
            account_type=account_type,
            account_name=account_name,
            balance=starting_balance,
            interest_rate=interest_rate,
            interest_accrual_date=interest_accrual_date
        )
        self.accounts[account_name] = account
        return account

    def add_credit_account(
        self,
        account_name: str,
        credit_limit: float,
        interest_rate: float = 0.0,
        payment_due_date: int = None,
        statement_date: int = None
    ) -> CreditAccount:
        """Add a credit account."""
        if account_name in self.credit_accounts:
            raise ValueError(f"Credit account '{account_name}' already exists in {self.name}.")

        account = CreditAccount(
            account_name=account_name,
            credit_limit=credit_limit,
            interest_rate=interest_rate,
            payment_due_date=payment_due_date,
            statement_date=statement_date
        )
        self.credit_accounts[account_name] = account
        return account

    def add_mortgage_account(
        self,
        account_name: str,
        original_principal: float,
        interest_rate: float = 0.0,
        loan_term_months: int = 360,
        current_principal: float = None,
        payment_due_date: int = 1,
        escrow: EscrowBreakdown = None,
        preferred_source_bank: str = None,
        preferred_source_account: str = None
    ) -> MortgageAccount:
        """Add a mortgage account."""
        if account_name in self.mortgage_accounts:
            raise ValueError(f"Mortgage account '{account_name}' already exists in {self.name}.")

        account = MortgageAccount(
            account_name=account_name,
            original_principal=original_principal,
            current_principal=current_principal,
            interest_rate=interest_rate,
            loan_term_months=loan_term_months,
            payment_due_date=payment_due_date,
            escrow=escrow,
            preferred_source_bank=preferred_source_bank,
            preferred_source_account=preferred_source_account
        )
        self.mortgage_accounts[account_name] = account
        return account

    def get_account(self, account_name: str) -> BankAccount | None:
        """Get a traditional bank account by name."""
        return self.accounts.get(account_name)

    def get_credit_account(self, account_name: str) -> CreditAccount | None:
        """Get a credit account by name."""
        return self.credit_accounts.get(account_name)

    def get_mortgage_account(self, account_name: str) -> MortgageAccount | None:
        """Get a mortgage account by name."""
        return self.mortgage_accounts.get(account_name)

    def get_all_accounts(self) -> list[BankAccount]:
        """Get all traditional bank accounts."""
        return list(self.accounts.values())

    def get_all_credit_accounts(self) -> list[CreditAccount]:
        """Get all credit accounts."""
        return list(self.credit_accounts.values())

    def get_all_mortgage_accounts(self) -> list[MortgageAccount]:
        """Get all mortgage accounts."""
        return list(self.mortgage_accounts.values())

    def total_balance(self) -> float:
        """Get total balance across all traditional accounts."""
        return sum(acc.balance for acc in self.accounts.values())

    def total_credit_owed(self) -> float:
        """Get total amount owed across all credit accounts."""
        return sum(acc.balance for acc in self.credit_accounts.values())

    def total_mortgage_owed(self) -> float:
        """Get total principal owed across all mortgage accounts."""
        return sum(acc.current_principal for acc in self.mortgage_accounts.values())

    def total_liabilities(self) -> float:
        """Get total liabilities (credit + mortgage)."""
        return self.total_credit_owed() + self.total_mortgage_owed()

    def total_available_credit(self) -> float:
        """Get total available credit across all credit accounts."""
        return sum(acc.available_credit for acc in self.credit_accounts.values())

    def update_account_balance(
        self,
        account_name: str,
        new_balance: float,
        description: str = "Manual balance adjustment"
    ) -> BankAccount | None:
        """
        Update an account balance directly.
        Useful for syncing with bank statements.

        Args:
            account_name: Name of account to update
            new_balance: New balance amount
            description: Reason for the update

        Returns:
            Updated account or None if not found
        """
        if account_name in self.accounts:
            account = self.accounts[account_name]
            difference = new_balance - account.balance

            if difference > 0:
                account.deposit(difference, description=description)
            elif difference < 0:
                account.withdraw(-difference, description=description)

            return account
        return None

    def update_credit_balance(
        self,
        account_name: str,
        new_balance: float,
        description: str = "Manual balance adjustment"
    ) -> CreditAccount | None:
        """
        Update a credit account balance directly.

        Args:
            account_name: Name of credit account to update
            new_balance: New balance owed
            description: Reason for the update

        Returns:
            Updated credit account or None if not found
        """
        if account_name in self.credit_accounts:
            account = self.credit_accounts[account_name]
            account.balance = new_balance
            account._record_transaction("ADJUSTMENT", 0, description)
            return account
        return None

    def copy(self):
        """Create a deep copy of this bank and all its accounts."""
        return deepcopy(self)

    def __repr__(self):
        return (
            f"Bank({self.name}, {len(self.accounts)} bank accounts, "
            f"{len(self.credit_accounts)} credit accounts, "
            f"{len(self.mortgage_accounts)} mortgage accounts)"
        )
