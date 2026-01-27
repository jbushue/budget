"""
GraphQL Schema for Personal Finance Management System
Provides a GraphQL API for React Native and other web clients.
"""

import graphene
from datetime import date, datetime, timedelta
from typing import Optional, List
from models.finance_manager import FinanceManager
from models.bank import Bank
from models.bank_account import BankAccount
from models.credit_card_account import CreditAccount
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource


# ==================== Types ====================

class BankAccountType(graphene.ObjectType):
    """Represents a bank account in GraphQL."""
    id = graphene.String()
    account_name = graphene.String()
    account_type = graphene.String()
    balance = graphene.Float()
    interest_rate = graphene.Float()
    interest_accrual_date = graphene.Int()


class CreditAccountType(graphene.ObjectType):
    """Represents a credit account in GraphQL."""
    id = graphene.String()
    account_name = graphene.String()
    balance = graphene.Float()
    regular_balance = graphene.Float()
    credit_limit = graphene.Float()
    available_credit = graphene.Float()
    interest_rate = graphene.Float()
    payment_due_date = graphene.Int()
    statement_date = graphene.Int()
    status = graphene.String()


class BankType(graphene.ObjectType):
    """Represents a bank in GraphQL."""
    name = graphene.String()
    bank_type = graphene.String()
    bank_accounts = graphene.List(BankAccountType)
    credit_accounts = graphene.List(CreditAccountType)
    total_balance = graphene.Float()
    total_credit_limit = graphene.Float()
    total_available_credit = graphene.Float()

    def resolve_bank_accounts(self, info):
        """Resolve bank accounts."""
        return [
            BankAccountType(
                id=name,
                account_name=name,
                account_type=acc.account_type.value,
                balance=acc.balance,
                interest_rate=acc.interest_rate,
                interest_accrual_date=acc.interest_accrual_date
            )
            for name, acc in self.accounts.items()
        ]

    def resolve_credit_accounts(self, info):
        """Resolve credit accounts."""
        return [
            CreditAccountType(
                id=name,
                account_name=name,
                balance=acc.balance,
                regular_balance=acc.regular_balance,
                credit_limit=acc.credit_limit,
                available_credit=acc.available_credit(),
                interest_rate=acc.interest_rate,
                payment_due_date=acc.payment_due_date,
                statement_date=acc.statement_date,
                status=acc.status.value
            )
            for name, acc in self.credit_accounts.items()
        ]

    def resolve_total_balance(self, info):
        """Resolve total balance across all accounts."""
        return sum(acc.balance for acc in self.get_all_accounts())

    def resolve_total_credit_limit(self, info):
        """Resolve total credit limit."""
        return sum(acc.credit_limit for acc in self.get_all_credit_accounts())

    def resolve_total_available_credit(self, info):
        """Resolve total available credit."""
        return self.total_available_credit()


class BillType(graphene.ObjectType):
    """Represents a bill in GraphQL."""
    id = graphene.String()
    bill_name = graphene.String()
    amount = graphene.Float()
    due_date = graphene.Int()
    bill_type = graphene.String()
    frequency = graphene.String()
    min_amount = graphene.Float()
    max_amount = graphene.Float()
    next_due_date = graphene.String()
    preferred_source_bank = graphene.String()
    preferred_source_account = graphene.String()


class IncomeSourceType(graphene.ObjectType):
    """Represents an income source in GraphQL."""
    id = graphene.String()
    source_name = graphene.String()
    amount = graphene.Float()
    frequency = graphene.String()
    pay_date = graphene.Int()
    next_pay_date = graphene.String()
    distribution = graphene.JSONString()


class BalanceSnapshotType(graphene.ObjectType):
    """Represents a balance snapshot on a specific date."""
    date = graphene.String()
    balances = graphene.JSONString()
    total = graphene.Float()


class ProjectionType(graphene.ObjectType):
    """Represents a full projection."""
    start_date = graphene.String()
    end_date = graphene.String()
    snapshots = graphene.List(BalanceSnapshotType)
    final_balances = graphene.JSONString()
    total_final_balance = graphene.Float()
    total_income = graphene.Float()
    total_expenses = graphene.Float()
    net_change = graphene.Float()


