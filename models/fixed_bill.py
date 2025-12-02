from datetime import date

class FixedBill:
    def __init__(self, bill_name: str, amount: float, due_date: date, destination_account: str):
        if amount <= 0:
            raise ValueError("Bill amount must be positive.")
        self.bill_name: str = bill_name
        self.amount: float = amount
        self.due_date: date = due_date
        self.destination_account: str = destination_account
        self.paid: bool = False

    def pay_from_account(self, bank: Bank, account_name: str) -> None:
        if account_name not in bank.accounts:
            raise ValueError("Source account does not exist in the bank.")
        if self.paid:
            raise ValueError("Bill has already been paid.")
        bank.accounts[account_name].withdraw(self.amount)
        self.paid = True