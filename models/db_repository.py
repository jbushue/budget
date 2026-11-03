"""
Database repository for handling CRUD operations and data persistence.
Bridges between the in-memory models and SQLAlchemy ORM.
"""

import json
from sqlalchemy.orm import Session
from models.database import (
    local_date,
    get_session, BankModel, BankAccountModel, CreditAccountModel,
    BillModel, IncomeSourceModel, PromoOfferModel, MortgageAccountModel,
    MortgagePaymentModel, BillGroupModel, BillGroupMemberModel,
    HELOCAccountModel, BillPaymentModel
)
from models.bank import Bank
from models.bank_account import BankAccount, AccountType
from models.credit_card_account import CreditAccount, PromoOffer
from models.mortgage_account import MortgageAccount, EscrowBreakdown
from models.heloc_account import HELOCAccount
from models.fixed_bill import Bill, FloatingBill, AccountLinkedBill, GroupLinkedBill
from models.income_source import IncomeSource
from models.bill_group import BillGroup, BillGroupMember
from models.types import AllocationMethod
from models import occurrences as occ



def _as_day(value):
    return occ._as_date(value)


def _day(entry: dict):
    from datetime import date as date_type
    return occ.paid_on(entry) or date_type.today()


def _dates_json(dates) -> str | None:
    return json.dumps(sorted(d.isoformat() for d in dates)) if dates else None


def _dates_from(text) -> set:
    try:
        return {d for d in (occ._as_date(x) for x in json.loads(text or "[]")) if d}
    except (ValueError, TypeError):
        return set()


def _amounts_json(amounts: dict) -> str | None:
    return json.dumps({d.isoformat(): v for d, v in amounts.items()}) if amounts else None


def _amounts_from(text) -> dict:
    try:
        return {occ._as_date(k): float(v) for k, v in json.loads(text or "{}").items() if occ._as_date(k)}
    except (ValueError, TypeError, AttributeError):
        return {}


def _log_json(entries: list[dict]) -> str | None:
    def plain(v):
        return v.isoformat() if hasattr(v, "isoformat") else v
    return json.dumps([{k: plain(v) for k, v in e.items()} for e in entries]) if entries else None


def _log_from(text) -> list[dict]:
    try:
        entries = json.loads(text or "[]")
    except (ValueError, TypeError):
        return []
    for e in entries:
        for k in ("date", "due"):
            if e.get(k):
                e[k] = occ._as_date(e[k])
    return entries


def _min_rule_to_db(account) -> str | None:
    from models.min_payment import normalize
    rule = normalize(getattr(account, "min_rule", None))
    return json.dumps(rule) if rule else None