class PaymentPlanType(graphene.ObjectType):
    """Represents a payment plan."""
    strategy = graphene.JSONString()
    discretionary_funds = graphene.Float()
    total_interest = graphene.Float()
    total_fees = graphene.Float()
    violations = graphene.List(graphene.String)


class FinancialSnapshotType(graphene.ObjectType):
    """Represents current financial state."""
    timestamp = graphene.String()
    banks = graphene.List(BankType)
    total_assets = graphene.Float()
    total_liabilities = graphene.Float()
    net_worth = graphene.Float()
    upcoming_bills_30_days = graphene.List(BillType)
    upcoming_income_30_days = graphene.List(IncomeSourceType)


# ==================== Queries ====================

class Query(graphene.ObjectType):
    """Root query for the GraphQL API."""

    # Bank Queries
    all_banks = graphene.List(BankType)
    bank = graphene.Field(BankType, name=graphene.String(required=True))

    # Bill Queries
    all_bills = graphene.List(BillType)
    upcoming_bills = graphene.List(BillType, days=graphene.Int(default_value=60))

    # Income Queries
    all_income = graphene.List(IncomeSourceType)
    upcoming_income = graphene.List(IncomeSourceType, days=graphene.Int(default_value=60))

    # Financial Queries
    snapshot = graphene.Field(FinancialSnapshotType)
    balance_on_date = graphene.Field(
        graphene.JSONString,
        date=graphene.String(required=True),
        description="Get balance on specific date (YYYY-MM-DD)"
    )
    projection = graphene.Field(
        ProjectionType,
        days=graphene.Int(default_value=90),
        description="Project balances for N days"
    )
    payment_plan = graphene.Field(
        PaymentPlanType,
        days=graphene.Int(default_value=90),
        description="Get optimized payment plan"
    )

    def resolve_all_banks(self, info):
        """Get all banks."""
        manager = info.context.get('manager')
        return manager.banks if manager else []

    def resolve_bank(self, info, name):
        """Get specific bank by name."""
        manager = info.context.get('manager')
        if manager:
            for bank in manager.banks:
                if bank.name == name:
                    return bank
        return None

    def resolve_all_bills(self, info):
        """Get all bills."""
        manager = info.context.get('manager')
        if manager:
            return [
                BillType(
                    id=bill.bill_name,
                    bill_name=bill.bill_name,
                    amount=bill.amount,
                    due_date=bill.due_date,
                    bill_type=bill.bill_type.value if hasattr(bill, 'bill_type') else 'fixed',
                    frequency=bill.frequency.value,
                    min_amount=getattr(bill, 'min_amount', None),
                    max_amount=getattr(bill, 'max_amount', None),
                    next_due_date=bill.get_next_due_date(date.today() - timedelta(days=1)).isoformat(),
                    preferred_source_bank=bill.preferred_source_bank,
                    preferred_source_account=bill.preferred_source_account
                )
                for bill in manager.bills
            ]
        return []

    def resolve_upcoming_bills(self, info, days):
        """Get upcoming bills."""
        manager = info.context.get('manager')
        if manager:
            bills = manager.get_upcoming_bills(days)
            return [
                BillType(
                    id=bill.bill_name,
                    bill_name=bill.bill_name,
                    amount=bill.amount,
                    due_date=bill.due_date,
                    bill_type=bill.bill_type.value if hasattr(bill, 'bill_type') else 'fixed',
                    frequency=bill.frequency.value,
                    min_amount=getattr(bill, 'min_amount', None),
                    max_amount=getattr(bill, 'max_amount', None),
                    next_due_date=bill.get_next_due_date(date.today() - timedelta(days=1)).isoformat(),
                    preferred_source_bank=bill.preferred_source_bank,
                    preferred_source_account=bill.preferred_source_account
                )
                for bill in bills
            ]
        return []

    def resolve_all_income(self, info):
        """Get all income sources."""
        manager = info.context.get('manager')
        if manager:
            return [
                IncomeSourceType(
                    id=income.source_name,
                    source_name=income.source_name,
                    amount=income.amount,
                    frequency=income.frequency.value,
                    pay_date=income.pay_date,
                    next_pay_date=income.get_next_pay_date(date.today() - timedelta(days=1)).isoformat(),
                    distribution=income.distribution
                )
                for income in manager.income_sources
            ]
        return []

    def resolve_upcoming_income(self, info, days):
        """Get upcoming income."""
        manager = info.context.get('manager')
        if manager:
            income_sources = manager.get_upcoming_income(days)
            return [
                IncomeSourceType(
                    id=income.source_name,
                    source_name=income.source_name,
                    amount=income.amount,
                    frequency=income.frequency.value,
                    pay_date=income.pay_date,
                    next_pay_date=income.get_next_pay_date(date.today() - timedelta(days=1)).isoformat(),
                    distribution=income.distribution
                )
                for income in income_sources
            ]
        return []

    def resolve_snapshot(self, info):
        """Get current financial snapshot."""
        manager = info.context.get('manager')
        if not manager:
            return None

        return FinancialSnapshotType(
            timestamp=datetime.now().isoformat(),
            banks=manager.banks,
            total_assets=manager.get_total_assets(),
            total_liabilities=manager.get_total_liabilities(),
            net_worth=manager.get_net_worth(),
            upcoming_bills_30_days=manager.get_upcoming_bills(30),
            upcoming_income_30_days=manager.get_upcoming_income(30)
        )

    def resolve_balance_on_date(self, info, date_str):
        """Get balance on specific date."""
        manager = info.context.get('manager')
        if not manager:
            return None

        try:
            target_date = datetime.fromisoformat(date_str).date()
            balances = manager.get_balance_on_date(target_date)
            return balances
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

    def resolve_projection(self, info, days):
        """Get projection."""
        manager = info.context.get('manager')
        if not manager:
            return None

        end_date = date.today() + timedelta(days=days)
        result = manager.project_balances(end_date=end_date)

        snapshots = [
            BalanceSnapshotType(
                date=snap['date'].isoformat(),
                balances=snap['balances'],
                total=sum(snap['balances'].values())
            )
            for snap in result['snapshots']
        ]

        # Calculate totals
        total_income = sum(cf['amount'] for cf in result['cash_flow'] if cf['type'] == 'INCOME')
        total_expenses = sum(-cf['amount'] for cf in result['cash_flow'] if cf['type'] == 'BILL_PAYMENT')
        net_change = sum(cf['amount'] for cf in result['cash_flow'])

        return ProjectionType(
            start_date=result['start_date'].isoformat(),
            end_date=result['end_date'].isoformat(),
            snapshots=snapshots,
            final_balances=result['final_balances'],
            total_final_balance=sum(result['final_balances'].values()),
            total_income=total_income,
            total_expenses=total_expenses,
            net_change=net_change
        )

    def resolve_payment_plan(self, info, days):
        """Get optimized payment plan."""
        manager = info.context.get('manager')
        if not manager:
            return None

        end_date = date.today() + timedelta(days=days)
        plan = manager.optimize_payments(end_date=end_date)

        return PaymentPlanType(
            strategy=plan.strategy,
            discretionary_funds=plan.final_discretionary,
            total_interest=plan.total_interest_paid,
            total_fees=plan.total_fees,
            violations=plan.violations
        )


