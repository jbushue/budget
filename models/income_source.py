from models.bank import Bank

class IncomeSource:
    def __init__(self, source_name: str, amount: float, frequency: str = "monthly", distribution: dict = None):
        if amount <= 0:
            raise ValueError("Income amount must be positive.")
        self.source_name: str = source_name
        self.amount: float = amount
        self.frequency: str = frequency  # e.g., 'monthly', 'weekly'
        self.distribution: dict = distribution or {} # {account_name: amount or "remainder"}

    def deposit_all(self, bank: Bank) -> None:
        if not self.distribution:
            # Default: deposit all to the first account
            account_name = next(iter(bank.accounts))
            bank.accounts[account_name].deposit(self.amount)
            return

        total_fixed = 0.0
        remainder_account = None

        for account_name, value in self.distribution.items():
            if value == "remainder":
                if remainder_account is not None:
                    raise ValueError("Only one account can be set as 'remainder'.")
                remainder_account = account_name
            else:
                if account_name not in bank.accounts:
                    raise ValueError(f"Account {account_name} does not exist in the bank.")
                bank.accounts[account_name].deposit(float(value))
                total_fixed += float(value)

        if remainder_account:
            remainder = self.amount - total_fixed
            if remainder < 0:
                raise ValueError("Distributed amounts exceed total income.")
            if remainder_account not in bank.accounts:
                raise ValueError(f"Account {remainder_account} does not exist in the bank.")
            bank.accounts[remainder_account].deposit(remainder)
        elif abs(total_fixed - self.amount) > 1e-6:
            raise ValueError("Distributed amounts do not sum to total income and no remainder account specified.")