"""
Database models and configuration using SQLAlchemy with SQLite.
Provides persistent storage for the financial management system.
"""

from datetime import date, datetime, timezone
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import enum
import os

from models.income_source import IncomeFrequency
from models.types import *

# Create database directory if it doesn't exist
DB_DIR = os.path.join(os.path.expanduser("~"), ".budget_app")
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
    """Represents a traditional bank account (checking/savings)."""
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    account_type = Column(Enum(AccountTypeEnum), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    interest_rate = Column(Float, nullable=False, default=0.0)  # APR as percentage
    interest_accrual_date = Column(Integer, nullable=True)  # Day of month (1-31)
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
    market_value = Column(Float, nullable=True)  # Current market value of the property
    
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

    # Migration: sessions belong to a user (older password-only sessions stop working)
    if "auth_sessions" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("auth_sessions")]
        if "user_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN user_id INTEGER"))


def get_session():
    """Get a database session."""
    return SessionLocal()

