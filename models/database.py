"""
Database models and configuration using SQLAlchemy with SQLite.
Provides persistent storage for the financial management system.
"""

from datetime import date, datetime, timezone
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import enum
import os

from models.income_source import IncomeFrequency
from models.types import *

# Create database directory if it doesn't exist (BUDGET_DATA_DIR moves it, e.g. to a Docker volume)
DB_DIR = os.environ.get("BUDGET_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".budget_app")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "finance.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Helper function for timezone-aware datetime
def utc_now():
    return datetime.now(timezone.utc)


def to_local(dt):
    """Local wall-clock time (naive) for a ``utc_now`` timestamp (SQLite hands back naive UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)


def local_date(dt):
    """Calendar date in local time for a stored ``utc_now`` timestamp."""
    return to_local(dt).date()

# Create engine and session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ==================== Enums ====================

AccountTypeEnum = AccountType
BillTypeEnum = BillType
BillFrequencyEnum = BillFrequency
IncomeFrequencyEnum = IncomeFrequency
CreditAccountStatusEnum = CreditAccountStatus
MortgageStatusEnum = MortgageStatus
AllocationMethodEnum = AllocationMethod


# ==================== Database Models ====================

class BankModel(Base):
    """Represents a bank/financial institution."""
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    bank_type = Column(String(50), nullable=False, default="traditional")  # traditional, credit_issuer, mortgage_lender
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    bank_accounts = relationship("BankAccountModel", back_populates="bank", cascade="all, delete-orphan")
    credit_accounts = relationship("CreditAccountModel", back_populates="bank", cascade="all, delete-orphan")
    mortgage_accounts = relationship("MortgageAccountModel", back_populates="bank", cascade="all, delete-orphan")
    heloc_accounts = relationship("HELOCAccountModel", back_populates="bank", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BankModel(id={self.id}, name={self.name})>"


class BankAccountModel(Base):
    """A cash-type account: checking, savings, EBT, HSA, brokerage, ... (models.types.ACCOUNT_KINDS)."""
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    account_type = Column(Enum(AccountTypeEnum), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    interest_rate = Column(Float, nullable=False, default=0.0)  # APR as percentage
    interest_accrual_date = Column(Integer, nullable=True)  # Day of month (1-31)
    refill_amount = Column(Float, nullable=False, default=0.0)   # added each month (EBT benefits, HSA)
    refill_day = Column(Integer, nullable=True)
    weekly_spending = Column(Float, nullable=False, default=0.0)  # spent from it each week
    offsets_everyday = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    bank = relationship("BankModel", back_populates="bank_accounts")
    transactions = relationship("TransactionModel", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BankAccountModel(id={self.id}, name={self.account_name}, balance={self.balance})>"


class CreditAccountModel(Base):
    """Represents a credit card account."""
    __tablename__ = "credit_accounts"

    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    credit_limit = Column(Float, nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    regular_balance = Column(Float, nullable=False, default=0.0)
    interest_rate = Column(Float, nullable=False, default=0.0)  # APR as percentage
    payment_due_date = Column(Integer, nullable=True)  # Day of month (1-31)
    statement_date = Column(Integer, nullable=True)  # Day of month (1-31)
    min_rule = Column(Text, nullable=True)  # JSON: how the minimum payment is worked out (min_payment.py)
    payment_order = Column(String(20), nullable=True)  # regular_first (default) | regular_last: promo balances
    status = Column(Enum(CreditAccountStatusEnum), nullable=False, default=CreditAccountStatusEnum.ACTIVE)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    bank = relationship("BankModel", back_populates="credit_accounts")
    transactions = relationship("CreditTransactionModel", back_populates="account", cascade="all, delete-orphan")
    promos = relationship("PromoOfferModel", back_populates="credit_account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CreditAccountModel(id={self.id}, name={self.account_name}, balance={self.balance})>"


class TransactionModel(Base):
    """Represents a transaction on a bank account."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    trans_type = Column(String(50), nullable=False)  # DEPOSIT, WITHDRAWAL, INTEREST, ADJUSTMENT
    amount = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    transaction_date = Column(Date, nullable=False, default=date.today)
    balance_after = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    account = relationship("BankAccountModel", back_populates="transactions")

    def __repr__(self):
        return f"<TransactionModel(id={self.id}, type={self.trans_type}, amount={self.amount})>"


class CreditTransactionModel(Base):
    """Represents a transaction on a credit account."""
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("credit_accounts.id"), nullable=False)
    trans_type = Column(String(50), nullable=False)  # PURCHASE, PAYMENT, INTEREST, PROMO_INTEREST, ADJUSTMENT
    amount = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    transaction_date = Column(Date, nullable=False, default=date.today)
    balance_after = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    account = relationship("CreditAccountModel", back_populates="transactions")

    def __repr__(self):
        return f"<CreditTransactionModel(id={self.id}, type={self.trans_type}, amount={self.amount})>"


