from datetime import date
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import FixedBill
from models.income_source import IncomeSource

class FinanceManager:
    def __init__(self, banks: list[Bank], income_sources: list[IncomeSource], bills: list[FixedBill]):
        self.banks = banks
        self.income_sources = income_sources
        self.bills = bills

    def get_best_account_for_payment(self, amount: float) -> tuple[Bank, str]:
        candidates = []
        for bank in self.banks:
            for name, acc in bank.accounts.items():
                if acc.balance >= amount:
                    candidates.append((bank, name, acc.balance))
        if not candidates:
            raise ValueError("No account has sufficient funds for this payment.")
        best = max(candidates, key=lambda x: x[2])
        return best[0], best[1]

    def pay_due_bills(self, today: date = date.today()) -> None:
        for bill in sorted(self.bills, key=lambda b: b.due_date):
            if not bill.paid and bill.due_date <= today:
                bank, account_name = self.get_best_account_for_payment(bill.amount)
                bill.pay_from_account(bank, account_name)

    def pay_due_credit_accounts(self, today: date = date.today()) -> None:
        for bank in self.banks:
            for credit in getattr(bank, "credit_accounts", []):
                if hasattr(credit, "payment_due_date") and hasattr(credit, "minimum_payment"):
                    if credit.payment_due_date <= today and credit.balance > 0:
                        bank_for_payment, account_name = self.get_best_account_for_payment(credit.minimum_payment)
                        credit.make_payment(credit.minimum_payment, account_name, bank_for_payment)

    def deposit_all_income(self) -> None:
        for income in self.income_sources:
            # Deposit to the first account of the first bank by default
            bank = self.banks[0]
            account_name = getattr(income, "preferred_account", None) or next(iter(bank.accounts))
            income.deposit_to_account(bank, account_name)

    def generate_report(self, report_date: date) -> str:
        banks = deepcopy(self.banks)
        bills = deepcopy(self.bills)
        income_sources = deepcopy(self.income_sources)

        for income in income_sources:
            bank = banks[0]
            account_name = getattr(income, "preferred_account", None) or next(iter(bank.accounts))
            income.deposit_to_account(bank, account_name)

        for bill in sorted(bills, key=lambda b: b.due_date):
            if not bill.paid and bill.due_date <= report_date:
                try:
                    bank, account_name = self.get_best_account_for_payment(bill.amount)
                    bill.pay_from_account(bank, account_name)
                except Exception:
                    pass

        for bank in banks:
            for credit in getattr(bank, "credit_accounts", []):
                if hasattr(credit, "payment_due_date") and hasattr(credit, "minimum_payment"):
                    if credit.payment_due_date <= report_date and credit.balance > 0:
                        try:
                            bank_for_payment, account_name = self.get_best_account_for_payment(credit.minimum_payment)
                            credit.make_payment(credit.minimum_payment, account_name, bank_for_payment)
                        except Exception:
                            pass
                if hasattr(credit, "accrue_interest_if_due"):
                    credit.accrue_interest_if_due(report_date)

        report_lines = []
        report_lines.append(f"=== Finance Report as of {report_date} ===\n")

        for bank in banks:
            report_lines.append(f"Bank: {getattr(bank, 'name', 'Unnamed Bank')}")
            for name, acc in bank.accounts.items():
                report_lines.append(f"  - {name}: Balance = {acc.balance:.2f}")

        report_lines.append("\nBills:")
        for bill in bills:
            status = "Paid" if bill.paid else "Unpaid"
            report_lines.append(
                f"  - {bill.bill_name}: Amount = {bill.amount:.2f}, Due = {bill.due_date}, Status = {status}, Destination = {bill.destination_account}"
            )

        report_lines.append("\nCredit Accounts:")
        for bank in banks:
            for credit in getattr(bank, "credit_accounts", []):
                due_date = getattr(credit, "payment_due_date", "N/A")
                min_payment = getattr(credit, "minimum_payment", "N/A")
                report_lines.append(
                    f"  - {credit.account_name} (Bank: {getattr(bank, 'name', 'Unnamed Bank')}): Balance = {credit.balance:.2f}, Payment Due = {due_date}, Minimum Payment = {min_payment}"
                )

        report_lines.append("\nIncome Sources:")
        for income in income_sources:
            report_lines.append(
                f"  - {income.source_name}: Amount = {income.amount:.2f}, Frequency = {income.frequency}"
            )

        return "\n".join(report_lines)