# ==================== Mutations ====================

class CreateBank(graphene.Mutation):
    """Create a new bank."""

    class Arguments:
        name = graphene.String(required=True)
        bank_type = graphene.String(default_value="traditional")

    bank = graphene.Field(BankType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, bank_type):
        manager = info.context.get('manager')
        if not manager:
            return CreateBank(success=False, message="Manager not available")

        try:
            # Check if bank exists
            if any(b.name == name for b in manager.banks):
                return CreateBank(success=False, message=f"Bank '{name}' already exists")

            bank = Bank(name, bank_type)
            manager.banks.append(bank)
            return CreateBank(bank=bank, success=True, message=f"Bank '{name}' created")
        except Exception as e:
            return CreateBank(success=False, message=str(e))


class CreateAccount(graphene.Mutation):
    """Create a new account in a bank."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        account_type = graphene.String(default_value="checking")
        balance = graphene.Float(default_value=0.0)
        interest_rate = graphene.Float(default_value=0.0)
        credit_limit = graphene.Float()

    account = graphene.Field(BankAccountType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, account_type, balance, interest_rate, credit_limit=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateAccount(success=False, message="Manager not available")

        try:
            bank = next((b for b in manager.banks if b.name == bank_name), None)
            if not bank:
                return CreateAccount(success=False, message=f"Bank '{bank_name}' not found")

            if account_type == "credit":
                if not credit_limit:
                    return CreateAccount(success=False, message="credit_limit required for credit accounts")
                account = bank.add_credit_account(account_name, credit_limit, interest_rate)
            else:
                account = bank.add_account(account_type, account_name, balance, interest_rate)

            return CreateAccount(account=account, success=True, message=f"Account '{account_name}' created")
        except Exception as e:
            return CreateAccount(success=False, message=str(e))


class CreateBill(graphene.Mutation):
    """Create a new bill."""

    class Arguments:
        bill_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        due_date = graphene.Int(required=True)
        frequency = graphene.String(default_value="monthly")

    bill = graphene.Field(BillType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, amount, due_date, frequency):
        manager = info.context.get('manager')
        if not manager:
            return CreateBill(success=False, message="Manager not available")

        try:
            bill = Bill(bill_name, amount, due_date, frequency=frequency)
            manager.bills.append(bill)
            return CreateBill(bill=bill, success=True, message=f"Bill '{bill_name}' created")
        except Exception as e:
            return CreateBill(success=False, message=str(e))


class CreateIncomeSource(graphene.Mutation):
    """Create a new income source."""

    class Arguments:
        source_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        frequency = graphene.String(default_value="monthly")
        pay_date = graphene.Int(default_value=1)
        distribution = graphene.JSONString(default_value={})

    income = graphene.Field(IncomeSourceType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, source_name, amount, frequency, pay_date, distribution):
        manager = info.context.get('manager')
        if not manager:
            return CreateIncomeSource(success=False, message="Manager not available")

        try:
            income = IncomeSource(source_name, amount, frequency, pay_date, distribution)
            manager.income_sources.append(income)
            return CreateIncomeSource(income=income, success=True, message=f"Income '{source_name}' created")
        except Exception as e:
            return CreateIncomeSource(success=False, message=str(e))


class UpdateAccountBalance(graphene.Mutation):
    """Update account balance."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        new_balance = graphene.Float(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    new_balance = graphene.Float()

    def mutate(self, info, bank_name, account_name, new_balance):
        manager = info.context.get('manager')
        if not manager:
            return UpdateAccountBalance(success=False, message="Manager not available")

        try:
            bank = next((b for b in manager.banks if b.name == bank_name), None)
            if not bank:
                return UpdateAccountBalance(success=False, message=f"Bank '{bank_name}' not found")

            bank.update_account_balance(account_name, new_balance)
            return UpdateAccountBalance(
                success=True,
                message=f"Account balance updated",
                new_balance=new_balance
            )
        except Exception as e:
            return UpdateAccountBalance(success=False, message=str(e))


