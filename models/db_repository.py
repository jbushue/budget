"""
Database repository for handling CRUD operations and data persistence.
Bridges between the in-memory models and SQLAlchemy ORM.
"""

import json
from sqlalchemy.orm import Session
from models.database import (
    get_session, BankModel, BankAccountModel, CreditAccountModel,
    BillModel, IncomeSourceModel, PromoOfferModel, MortgageAccountModel,
    MortgagePaymentModel
)
from models.bank import Bank
from models.bank_account import BankAccount, AccountType
from models.credit_card_account import CreditAccount, PromoOffer
from models.mortgage_account import MortgageAccount, EscrowBreakdown
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource


class DatabaseRepository:
    """Handles all database operations for the financial system."""

    def __init__(self):
        self.session: Session = get_session()

    def close(self):
        """Close the database session."""
        self.session.close()

    # ==================== Bank Operations ====================

    def save_bank(self, bank: Bank) -> BankModel:
        """Save a bank to the database."""
        # Check if bank already exists
        db_bank = self.session.query(BankModel).filter(BankModel.name == bank.name).first()

        if db_bank:
            # Update existing bank
            db_bank.bank_type = bank.bank_type
            self.session.commit()
        else:
            # Create new bank
            db_bank = BankModel(
                name=bank.name,
                bank_type=bank.bank_type
            )
            self.session.add(db_bank)
            self.session.commit()

        # Save all accounts
        for account in bank.get_all_accounts():
            self.save_bank_account(account, db_bank.id)

        for credit_account in bank.get_all_credit_accounts():
            self.save_credit_account(credit_account, db_bank.id)

        # Save all mortgage accounts
        for mortgage_account in bank.get_all_mortgage_accounts():
            self.save_mortgage_account(mortgage_account, db_bank.id)

        return db_bank

    def load_banks(self) -> list[Bank]:
        """Load all banks from the database."""
        db_banks = self.session.query(BankModel).all()
        banks = []

        for db_bank in db_banks:
            bank = Bank(db_bank.name, db_bank.bank_type)

            # Load bank accounts
            for db_account in db_bank.bank_accounts:
                account = BankAccount(
                    account_type=db_account.account_type.value,
                    account_name=db_account.account_name,
                    balance=db_account.balance,
                    interest_rate=db_account.interest_rate,
                    interest_accrual_date=db_account.interest_accrual_date
                )
                bank.accounts[db_account.account_name] = account

            # Load credit accounts
            for db_credit in db_bank.credit_accounts:
                credit = CreditAccount(
                    account_name=db_credit.account_name,
                    credit_limit=db_credit.credit_limit,
                    interest_rate=db_credit.interest_rate,
                    payment_due_date=db_credit.payment_due_date,
                    statement_date=db_credit.statement_date,
                    status=db_credit.status.value
                )
                credit.balance = db_credit.balance
                credit.regular_balance = db_credit.regular_balance

                # Load promotional offers
                for db_promo in db_credit.promos:
                    promo = PromoOffer(
                        promo_name=db_promo.promo_name,
                        months_interest_free=db_promo.months_interest_free,
                        purchase_limit=db_promo.purchase_limit,
                        start_date=db_promo.start_date
                    )
                    promo.is_active = db_promo.is_active
                    promo.interest_charged = db_promo.interest_charged
                    promo.amount_used = db_promo.amount_used
                    credit.active_promos.append(promo)

                bank.credit_accounts[db_credit.account_name] = credit

            # Load mortgage accounts
            for db_mortgage in db_bank.mortgage_accounts:
                escrow = EscrowBreakdown(
                    property_tax_monthly=db_mortgage.escrow_property_tax,
                    homeowners_insurance_monthly=db_mortgage.escrow_insurance,
                    pmi_monthly=db_mortgage.escrow_pmi,
                    hoa_monthly=db_mortgage.escrow_hoa,
                    other_monthly=db_mortgage.escrow_other
                )
                mortgage = MortgageAccount(
                    account_name=db_mortgage.account_name,
                    original_principal=db_mortgage.original_principal,
                    current_principal=db_mortgage.current_principal,
                    interest_rate=db_mortgage.interest_rate,
                    loan_term_months=db_mortgage.loan_term_months,
                    payment_due_date=db_mortgage.payment_due_date,
                    start_date=db_mortgage.start_date,
                    escrow=escrow,
                    preferred_source_bank=db_mortgage.preferred_source_bank,
                    preferred_source_account=db_mortgage.preferred_source_account
                )
                mortgage.escrow_balance = db_mortgage.escrow_balance
                bank.mortgage_accounts[db_mortgage.account_name] = mortgage

            banks.append(bank)

        return banks

    def save_bank_account(self, account: BankAccount, bank_id: int) -> BankAccountModel:
        """Save a bank account to the database."""
        db_account = self.session.query(BankAccountModel).filter(
            BankAccountModel.account_name == account.account_name,
            BankAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.balance = account.balance
            db_account.interest_rate = account.interest_rate
            db_account.interest_accrual_date = account.interest_accrual_date
        else:
            db_account = BankAccountModel(
                bank_id=bank_id,
                account_name=account.account_name,
                account_type=AccountType[account.account_type.name],
                balance=account.balance,
                interest_rate=account.interest_rate,
                interest_accrual_date=account.interest_accrual_date
            )
            self.session.add(db_account)

        self.session.commit()
        return db_account

    def save_credit_account(self, account: CreditAccount, bank_id: int) -> CreditAccountModel:
        """Save a credit account to the database."""
        db_account = self.session.query(CreditAccountModel).filter(
            CreditAccountModel.account_name == account.account_name,
            CreditAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.balance = account.balance
            db_account.regular_balance = account.regular_balance
            db_account.interest_rate = account.interest_rate
        else:
            db_account = CreditAccountModel(
                bank_id=bank_id,
                account_name=account.account_name,
                credit_limit=account.credit_limit,
                balance=account.balance,
                regular_balance=account.regular_balance,
                interest_rate=account.interest_rate,
                payment_due_date=account.payment_due_date,
                statement_date=account.statement_date
            )
            self.session.add(db_account)

        self.session.commit()
        return db_account

    def save_mortgage_account(self, account: MortgageAccount, bank_id: int) -> MortgageAccountModel:
        """Save a mortgage account to the database."""
        db_account = self.session.query(MortgageAccountModel).filter(
            MortgageAccountModel.account_name == account.account_name,
            MortgageAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.current_principal = account.current_principal
            db_account.interest_rate = account.interest_rate
            db_account.escrow_property_tax = account.escrow.property_tax_monthly
            db_account.escrow_insurance = account.escrow.homeowners_insurance_monthly
            db_account.escrow_pmi = account.escrow.pmi_monthly
            db_account.escrow_hoa = account.escrow.hoa_monthly
            db_account.escrow_other = account.escrow.other_monthly
            db_account.escrow_balance = account.escrow_balance
            db_account.preferred_source_bank = account.preferred_source_bank
            db_account.preferred_source_account = account.preferred_source_account
        else:
            db_account = MortgageAccountModel(
                bank_id=bank_id,
                account_name=account.account_name,
                original_principal=account.original_principal,
                current_principal=account.current_principal,
                interest_rate=account.interest_rate,
                loan_term_months=account.loan_term_months,
                payment_due_date=account.payment_due_date,
                start_date=account.start_date,
                escrow_property_tax=account.escrow.property_tax_monthly,
                escrow_insurance=account.escrow.homeowners_insurance_monthly,
                escrow_pmi=account.escrow.pmi_monthly,
                escrow_hoa=account.escrow.hoa_monthly,
                escrow_other=account.escrow.other_monthly,
                escrow_balance=account.escrow_balance,
                preferred_source_bank=account.preferred_source_bank,
                preferred_source_account=account.preferred_source_account
            )
            self.session.add(db_account)

        self.session.commit()
        return db_account

    # ==================== Bill Operations ====================

    def save_bill(self, bill: Bill) -> BillModel:
        """Save a bill to the database."""
        db_bill = self.session.query(BillModel).filter(BillModel.bill_name == bill.bill_name).first()

        if db_bill:
            db_bill.amount = bill.amount
            db_bill.due_date = bill.due_date
            db_bill.bill_type = bill.bill_type
            db_bill.frequency = bill.frequency
            db_bill.preferred_source_bank = bill.preferred_source_bank
            db_bill.preferred_source_account = bill.preferred_source_account
            db_bill.is_paid_this_period = bill.is_paid_this_period
        else:
            kwargs = {
                'bill_name': bill.bill_name,
                'amount': bill.amount,
                'due_date': bill.due_date,
                'bill_type': bill.bill_type,
                'frequency': bill.frequency,
                'preferred_source_bank': bill.preferred_source_bank,
                'preferred_source_account': bill.preferred_source_account,
                'is_paid_this_period': bill.is_paid_this_period
            }

            # Add floating bill specifics if applicable
            if isinstance(bill, FloatingBill):
                kwargs['min_amount'] = bill.min_amount
                kwargs['max_amount'] = bill.max_amount

            db_bill = BillModel(**kwargs)
            self.session.add(db_bill)

        self.session.commit()
        return db_bill

    def load_bills(self) -> list[Bill]:
        """Load all bills from the database."""
        db_bills = self.session.query(BillModel).all()
        bills = []

        for db_bill in db_bills:
            if db_bill.bill_type.value == "floating":
                bill = FloatingBill(
                    bill_name=db_bill.bill_name,
                    estimated_amount=db_bill.amount,
                    due_date=db_bill.due_date,
                    min_amount=db_bill.min_amount,
                    max_amount=db_bill.max_amount,
                    frequency=db_bill.frequency.value,
                    preferred_source_bank=db_bill.preferred_source_bank,
                    preferred_source_account=db_bill.preferred_source_account
                )
            else:
                bill = Bill(
                    bill_name=db_bill.bill_name,
                    amount=db_bill.amount,
                    due_date=db_bill.due_date,
                    bill_type=db_bill.bill_type.value,
                    frequency=db_bill.frequency.value,
                    preferred_source_bank=db_bill.preferred_source_bank,
                    preferred_source_account=db_bill.preferred_source_account
                )

            bill.is_paid_this_period = db_bill.is_paid_this_period
            bills.append(bill)

        return bills

    # ==================== Income Operations ====================

    def save_income_source(self, income: IncomeSource) -> IncomeSourceModel:
        """Save an income source to the database."""
        db_income = self.session.query(IncomeSourceModel).filter(
            IncomeSourceModel.source_name == income.source_name
        ).first()

        # Convert distribution dict to JSON string
        distribution_json = json.dumps(income.distribution) if income.distribution else None

        if db_income:
            db_income.amount = income.amount
            db_income.frequency = income.frequency
            db_income.pay_date = income.pay_date
            db_income.distribution = distribution_json
        else:
            db_income = IncomeSourceModel(
                source_name=income.source_name,
                amount=income.amount,
                frequency=income.frequency,
                pay_date=income.pay_date,
                distribution=distribution_json
            )
            self.session.add(db_income)

        self.session.commit()
        return db_income

    def load_income_sources(self) -> list[IncomeSource]:
        """Load all income sources from the database."""
        db_incomes = self.session.query(IncomeSourceModel).all()
        incomes = []

        for db_income in db_incomes:
            # Parse distribution JSON
            distribution = json.loads(db_income.distribution) if db_income.distribution else {}
            
            # Parse pay_date JSON (supports both list format and legacy integer format)
            pay_date = None
            if db_income.pay_date:
                try:
                    pay_date = json.loads(db_income.pay_date)
                    # Ensure it's a list
                    if isinstance(pay_date, int):
                        pay_date = [pay_date]
                except (json.JSONDecodeError, TypeError):
                    # Handle legacy integer format stored as string
                    try:
                        pay_date = [int(db_income.pay_date)]
                    except ValueError:
                        pay_date = None

            income = IncomeSource(
                source_name=db_income.source_name,
                amount=db_income.amount,
                frequency=db_income.frequency.value,
                pay_date=pay_date,
                distribution=distribution
            )
            incomes.append(income)

        return incomes

    # ==================== Promotional Offer Operations ====================

    def save_promo(self, credit_account_id: int, promo: PromoOffer) -> PromoOfferModel:
        """Save a promotional offer to the database."""
        db_promo = self.session.query(PromoOfferModel).filter(
            PromoOfferModel.credit_account_id == credit_account_id,
            PromoOfferModel.promo_name == promo.promo_name
        ).first()

        if db_promo:
            db_promo.amount_used = promo.amount_used
            db_promo.is_active = promo.is_active
            db_promo.interest_charged = promo.interest_charged
        else:
            db_promo = PromoOfferModel(
                credit_account_id=credit_account_id,
                promo_name=promo.promo_name,
                months_interest_free=promo.months_interest_free,
                purchase_limit=promo.purchase_limit,
                amount_used=promo.amount_used,
                start_date=promo.start_date,
                end_date=promo.end_date,
                is_active=promo.is_active,
                interest_charged=promo.interest_charged
            )
            self.session.add(db_promo)

        self.session.commit()
        return db_promo

    # ==================== Utility Methods ====================

    def get_bank_by_name(self, bank_name: str) -> BankModel:
        """Get a bank by name."""
        return self.session.query(BankModel).filter(BankModel.name == bank_name).first()

    def export_data(self) -> dict:
        """Export all data as a dictionary (useful for backups)."""
        return {
            "banks": [db_bank.id for db_bank in self.session.query(BankModel).all()],
            "accounts": len(self.session.query(BankAccountModel).all()),
            "credit_accounts": len(self.session.query(CreditAccountModel).all()),
            "bills": len(self.session.query(BillModel).all()),
            "income_sources": len(self.session.query(IncomeSourceModel).all()),
        }