def _min_rule_from_db(text) -> dict | None:
    from models.min_payment import normalize
    try:
        return normalize(json.loads(text)) if text else None
    except (TypeError, ValueError):
        return None


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

        # Save all HELOC accounts
        for heloc_account in bank.get_all_heloc_accounts():
            self.save_heloc_account(heloc_account, db_bank.id)

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
                    interest_accrual_date=db_account.interest_accrual_date,
                    refill_amount=db_account.refill_amount or 0.0,
                    refill_day=db_account.refill_day,
                    weekly_spending=db_account.weekly_spending or 0.0,
                    offsets_everyday=bool(db_account.offsets_everyday),
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
                credit.min_rule = _min_rule_from_db(db_credit.min_rule)

                # Load promotional offers
                for db_promo in db_credit.promos:
                    promo = PromoOffer(
                        promo_name=db_promo.promo_name,
                        months_interest_free=db_promo.months_interest_free,
                        purchase_limit=db_promo.purchase_limit,
                        start_date=db_promo.start_date,
                        end_date=db_promo.end_date
                    )
                    promo.interest_charged = db_promo.interest_charged
                    promo.amount_used = db_promo.amount_used
                    credit.active_promos.append(promo)
                    credit.promo_balance[db_promo.promo_name] = db_promo.promo_balance

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
                    preferred_source_account=db_mortgage.preferred_source_account,
                    market_value=getattr(db_mortgage, 'market_value', None),
                )
                mortgage.escrow_balance = db_mortgage.escrow_balance
                if db_mortgage.status is not None:
                    mortgage.status = db_mortgage.status
                bank.mortgage_accounts[db_mortgage.account_name] = mortgage

            # Load HELOC accounts
            for db_heloc in db_bank.heloc_accounts:
                from datetime import date as date_type
                start = db_heloc.start_date
                if isinstance(start, str):
                    start = date_type.fromisoformat(start)
                heloc = HELOCAccount(
                    account_name=db_heloc.account_name,
                    credit_limit=db_heloc.credit_limit,
                    interest_rate=db_heloc.interest_rate,
                    draw_period_months=db_heloc.draw_period_months,
                    total_term_months=db_heloc.total_term_months,
                    start_date=start,
                    current_balance=db_heloc.balance,
                    payment_due_date=db_heloc.payment_due_date or 1,
                    preferred_source_bank=db_heloc.preferred_source_bank,
                    preferred_source_account=db_heloc.preferred_source_account,
                )
                bank.heloc_accounts[db_heloc.account_name] = heloc

            banks.append(bank)

        return banks

    def save_bank_account(self, account: BankAccount, bank_id: int) -> BankAccountModel:
        """Save a bank account to the database."""
        db_account = self.session.query(BankAccountModel).filter(
            BankAccountModel.account_name == account.account_name,
            BankAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.account_type = AccountType[account.account_type.name]
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
        db_account.refill_amount = getattr(account, "refill_amount", 0.0) or 0.0
        db_account.refill_day = getattr(account, "refill_day", None)
        db_account.weekly_spending = getattr(account, "weekly_spending", 0.0) or 0.0
        db_account.offsets_everyday = bool(getattr(account, "offsets_everyday", False))

        self.session.commit()
        return db_account

    def save_credit_account(self, account: CreditAccount, bank_id: int) -> CreditAccountModel:
        """Save a credit account to the database."""
        db_account = self.session.query(CreditAccountModel).filter(
            CreditAccountModel.account_name == account.account_name,
            CreditAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.credit_limit = account.credit_limit
            db_account.balance = account.balance
            db_account.regular_balance = account.regular_balance
            db_account.interest_rate = account.interest_rate
            db_account.payment_due_date = account.payment_due_date
            db_account.statement_date = account.statement_date
            db_account.min_rule = _min_rule_to_db(account)
            db_account.status = account.status
        else:
            db_account = CreditAccountModel(
                bank_id=bank_id,
                account_name=account.account_name,
                credit_limit=account.credit_limit,
                balance=account.balance,
                regular_balance=account.regular_balance,
                interest_rate=account.interest_rate,
                payment_due_date=account.payment_due_date,
                statement_date=account.statement_date,
                min_rule=_min_rule_to_db(account),
                status=account.status,
            )
            self.session.add(db_account)

        self.session.commit()

        # Save all promotional offers for this credit account
        existing_promo_names = set()
        for promo in account.active_promos:
            self.save_promo(db_account.id, promo, account.promo_balance.get(promo.promo_name, 0.0))
            existing_promo_names.add(promo.promo_name)

        # Remove promos from DB that are no longer on the in-memory account
        for db_promo in self.session.query(PromoOfferModel).filter(
            PromoOfferModel.credit_account_id == db_account.id
        ).all():
            if db_promo.promo_name not in existing_promo_names:
                self.session.delete(db_promo)
        self.session.commit()

        return db_account

    def save_mortgage_account(self, account: MortgageAccount, bank_id: int) -> MortgageAccountModel:
        """Save a mortgage account to the database."""
        db_account = self.session.query(MortgageAccountModel).filter(
            MortgageAccountModel.account_name == account.account_name,
            MortgageAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.original_principal = account.original_principal
            db_account.current_principal = account.current_principal
            db_account.interest_rate = account.interest_rate
            db_account.loan_term_months = account.loan_term_months
            db_account.payment_due_date = account.payment_due_date
            db_account.start_date = account.start_date
            db_account.status = account.status
            db_account.escrow_property_tax = account.escrow.property_tax_monthly
            db_account.escrow_insurance = account.escrow.homeowners_insurance_monthly
            db_account.escrow_pmi = account.escrow.pmi_monthly
            db_account.escrow_hoa = account.escrow.hoa_monthly
            db_account.escrow_other = account.escrow.other_monthly
            db_account.escrow_balance = account.escrow_balance
            db_account.preferred_source_bank = account.preferred_source_bank
            db_account.preferred_source_account = account.preferred_source_account
            db_account.market_value = account.market_value
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
                preferred_source_account=account.preferred_source_account,
                market_value=account.market_value,
                status=account.status,
            )
            self.session.add(db_account)

        self.session.commit()
        return db_account

    def save_heloc_account(self, account: HELOCAccount, bank_id: int) -> HELOCAccountModel:
        """Save a HELOC account to the database."""
        db_account = self.session.query(HELOCAccountModel).filter(
            HELOCAccountModel.account_name == account.account_name,
            HELOCAccountModel.bank_id == bank_id
        ).first()

        if db_account:
            db_account.balance = account.balance
            db_account.interest_rate = account.interest_rate
            db_account.credit_limit = account.credit_limit
            db_account.draw_period_months = account.draw_period_months
            db_account.total_term_months = account.total_term_months
            db_account.start_date = account.start_date
            db_account.payment_due_date = account.payment_due_date
            db_account.preferred_source_bank = account.preferred_source_bank
            db_account.preferred_source_account = account.preferred_source_account
        else:
            db_account = HELOCAccountModel(
                bank_id=bank_id,
                account_name=account.account_name,
                credit_limit=account.credit_limit,
                balance=account.balance,
                interest_rate=account.interest_rate,
                draw_period_months=account.draw_period_months,
                total_term_months=account.total_term_months,
                start_date=account.start_date,
                payment_due_date=account.payment_due_date,
                preferred_source_bank=account.preferred_source_bank,
                preferred_source_account=account.preferred_source_account,
            )
            self.session.add(db_account)

        self.session.commit()
        return db_account

    # ==================== Bill Operations ====================

    def save_bill(self, bill: Bill) -> BillModel:
        """Save a bill to the database. GroupLinkedBill instances are skipped
        because they are auto-created from BillGroup data."""
        # GroupLinkedBill is auto-created from bill group data — don't persist separately
        if isinstance(bill, GroupLinkedBill):
            return None

        db_bill = self._find_bill_row(bill)

        if db_bill:
            db_bill.bill_name = bill.bill_name
            db_bill.amount = bill.amount
            db_bill.due_date = bill.due_date
            db_bill.due_month = getattr(bill, 'due_month', None)
            db_bill.bill_type = bill.bill_type
            db_bill.frequency = bill.frequency
            db_bill.preferred_source_bank = bill.preferred_source_bank
            db_bill.preferred_source_account = bill.preferred_source_account
            # Paid status is per due date now (payments, skips); the old flag stays False
            db_bill.is_paid_this_period = False
            db_bill.carryover_balance = 0.0
            db_bill.start_date = getattr(bill, 'start_date', None)
            db_bill.late_fee = getattr(bill, 'late_fee', None)
            db_bill.skipped_dates = _dates_json(getattr(bill, 'skipped', None))
            db_bill.tracked_from = getattr(bill, 'tracked_from', None)

            # Update floating bill fields
            if isinstance(bill, FloatingBill):
                db_bill.min_amount = bill.min_amount
                db_bill.max_amount = bill.max_amount
                db_bill.estimated_amount = bill.estimated_amount
                db_bill.actual_amount = None
                db_bill.actual_amounts = _amounts_json(bill.actual_amounts)
                db_bill.amount_history = json.dumps(bill.amount_history) if bill.amount_history else None

            # Update linked bill fields
            if isinstance(bill, AccountLinkedBill):
                db_bill.linked_bank_name = bill.linked_bank_name
                db_bill.linked_account_name = bill.linked_account.account_name
                db_bill.linked_account_type = bill.linked_account_type
        else:
            kwargs = {
                'bill_name': bill.bill_name,
                'amount': bill.amount,
                'due_date': bill.due_date,
                'due_month': getattr(bill, 'due_month', None),
                'bill_type': bill.bill_type,
                'frequency': bill.frequency,
                'preferred_source_bank': bill.preferred_source_bank,
                'preferred_source_account': bill.preferred_source_account,
                'is_paid_this_period': False,
                'carryover_balance': 0.0,
                'start_date': getattr(bill, 'start_date', None),
                'late_fee': getattr(bill, 'late_fee', None),
                'skipped_dates': _dates_json(getattr(bill, 'skipped', None)),
                'tracked_from': getattr(bill, 'tracked_from', None),
            }

            # Add floating bill specifics if applicable
            if isinstance(bill, FloatingBill):
                kwargs['min_amount'] = bill.min_amount
                kwargs['max_amount'] = bill.max_amount
                kwargs['estimated_amount'] = bill.estimated_amount
                kwargs['actual_amounts'] = _amounts_json(bill.actual_amounts)
                kwargs['amount_history'] = json.dumps(bill.amount_history) if bill.amount_history else None

            # Add linked bill specifics if applicable
            if isinstance(bill, AccountLinkedBill):
                kwargs['linked_bank_name'] = bill.linked_bank_name
                kwargs['linked_account_name'] = bill.linked_account.account_name
                kwargs['linked_account_type'] = bill.linked_account_type

            db_bill = BillModel(**kwargs)
            self.session.add(db_bill)

        self.session.flush()
        self._sync_bill_payments(db_bill, bill)
        self.session.commit()
        return db_bill

    def _find_bill_row(self, bill: Bill):
        """Find the DB row for a bill. Account-linked bills are keyed by their
        linked account (names can collide across banks); others by name."""
        query = self.session.query(BillModel)
        if isinstance(bill, AccountLinkedBill):
            return query.filter(
                BillModel.linked_account_type == bill.linked_account_type,
                BillModel.linked_bank_name == bill.linked_bank_name,
                BillModel.linked_account_name == bill.linked_account.account_name,
            ).first()
        return query.filter(
            BillModel.bill_name == bill.bill_name,
            BillModel.linked_account_name.is_(None),
        ).first()

    def _sync_bill_payments(self, db_bill: BillModel, bill: Bill):
        """
        Make the DB rows match the bill's payment history. Usually that's just
        appending new payments; if one was removed or changed (e.g. a match
        undone), the rows are rewritten so the change sticks.
        """
        def sig(paid_on, amount, due):
            # Not the source: renaming an account rewrites the source columns in SQL
            return (paid_on, round(float(amount or 0.0), 2), due)

        rows = sorted(db_bill.payments, key=lambda r: r.id or 0)
        in_db = [sig(r.payment_date, r.amount_paid, r.due_date) for r in rows]
        wanted = [sig(_day(e), e.get('amount_paid'), occ.due_of(e)) for e in bill.payment_history]
        if wanted[:len(in_db)] == in_db:
            new_entries = bill.payment_history[len(in_db):]
        else:
            for r in rows:
                self.session.delete(r)
            self.session.flush()
            new_entries = bill.payment_history
        for entry in new_entries:
            self.session.add(BillPaymentModel(
                bill_id=db_bill.id,
                amount_paid=entry.get('amount_paid') or 0.0,
                source_bank=entry.get('source_bank') or '',
                source_account=entry.get('source_account') or '',
                payment_date=_day(entry),
                due_date=occ.due_of(entry),
                owed=entry.get('owed'),
                moved_money=entry.get('moved_money'),
            ))

    @staticmethod
    def _payment_history_from_db(db_bill: BillModel) -> list[dict]:
        """Rebuild a bill's in-memory payment history from its DB rows."""
        return [
            {
                "date": p.payment_date,
                "source_bank": p.source_bank,
                "source_account": p.source_account,
                "amount_paid": p.amount_paid,
                "due": p.due_date,
                "owed": p.owed,
                "moved_money": p.moved_money,
            }
            for p in sorted(db_bill.payments, key=lambda p: (p.payment_date, p.id))
        ]

    @staticmethod
    def _restore_paid_state(bill: Bill, db_bill: BillModel):
        """Payments, skips and tracking start; older data gets due dates filled in."""
        bill.payment_history = DatabaseRepository._payment_history_from_db(db_bill)
        bill.skipped = _dates_from(getattr(db_bill, 'skipped_dates', None))
        bill.tracked_from = getattr(db_bill, 'tracked_from', None)
        bill.start_date = db_bill.start_date
        bill.late_fee = getattr(db_bill, 'late_fee', None)
        if db_bill.created_at:
            bill.created_on = local_date(db_bill.created_at)
        occ.pin_anchor(bill)
        occ.assign_legacy(bill)
        # The old "paid this period" flag with no payment behind it: skip that due date
        # (linked bills do this once their real account is connected)
        bill._legacy_paid = bool(db_bill.is_paid_this_period) and not bill.payment_history

    @staticmethod
    def _apply_legacy_flag(bill):
        if bill.__dict__.pop('_legacy_paid', False):
            bill.is_paid_this_period = True

    def load_bills(self) -> list[Bill]:
        """Load all bills from the database."""
        db_bills = self.session.query(BillModel).all()
        bills = []

        for db_bill in db_bills:
            # Skip group_payment bills — they are auto-created from BillGroup data
            if db_bill.bill_type.value == "group_payment":
                continue

            linked_bank = getattr(db_bill, 'linked_bank_name', None)
            linked_acct = getattr(db_bill, 'linked_account_name', None)
            linked_type = getattr(db_bill, 'linked_account_type', None)

            if linked_bank and linked_acct and linked_type:
                # This is an AccountLinkedBill — create a placeholder that will
                # be reconnected to the actual account by _rebuild_linked_bills()
                # in FinanceManager.load_from_database()
                from models.types import BillType as BT
                bt_map = {
                    'credit': BT.CREDIT_PAYMENT,
                    'mortgage': BT.MORTGAGE_PAYMENT,
                    'heloc': BT.HELOC_PAYMENT,
                }
                # Create a stub linked bill with a dummy account
                # The real account gets reconnected in _rebuild_linked_bills
                class _StubAccount:
                    def __init__(self, name, due_date, balance, acct_type):
                        self.account_name = name
                        self.payment_due_date = due_date
                        self.balance = balance
                        self.current_principal = balance
                        self.preferred_source_bank = None
                        self.preferred_source_account = None
                        self.is_paid_this_period = False
                    def calculate_minimum_payment(self):
                        return 0.0
                    @property
                    def total_monthly_payment(self):
                        return 0.0

                stub = _StubAccount(linked_acct, db_bill.due_date, 0, linked_type)
                bill = AccountLinkedBill(
                    linked_account=stub,
                    linked_bank_name=linked_bank,
                    linked_account_type=linked_type,
                    bill_type=bt_map.get(linked_type, BT.CREDIT_PAYMENT),
                    preferred_source_bank=db_bill.preferred_source_bank,
                    preferred_source_account=db_bill.preferred_source_account,
                )
                self._restore_paid_state(bill, db_bill)
                bills.append(bill)
            elif db_bill.bill_type.value == "floating":
                # Use stored estimated_amount if available, else fall back to amount
                estimated = db_bill.estimated_amount if db_bill.estimated_amount else db_bill.amount
                bill = FloatingBill(
                    bill_name=db_bill.bill_name,
                    estimated_amount=estimated,
                    due_date=db_bill.due_date,
                    min_amount=db_bill.min_amount,
                    max_amount=db_bill.max_amount,
                    frequency=db_bill.frequency.value,
                    due_month=getattr(db_bill, 'due_month', None),
                    preferred_source_bank=db_bill.preferred_source_bank,
                    preferred_source_account=db_bill.preferred_source_account
                )

                # Restore amount history
                if db_bill.amount_history:
                    try:
                        bill.amount_history = json.loads(db_bill.amount_history)
                    except (json.JSONDecodeError, TypeError):
                        bill.amount_history = []

                self._restore_paid_state(bill, db_bill)
                bill.actual_amounts = _amounts_from(getattr(db_bill, 'actual_amounts', None))
                # An actual amount saved before they were kept per due date
                if db_bill.actual_amount is not None and not bill.actual_amounts:
                    bill.set_actual_amount(db_bill.actual_amount)
                self._apply_legacy_flag(bill)
                bills.append(bill)
            else:
                bill = Bill(
                    bill_name=db_bill.bill_name,
                    amount=db_bill.amount,
                    due_date=db_bill.due_date,
                    bill_type=db_bill.bill_type.value,
                    frequency=db_bill.frequency.value,
                    due_month=getattr(db_bill, 'due_month', None),
                    preferred_source_bank=db_bill.preferred_source_bank,
                    preferred_source_account=db_bill.preferred_source_account
                )

                self._restore_paid_state(bill, db_bill)
                self._apply_legacy_flag(bill)
                bills.append(bill)

        return bills

    # ==================== Income Operations ====================

    def save_income_source(self, income: IncomeSource) -> IncomeSourceModel:
        """Save an income source to the database."""
        db_income = self.session.query(IncomeSourceModel).filter(
            IncomeSourceModel.source_name == income.source_name
        ).first()

        # Convert distribution to JSON string (handle DistributionType object)
        distribution_json = None
        if income.distribution:
            if hasattr(income.distribution, 'to_json'):
                distribution_json = json.dumps(income.distribution.to_json())
            elif hasattr(income.distribution, '__todict__'):
                distribution_json = json.dumps(income.distribution.__todict__())
            elif isinstance(income.distribution, dict):
                distribution_json = json.dumps(income.distribution)
        
        # Convert pay_date list to JSON string
        pay_date_json = json.dumps(income.pay_date) if income.pay_date else None

        if db_income:
            db_income.amount = income.amount
            db_income.frequency = income.frequency
            db_income.pay_date = pay_date_json
            db_income.distribution = distribution_json
            db_income.start_date = getattr(income, 'start_date', None)
        else:
            db_income = IncomeSourceModel(
                source_name=income.source_name,
                amount=income.amount,
                frequency=income.frequency,
                pay_date=pay_date_json,
                distribution=distribution_json,
                start_date=getattr(income, 'start_date', None),
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
            income.start_date = db_income.start_date
            incomes.append(income)

        return incomes

    # ==================== Promotional Offer Operations ====================

    def save_promo(self, credit_account_id: int, promo: PromoOffer, promo_balance: float = 0.0) -> PromoOfferModel:
        """Save a promotional offer to the database."""
        db_promo = self.session.query(PromoOfferModel).filter(
            PromoOfferModel.credit_account_id == credit_account_id,
            PromoOfferModel.promo_name == promo.promo_name
        ).first()

        if db_promo:
            db_promo.months_interest_free = promo.months_interest_free
            db_promo.purchase_limit = promo.purchase_limit
            db_promo.start_date = promo.start_date
            db_promo.end_date = promo.end_date
            db_promo.amount_used = promo.amount_used
            db_promo.promo_balance = promo_balance
            db_promo.is_active = promo.is_active
            db_promo.interest_charged = promo.interest_charged
        else:
            db_promo = PromoOfferModel(
                credit_account_id=credit_account_id,
                promo_name=promo.promo_name,
                months_interest_free=promo.months_interest_free,
                purchase_limit=promo.purchase_limit,
                amount_used=promo.amount_used,
                promo_balance=promo_balance,
                start_date=promo.start_date,
                end_date=promo.end_date,
                is_active=promo.is_active,
                interest_charged=promo.interest_charged
            )
            self.session.add(db_promo)

        self.session.commit()
        return db_promo

    # ==================== Bill Group Operations ====================

    def save_bill_group(self, group: BillGroup) -> BillGroupModel:
        """Save a bill group and its members to the database."""
        db_group = self.session.query(BillGroupModel).filter(
            BillGroupModel.group_name == group.group_name
        ).first()

        if db_group:
            db_group.total_payment = group.total_payment
            db_group.due_date = group.due_date
            db_group.frequency = group.frequency
            db_group.group_type = group.group_type
            db_group.preferred_source_bank = group.preferred_source_bank
            db_group.preferred_source_account = group.preferred_source_account
            db_group.is_paid_this_period = False
            db_group.last_paid_date = _as_day(group.last_paid_date)
            db_group.payment_log = _log_json(group.payment_history)
            db_group.skipped_dates = _dates_json(group.skipped)
            db_group.tracked_from = group.tracked_from
        else:
            db_group = BillGroupModel(
                group_name=group.group_name,
                total_payment=group.total_payment,
                due_date=group.due_date,
                frequency=group.frequency,
                group_type=group.group_type,
                preferred_source_bank=group.preferred_source_bank,
                preferred_source_account=group.preferred_source_account,
                is_paid_this_period=False,
                last_paid_date=_as_day(group.last_paid_date),
                payment_log=_log_json(group.payment_history),
                skipped_dates=_dates_json(group.skipped),
                tracked_from=group.tracked_from,
            )
            self.session.add(db_group)
            self.session.flush()  # get db_group.id

        self.session.commit()

        # Sync members: remove old, upsert current
        existing_members = {
            (m.bank_name, m.account_name): m
            for m in self.session.query(BillGroupMemberModel).filter(
                BillGroupMemberModel.group_id == db_group.id
            ).all()
        }
        current_keys = set()
        for member in group.members:
            key = (member.bank_name, member.account_name)
            current_keys.add(key)
            if key in existing_members:
                db_member = existing_members[key]
                db_member.allocation_method = member.allocation_method
                db_member.fixed_amount = member.fixed_amount
            else:
                db_member = BillGroupMemberModel(
                    group_id=db_group.id,
                    bank_name=member.bank_name,
                    account_name=member.account_name,
                    allocation_method=member.allocation_method,
                    fixed_amount=member.fixed_amount,
                )
                self.session.add(db_member)

        # Delete members no longer in the group
        for key, db_member in existing_members.items():
            if key not in current_keys:
                self.session.delete(db_member)

        self.session.commit()
        return db_group

    def load_bill_groups(self) -> list[BillGroup]:
        """Load all bill groups from the database."""
        db_groups = self.session.query(BillGroupModel).all()
        groups = []

        for db_group in db_groups:
            members = []
            for db_member in db_group.members:
                members.append(BillGroupMember(
                    bank_name=db_member.bank_name,
                    account_name=db_member.account_name,
                    allocation_method=AllocationMethod(db_member.allocation_method.value) if hasattr(db_member.allocation_method, 'value') else AllocationMethod(db_member.allocation_method),
                    fixed_amount=db_member.fixed_amount,
                ))
            group = BillGroup(
                group_name=db_group.group_name,
                total_payment=db_group.total_payment,
                due_date=db_group.due_date,
                frequency=db_group.frequency.value if hasattr(db_group.frequency, 'value') else db_group.frequency,
                group_type=db_group.group_type,
                preferred_source_bank=db_group.preferred_source_bank,
                preferred_source_account=db_group.preferred_source_account,
                members=members,
            )
            if getattr(db_group, 'created_at', None):
                group.created_on = local_date(db_group.created_at)
            group.tracked_from = getattr(db_group, 'tracked_from', None)
            group.skipped = _dates_from(getattr(db_group, 'skipped_dates', None))
            log = getattr(db_group, 'payment_log', None)
            if log:
                group.payment_history = _log_from(log)
            elif db_group.last_paid_date:
                # Saved before group payments were kept: the last one paid in full
                group.payment_history = [{"date": db_group.last_paid_date, "amount_paid": db_group.total_payment}]
            as_bill = group.as_bill()
            occ.assign_legacy(as_bill)
            if db_group.is_paid_this_period and not group.payment_history:
                as_bill.is_paid_this_period = True
            groups.append(group)

        return groups

    def delete_bill_group(self, group_name: str) -> bool:
        """Delete a bill group by name. Returns True if deleted."""
        db_group = self.session.query(BillGroupModel).filter(
            BillGroupModel.group_name == group_name
        ).first()
        if db_group:
            self.session.delete(db_group)
            self.session.commit()
            return True
        return False

    # ==================== Deletion Sync ====================

    def prune_deleted(self, banks: list[Bank], bills: list[Bill],
                      income_sources: list[IncomeSource], bill_groups: list[BillGroup]) -> None:
        """Delete DB rows for objects that no longer exist in memory, so
        deletions survive a restart. Uses ORM deletes so cascades apply."""
        from sqlalchemy import text

        bank_map = {b.name: b for b in banks}
        removed_accounts: list[tuple[str, str]] = []
        for db_bank in self.session.query(BankModel).all():
            bank = bank_map.get(db_bank.name)
            if bank is None:
                for rel in (db_bank.bank_accounts, db_bank.credit_accounts,
                            db_bank.mortgage_accounts, db_bank.heloc_accounts):
                    removed_accounts.extend((db_bank.name, a.account_name) for a in rel)
                self.session.delete(db_bank)
                continue
            for rel, live in ((db_bank.bank_accounts, bank.accounts),
                              (db_bank.credit_accounts, bank.credit_accounts),
                              (db_bank.mortgage_accounts, bank.mortgage_accounts),
                              (db_bank.heloc_accounts, bank.heloc_accounts)):
                for db_acc in list(rel):
                    if db_acc.account_name not in live:
                        removed_accounts.append((db_bank.name, db_acc.account_name))
                        self.session.delete(db_acc)

        plain_names = set()
        linked_keys = set()
        for bill in bills:
            if isinstance(bill, GroupLinkedBill):
                continue
            if isinstance(bill, AccountLinkedBill):
                linked_keys.add((bill.linked_account_type, bill.linked_bank_name,
                                 bill.linked_account.account_name))
            else:
                plain_names.add(bill.bill_name)
        for db_bill in self.session.query(BillModel).all():
            if db_bill.linked_account_name:
                key = (db_bill.linked_account_type, db_bill.linked_bank_name, db_bill.linked_account_name)
                if key not in linked_keys:
                    self.session.delete(db_bill)
            elif db_bill.bill_name not in plain_names:
                self.session.delete(db_bill)

        income_names = {i.source_name for i in income_sources}
        for db_income in self.session.query(IncomeSourceModel).all():
            if db_income.source_name not in income_names:
                self.session.delete(db_income)

        group_names = {g.group_name for g in bill_groups}
        for db_group in self.session.query(BillGroupModel).all():
            if db_group.group_name not in group_names:
                self.session.delete(db_group)

        self.session.commit()

        # SimpleFIN mappings and balance history live in raw-SQL tables keyed by account name
        if removed_accounts:
            tables = set(self.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'")).scalars())
            for bank_name, account_name in removed_accounts:
                params = {"b": bank_name, "a": account_name}
                if "simplefin_account_mappings" in tables:
                    self.session.execute(text(
                        "DELETE FROM simplefin_account_mappings "
                        "WHERE local_bank_name = :b AND local_account_name = :a"
                    ), params)
                if "balance_history" in tables:
                    self.session.execute(text(
                        "DELETE FROM balance_history WHERE bank_name = :b AND account_name = :a"
                    ), params)
            self.session.commit()

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