class SaveDatabase(graphene.Mutation):
    """Save data to database."""

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info):
        manager = info.context.get('manager')
        if not manager:
            return SaveDatabase(success=False, message="Manager not available")

        try:
            if manager.save_to_database():
                return SaveDatabase(success=True, message="Data saved to database")
            else:
                return SaveDatabase(success=False, message="Failed to save data")
        except Exception as e:
            return SaveDatabase(success=False, message=str(e))


class LoadDatabase(graphene.Mutation):
    """Load data from database."""

    success = graphene.Boolean()
    message = graphene.String()
    banks_count = graphene.Int()

    def mutate(self, info):
        manager = info.context.get('manager')
        if not manager:
            return LoadDatabase(success=False, message="Manager not available")

        try:
            if manager.load_from_database():
                return LoadDatabase(
                    success=True,
                    message="Data loaded from database",
                    banks_count=len(manager.banks)
                )
            else:
                return LoadDatabase(success=False, message="Failed to load data")
        except Exception as e:
            return LoadDatabase(success=False, message=str(e))


class Mutation(graphene.ObjectType):
    """Root mutation for the GraphQL API."""

    create_bank = CreateBank.Field()
    create_account = CreateAccount.Field()
    create_bill = CreateBill.Field()
    create_income_source = CreateIncomeSource.Field()
    update_account_balance = UpdateAccountBalance.Field()
    save_database = SaveDatabase.Field()
    load_database = LoadDatabase.Field()


# ==================== Schema ====================

schema = graphene.Schema(query=Query, mutation=Mutation)