class MortgageAccountModel(Base):
    """Represents a mortgage loan account."""
    __tablename__ = "mortgage_accounts"

    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    original_principal = Column(Float, nullable=False)
    current_principal = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)  # APR as percentage
    loan_term_months = Column(Integer, nullable=False)
    payment_due_date = Column(Integer, nullable=True)  # Day of month (1-31)
    start_date = Column(Date, nullable=True)
    status = Column(Enum(MortgageStatusEnum), nullable=False, default=MortgageStatusEnum.ACTIVE)
    
    # Escrow breakdown (stored as JSON string)
    escrow_property_tax = Column(Float, nullable=False, default=0.0)
    escrow_insurance = Column(Float, nullable=False, default=0.0)
    escrow_pmi = Column(Float, nullable=False, default=0.0)
    escrow_hoa = Column(Float, nullable=False, default=0.0)
    escrow_other = Column(Float, nullable=False, default=0.0)
    escrow_balance = Column(Float, nullable=False, default=0.0)
    
    # Payment source preferences
    preferred_source_bank = Column(String(100), nullable=True)
    preferred_source_account = Column(String(100), nullable=True)
    
    # Property value tracking
    market_value = Column(Float, nullable=True)  # Current market value of the property (or vehicle)

    # Kind of loan and its kind-specific settings (see mortgage_account.py)
    loan_kind = Column(String(20), nullable=False, default="mortgage")
    payment_override = Column(Float, nullable=True)
    value_as_of = Column(Date, nullable=True)
    depreciation_rate = Column(Float, nullable=True)
    payments_start = Column(Date, nullable=True)
    subsidized = Column(Boolean, nullable=False, default=False)
    capitalized = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    bank = relationship("BankModel", back_populates="mortgage_accounts")
    payments = relationship("MortgagePaymentModel", back_populates="mortgage", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MortgageAccountModel(id={self.id}, name={self.account_name}, principal={self.current_principal})>"


class MortgagePaymentModel(Base):
    """Represents a mortgage payment."""
    __tablename__ = "mortgage_payments"

    id = Column(Integer, primary_key=True)
    mortgage_id = Column(Integer, ForeignKey("mortgage_accounts.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    principal_amount = Column(Float, nullable=False)
    interest_amount = Column(Float, nullable=False)
    escrow_amount = Column(Float, nullable=False, default=0.0)
    extra_principal = Column(Float, nullable=False, default=0.0)
    source_bank = Column(String(100), nullable=True)
    source_account = Column(String(100), nullable=True)
    payment_date = Column(Date, nullable=False, default=date.today)
    principal_after = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    mortgage = relationship("MortgageAccountModel", back_populates="payments")

    def __repr__(self):
        return f"<MortgagePaymentModel(id={self.id}, amount={self.total_amount}, date={self.payment_date})>"


class HELOCAccountModel(Base):
    """Represents a HELOC (Home Equity Line of Credit) account."""
    __tablename__ = "heloc_accounts"

    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    credit_limit = Column(Float, nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    interest_rate = Column(Float, nullable=False, default=0.0)  # APR as percentage
    draw_period_months = Column(Integer, nullable=False, default=180)
    total_term_months = Column(Integer, nullable=False, default=360)
    start_date = Column(Date, nullable=True)
    payment_due_date = Column(Integer, nullable=True)  # Day of month (1-31)
    preferred_source_bank = Column(String(100), nullable=True)
    preferred_source_account = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    bank = relationship("BankModel", back_populates="heloc_accounts")

    def __repr__(self):
        return f"<HELOCAccountModel(id={self.id}, name={self.account_name}, balance={self.balance})>"


class BillModel(Base):
    """Represents a bill/recurring expense."""
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True)
    bill_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Integer, nullable=False)  # Day of month (1-31)
    due_month = Column(Integer, nullable=True)  # Month (1-12) for yearly/semi-annual bills
    bill_type = Column(Enum(BillTypeEnum), nullable=False, default=BillTypeEnum.FIXED)
    frequency = Column(Enum(BillFrequencyEnum), nullable=False, default=BillFrequencyEnum.MONTHLY)

    # For floating bills
    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    estimated_amount = Column(Float, nullable=True)  # Base estimate for floating bills
    actual_amount = Column(Float, nullable=True)  # Current actual if set, else None
    amount_history = Column(String(2000), nullable=True)  # JSON list of past actual amounts

    # Payment source preferences
    preferred_source_bank = Column(String(100), nullable=True)
    preferred_source_account = Column(String(100), nullable=True)

    # Status
    is_paid_this_period = Column(Boolean, nullable=False, default=False)
    carryover_balance = Column(Float, nullable=False, default=0.0)  # Underpayment carried forward

    # Account-linked bill fields (for AccountLinkedBill)
    linked_bank_name = Column(String(100), nullable=True)
    linked_account_name = Column(String(100), nullable=True)
    linked_account_type = Column(String(50), nullable=True)  # 'credit', 'mortgage', 'heloc'

    # Schedule anchor for weekly/biweekly/quarterly/etc. bills
    start_date = Column(Date, nullable=True)

    # Fee charged when this bill is paid late (None = use the app-wide default)
    late_fee = Column(Float, nullable=True)

    # Due dates not owed (JSON list of ISO dates), a floating bill's actual
    # amount per due date (JSON {date: amount}), and the first due date that
    # can be overdue (set when paying by due date began)
    skipped_dates = Column(Text, nullable=True)
    actual_amounts = Column(Text, nullable=True)
    tracked_from = Column(Date, nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    payments = relationship("BillPaymentModel", back_populates="bill", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BillModel(id={self.id}, name={self.bill_name}, amount={self.amount})>"


class BillPaymentModel(Base):
    """Represents a payment for a bill."""
    __tablename__ = "bill_payments"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    amount_paid = Column(Float, nullable=False)
    source_bank = Column(String(100), nullable=False)
    source_account = Column(String(100), nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    # The due date this payment is for, what that due date owed, and whether
    # the app moved the money (False = just recorded)
    due_date = Column(Date, nullable=True)
    owed = Column(Float, nullable=True)
    moved_money = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    bill = relationship("BillModel", back_populates="payments")

    def __repr__(self):
        return f"<BillPaymentModel(id={self.id}, amount={self.amount_paid}, date={self.payment_date})>"


class IncomeSourceModel(Base):
    """Represents a source of income."""
    __tablename__ = "income_sources"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    frequency = Column(Enum(IncomeFrequencyEnum), nullable=False, default=IncomeFrequencyEnum.MONTHLY)
    pay_date = Column(String(100), nullable=True)  # JSON list of days: "[1]" or "[15, 31]" for semimonthly
    distribution = Column(String(1000), nullable=True)  # JSON string: {"account": amount}
    start_date = Column(Date, nullable=True)  # Schedule anchor (first pay date) for weekly/biweekly/etc.

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    deposits = relationship("IncomeDepositModel", back_populates="income_source", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<IncomeSourceModel(id={self.id}, name={self.source_name}, amount={self.amount})>"


class IncomeDepositModel(Base):
    """Represents a deposit from an income source."""
    __tablename__ = "income_deposits"

    id = Column(Integer, primary_key=True)
    income_id = Column(Integer, ForeignKey("income_sources.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    deposit_date = Column(Date, nullable=False, default=date.today)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    income_source = relationship("IncomeSourceModel", back_populates="deposits")

    def __repr__(self):
        return f"<IncomeDepositModel(id={self.id}, amount={self.amount}, date={self.deposit_date})>"


class PromoOfferModel(Base):
    """Represents a promotional interest-free offer on a credit card."""
    __tablename__ = "promo_offers"

    id = Column(Integer, primary_key=True)
    credit_account_id = Column(Integer, ForeignKey("credit_accounts.id"), nullable=False)
    promo_name = Column(String(100), nullable=False)
    months_interest_free = Column(Integer, nullable=False)
    purchase_limit = Column(Float, nullable=True)
    amount_used = Column(Float, nullable=False, default=0.0)
    promo_balance = Column(Float, nullable=False, default=0.0)
    start_date = Column(Date, nullable=False, default=date.today)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    interest_charged = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    credit_account = relationship("CreditAccountModel", back_populates="promos")

    def __repr__(self):
        return f"<PromoOfferModel(id={self.id}, name={self.promo_name}, active={self.is_active})>"


class BillGroupModel(Base):
    """Represents a bill group / bundled payment (e.g. student loans)."""
    __tablename__ = "bill_groups"

    id = Column(Integer, primary_key=True)
    group_name = Column(String(100), unique=True, nullable=False)
    total_payment = Column(Float, nullable=False, default=0.0)
    due_date = Column(Integer, nullable=False)  # Day of month (1-31)
    frequency = Column(Enum(BillFrequencyEnum), nullable=False, default=BillFrequencyEnum.MONTHLY)
    group_type = Column(String(50), nullable=False, default="student_loan")
    preferred_source_bank = Column(String(100), nullable=True)
    preferred_source_account = Column(String(100), nullable=True)
    is_paid_this_period = Column(Boolean, nullable=False, default=False)
    last_paid_date = Column(Date, nullable=True)
    # Payments per due date (JSON list), skipped due dates, tracking start (see bills)
    payment_log = Column(Text, nullable=True)
    skipped_dates = Column(Text, nullable=True)
    tracked_from = Column(Date, nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    members = relationship("BillGroupMemberModel", back_populates="bill_group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BillGroupModel(id={self.id}, name={self.group_name})>"


class BillGroupMemberModel(Base):
    """Represents a single account in a bill group."""
    __tablename__ = "bill_group_members"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("bill_groups.id"), nullable=False)
    bank_name = Column(String(100), nullable=False)
    account_name = Column(String(100), nullable=False)
    allocation_method = Column(Enum(AllocationMethodEnum), nullable=False, default=AllocationMethodEnum.PROPORTIONAL)
    fixed_amount = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    bill_group = relationship("BillGroupModel", back_populates="members")

    def __repr__(self):
        return f"<BillGroupMemberModel(id={self.id}, account={self.account_name})>"


# ==================== Initialize Database ====================

# ==================== Planning, ledger, goals, alerts, auth ====================

class AppSettingModel(Base):
    """One app-wide setting (see models/app_settings.py). Value is JSON."""
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(4000), nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class CategoryModel(Base):
    """A spending/income category with an optional monthly budget."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    kind = Column(String(20), nullable=False, default="expense")  # expense | income | transfer
    is_everyday = Column(Boolean, nullable=False, default=False)  # counts toward everyday spending
    monthly_budget = Column(Float, nullable=True)
    color = Column(String(20), nullable=True)
    # Envelope-style: unspent budget carries into next month (and overspending is taken from it)
    rollover = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now)


class CategoryRuleModel(Base):
    """Auto-categorization rule: descriptions containing `pattern` get `category`."""
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True)
    pattern = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # higher wins
    created_at = Column(DateTime, default=utc_now)


class LedgerTransactionModel(Base):
    """A real-world transaction (imported from SimpleFIN/CSV or entered by hand)."""
    __tablename__ = "ledger_transactions"

    id = Column(Integer, primary_key=True)
    txn_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    payee = Column(String(200), nullable=True)
    amount = Column(Float, nullable=False)  # negative = money out
    bank_name = Column(String(100), nullable=True)
    account_name = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    source = Column(String(20), nullable=False, default="manual")  # simplefin | csv | manual
    external_id = Column(String(200), nullable=True, unique=True)
    matched_bill = Column(String(100), nullable=True)
    notes = Column(String(500), nullable=True)
    tags = Column(String(300), nullable=True)  # comma-separated, lowercase
    created_at = Column(DateTime, default=utc_now)


class SavingsGoalModel(Base):
    """A savings goal or sinking fund."""
    __tablename__ = "savings_goals"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    target_amount = Column(Float, nullable=False)
    target_date = Column(Date, nullable=True)
    bank_name = Column(String(100), nullable=True)
    account_name = Column(String(100), nullable=True)
    saved_amount = Column(Float, nullable=False, default=0.0)  # money set aside so far
    linked_bill = Column(String(100), nullable=True)  # sinking fund for this bill
    created_at = Column(DateTime, default=utc_now)


class DismissedAlertModel(Base):
    """An alert the user dismissed (hidden until `until`)."""
    __tablename__ = "dismissed_alerts"

    key = Column(String(300), primary_key=True)
    until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class UserModel(Base):
    """A person who can sign in. Everyone shares the same household budget."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True, nullable=False)  # stored lowercase
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    must_change_password = Column(Boolean, nullable=False, default=False)  # still the generated one
    created_at = Column(DateTime, default=utc_now)
    last_login = Column(DateTime)


class AuthInviteModel(Base):
    """A one-time code: an invitation to register, or a password reset for one user."""
    __tablename__ = "auth_invites"

    id = Column(Integer, primary_key=True)
    code_hash = Column(String(64), unique=True, nullable=False)
    kind = Column(String(10), nullable=False, default="invite")  # invite | reset
    make_admin = Column(Boolean, nullable=False, default=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))  # reset: whose password
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    used_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=utc_now)


class AuthSessionModel(Base):
    """A login session token (stored as a SHA-256 hash)."""
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime)            # local time, updated every few minutes of use
    user_agent = Column(String(300))
    ip = Column(String(64))


class ActivityModel(Base):
    """Who changed what — the shared budget's history."""
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    at = Column(DateTime, nullable=False)   # local time
    user_id = Column(Integer)               # no foreign key: history outlives deleted accounts
    username = Column(String(32), nullable=False, default="")
    action = Column(String(80), nullable=False)
    detail = Column(String(400), nullable=False, default="")


class TransactionSplitModel(Base):
    """Part of a ledger transaction assigned to its own category (split transactions)."""
    __tablename__ = "transaction_splits"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("ledger_transactions.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=True)
    amount = Column(Float, nullable=False)  # signed, same sign as the transaction
    note = Column(String(200), nullable=True)


class AssetModel(Base):
    """Something you own that isn't a bank account: a car, investments, retirement, property..."""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    kind = Column(String(30), nullable=False, default="other")  # see models/assets.py KINDS
    value = Column(Float, nullable=False, default=0.0)
    notes = Column(String(300), nullable=True)
    # Optional loan against it (e.g. a car loan tracked as a credit account), for equity
    linked_bank = Column(String(100), nullable=True)
    linked_account = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    created_at = Column(DateTime, default=utc_now)


class AssetValueModel(Base):
    """Value history for an asset."""
    __tablename__ = "asset_values"

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    value = Column(Float, nullable=False)
    recorded_on = Column(Date, nullable=False)


def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    print(f"✓ Database initialized at: {DB_PATH}")


def _run_migrations():
    """Run any needed schema migrations for existing databases."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    # Migration: add promo_balance column to promo_offers table
    if "promo_offers" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("promo_offers")]
        if "promo_balance" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE promo_offers ADD COLUMN promo_balance FLOAT NOT NULL DEFAULT 0.0"
                ))

    # Migration: add floating bill tracking columns to bills table
    if "bills" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("bills")]
        with engine.begin() as conn:
            if "estimated_amount" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN estimated_amount FLOAT"
                ))
            if "actual_amount" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN actual_amount FLOAT"
                ))
            if "amount_history" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN amount_history TEXT"
                ))
            if "carryover_balance" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN carryover_balance FLOAT NOT NULL DEFAULT 0.0"
                ))
            if "due_month" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN due_month INTEGER"
                ))

    # Migration: create bill_groups and bill_group_members tables if they don't exist
    if "bill_groups" not in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE bill_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT UNIQUE NOT NULL,
                    total_payment REAL NOT NULL DEFAULT 0.0,
                    due_date INTEGER NOT NULL,
                    frequency TEXT NOT NULL DEFAULT 'monthly',
                    group_type TEXT NOT NULL DEFAULT 'student_loan',
                    preferred_source_bank TEXT,
                    preferred_source_account TEXT,
                    is_paid_this_period INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """))
    if "bill_group_members" not in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE bill_group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL REFERENCES bill_groups(id),
                    bank_name TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    allocation_method TEXT NOT NULL DEFAULT 'proportional',
                    fixed_amount REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT
                )
            """))

    # Migration: create heloc_accounts table if it doesn't exist
    if "heloc_accounts" not in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE heloc_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_id INTEGER NOT NULL REFERENCES banks(id),
                    account_name TEXT NOT NULL,
                    credit_limit REAL NOT NULL,
                    balance REAL NOT NULL DEFAULT 0.0,
                    interest_rate REAL NOT NULL DEFAULT 0.0,
                    draw_period_months INTEGER NOT NULL DEFAULT 180,
                    total_term_months INTEGER NOT NULL DEFAULT 360,
                    start_date TEXT,
                    payment_due_date INTEGER,
                    preferred_source_bank TEXT,
                    preferred_source_account TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """))

    # Migration: add market_value column to mortgage_accounts table
    if "mortgage_accounts" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("mortgage_accounts")]
        if "market_value" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE mortgage_accounts ADD COLUMN market_value FLOAT"
                ))
        # Migration: auto, student, personal and other loans
        with engine.begin() as conn:
            for name, kind in (("loan_kind", "VARCHAR(20) NOT NULL DEFAULT 'mortgage'"),
                               ("payment_override", "FLOAT"), ("value_as_of", "DATE"),
                               ("depreciation_rate", "FLOAT"), ("payments_start", "DATE"),
                               ("subsidized", "BOOLEAN NOT NULL DEFAULT 0"),
                               ("capitalized", "BOOLEAN NOT NULL DEFAULT 0")):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE mortgage_accounts ADD COLUMN {name} {kind}"))

    # Migration: add linked bill columns to bills table
    if "bills" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("bills")]
        with engine.begin() as conn:
            if "linked_bank_name" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN linked_bank_name TEXT"
                ))
            if "linked_account_name" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN linked_account_name TEXT"
                ))
            if "linked_account_type" not in columns:
                conn.execute(text(
                    "ALTER TABLE bills ADD COLUMN linked_account_type TEXT"
                ))

    # Migration: schedule anchor dates for bills and income sources
    for table in ("bills", "income_sources"):
        if table in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns(table)]
            if "start_date" not in columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN start_date DATE"))

    # Migration: per-bill late fee
    if "bills" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("bills")]
        if "late_fee" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE bills ADD COLUMN late_fee FLOAT"))

    # Migration: add last_paid_date to bill_groups (drives auto period reset)
    if "bill_groups" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("bill_groups")]
        if "last_paid_date" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE bill_groups ADD COLUMN last_paid_date DATE"
                ))

    # Migration: paid status per due date. Bills that already exist only count
    # due dates from a month back as overdue (what the app showed before)
    for table, cols in (("bills", (("skipped_dates", "TEXT"), ("actual_amounts", "TEXT"), ("tracked_from", "DATE"))),
                        ("bill_groups", (("payment_log", "TEXT"), ("skipped_dates", "TEXT"), ("tracked_from", "DATE"))),
                        ("bill_payments", (("due_date", "DATE"), ("owed", "FLOAT"), ("moved_money", "BOOLEAN")))):
        if table in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns(table)]
            with engine.begin() as conn:
                for name, kind in cols:
                    if name not in columns:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
                        if name == "tracked_from":
                            conn.execute(text(f"UPDATE {table} SET tracked_from = date('now', 'localtime', '-31 day')"))

    # Migration: sessions belong to a user (older password-only sessions stop working)
    if "auth_sessions" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("auth_sessions")]
        if "user_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN user_id INTEGER"))

    # Migration: remember which device each session is
    if "auth_sessions" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("auth_sessions")]
        with engine.begin() as conn:
            for name, kind in (("last_seen", "DATETIME"), ("user_agent", "VARCHAR(300)"), ("ip", "VARCHAR(64)")):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE auth_sessions ADD COLUMN {name} {kind}"))

    # Migration: budget rollover, transaction tags
    for table, name, kind in (("categories", "rollover", "BOOLEAN NOT NULL DEFAULT 0"),
                              ("ledger_transactions", "tags", "VARCHAR(300)")):
        if table in inspector.get_table_names():
            if name not in [col["name"] for col in inspector.get_columns(table)]:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))

    # Migration: more kinds of bank account (EBT, HSA, ...) and their refill/spending settings
    if "bank_accounts" in inspector.get_table_names():
        _widen_bank_account_types()
        columns = [col["name"] for col in inspector.get_columns("bank_accounts")]
        with engine.begin() as conn:
            for name, kind in (("refill_amount", "FLOAT NOT NULL DEFAULT 0.0"), ("refill_day", "INTEGER"),
                               ("weekly_spending", "FLOAT NOT NULL DEFAULT 0.0"),
                               ("offsets_everyday", "BOOLEAN NOT NULL DEFAULT 0")):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE bank_accounts ADD COLUMN {name} {kind}"))

    # Migration: each card's minimum payment rule
    if "credit_accounts" in inspector.get_table_names():
        if "min_rule" not in [col["name"] for col in inspector.get_columns("credit_accounts")]:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE credit_accounts ADD COLUMN min_rule TEXT"))
        if "payment_order" not in [col["name"] for col in inspector.get_columns("credit_accounts")]:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE credit_accounts ADD COLUMN payment_order VARCHAR(20)"))

    # Migration: flag accounts still using a generated password
    if "users" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "must_change_password" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0"))


def _widen_bank_account_types():
    """
    Databases made by older SQLAlchemy versions may have a CHECK constraint
    that only allows CHECKING/SAVINGS/MORTGAGE. SQLite can't drop a
    constraint, so copy the table into one without it (ids are kept, so
    transactions still point at the right accounts).
    """
    from sqlalchemy import text
    with engine.begin() as conn:
        sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='bank_accounts'")).scalar()
        if not sql or "CHECK" not in sql.upper() or "'EBT'" in sql:
            return
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(bank_accounts)"))]
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("DROP TABLE IF EXISTS bank_accounts_new"))
        conn.execute(text(
            "CREATE TABLE bank_accounts_new (id INTEGER NOT NULL PRIMARY KEY, "
            "bank_id INTEGER NOT NULL REFERENCES banks(id), account_name VARCHAR(100) NOT NULL, "
            "account_type VARCHAR(20) NOT NULL, balance FLOAT NOT NULL, interest_rate FLOAT NOT NULL, "
            "interest_accrual_date INTEGER, refill_amount FLOAT NOT NULL DEFAULT 0.0, refill_day INTEGER, "
            "weekly_spending FLOAT NOT NULL DEFAULT 0.0, offsets_everyday BOOLEAN NOT NULL DEFAULT 0, "
            "created_at DATETIME, updated_at DATETIME)"))
        keep = ", ".join(c for c in cols if c in (
            "id", "bank_id", "account_name", "account_type", "balance", "interest_rate", "interest_accrual_date",
            "refill_amount", "refill_day", "weekly_spending", "offsets_everyday", "created_at", "updated_at"))
        conn.execute(text(f"INSERT INTO bank_accounts_new ({keep}) SELECT {keep} FROM bank_accounts"))
        conn.execute(text("DROP TABLE bank_accounts"))
        conn.execute(text("ALTER TABLE bank_accounts_new RENAME TO bank_accounts"))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def get_session():
    """Get a database session."""
    return SessionLocal()

