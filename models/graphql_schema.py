"""
GraphQL Schema for Personal Finance Management System
Provides a GraphQL API for React Native and other web clients.
"""

import graphene
from models.gql_ext import ExtQuery, ExtMutation
from datetime import date, datetime, timedelta
from typing import Optional, List
from models.finance_manager import FinanceManager
from models.bank import Bank
from models.bank_account import BankAccount
from models.credit_card_account import CreditAccount
from models.fixed_bill import Bill, FloatingBill, AccountLinkedBill, GroupLinkedBill
from models.income_source import IncomeSource
from models.types import DistributionType


# ==================== Types ====================

class BankAccountType(graphene.ObjectType):
    """Represents a bank account in GraphQL."""
    id = graphene.String()
    account_name = graphene.String()
    account_type = graphene.String()
    balance = graphene.Float()
    interest_rate = graphene.Float()
    interest_accrual_date = graphene.Int()


class PromoOfferType(graphene.ObjectType):
    """Represents a promotional offer on a credit account."""
    promo_name = graphene.String()
    months_interest_free = graphene.Int()
    purchase_limit = graphene.Float()
    start_date = graphene.String()
    end_date = graphene.String()
    amount_used = graphene.Float()
    promo_balance = graphene.Float()
    is_active = graphene.Boolean()
    days_remaining = graphene.Int()
    interest_charged = graphene.Boolean()


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
    minimum_payment = graphene.Float()
    promo_offers = graphene.List(PromoOfferType)


class MortgageAccountType(graphene.ObjectType):
    """Represents a mortgage account in GraphQL."""
    id = graphene.String()
    account_name = graphene.String()
    original_principal = graphene.Float()
    current_principal = graphene.Float()
    interest_rate = graphene.Float()
    loan_term_months = graphene.Int()
    payment_due_date = graphene.Int()
    total_monthly_payment = graphene.Float()
    monthly_principal = graphene.Float()
    monthly_interest = graphene.Float()
    escrow_monthly = graphene.Float()
    preferred_source_bank = graphene.String()
    preferred_source_account = graphene.String()
    status = graphene.String()
    market_value = graphene.Float()
    equity = graphene.Float()
    is_paid_this_period = graphene.Boolean()


class HELOCAccountType(graphene.ObjectType):
    """Represents a HELOC account in GraphQL."""
    id = graphene.String()
    account_name = graphene.String()
    credit_limit = graphene.Float()
    balance = graphene.Float()
    available_credit = graphene.Float()
    interest_rate = graphene.Float()
    draw_period_months = graphene.Int()
    total_term_months = graphene.Int()
    start_date = graphene.String()
    draw_end_date = graphene.String()
    maturity_date = graphene.String()
    current_phase = graphene.String()
    minimum_payment = graphene.Float()
    monthly_interest = graphene.Float()
    payment_due_date = graphene.Int()
    preferred_source_bank = graphene.String()
    preferred_source_account = graphene.String()
    is_paid_this_period = graphene.Boolean()


class BankType(graphene.ObjectType):
    """Represents a bank in GraphQL."""
    name = graphene.String()
    bank_type = graphene.String()
    bank_accounts = graphene.List(BankAccountType)
    credit_accounts = graphene.List(CreditAccountType)
    mortgage_accounts = graphene.List(MortgageAccountType)
    heloc_accounts = graphene.List(HELOCAccountType)
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
        results = []
        for name, acc in self.credit_accounts.items():
            promos = []
            for p in getattr(acc, 'active_promos', []):
                promo_bal = acc.promo_balance.get(p.promo_name, 0.0) if hasattr(acc, 'promo_balance') else 0.0
                promos.append(PromoOfferType(
                    promo_name=p.promo_name,
                    months_interest_free=p.months_interest_free,
                    purchase_limit=p.purchase_limit,
                    start_date=p.start_date.isoformat() if p.start_date else None,
                    end_date=p.end_date.isoformat() if p.end_date else None,
                    amount_used=p.amount_used,
                    promo_balance=promo_bal,
                    is_active=p.is_active,
                    days_remaining=p.days_remaining,
                    interest_charged=p.interest_charged,
                ))
            results.append(CreditAccountType(
                id=name,
                account_name=name,
                balance=acc.balance,
                regular_balance=acc.regular_balance,
                credit_limit=acc.credit_limit,
                available_credit=acc.available_credit,
                interest_rate=acc.interest_rate,
                payment_due_date=acc.payment_due_date,
                statement_date=acc.statement_date,
                status=acc.status.value,
                minimum_payment=acc.calculate_minimum_payment(),
                promo_offers=promos,
            ))
        return results

    def resolve_mortgage_accounts(self, info):
        """Resolve mortgage accounts."""
        mortgage_dict = getattr(self, 'mortgage_accounts', {})
        if not isinstance(mortgage_dict, dict):
            mortgage_dict = {}
        return [
            MortgageAccountType(
                id=name,
                account_name=name,
                original_principal=m.original_principal,
                current_principal=m.current_principal,
                interest_rate=m.interest_rate,
                loan_term_months=m.loan_term_months,
                payment_due_date=m.payment_due_date,
                total_monthly_payment=m.total_monthly_payment,
                monthly_principal=m.current_monthly_principal,
                monthly_interest=m.current_monthly_interest,
                escrow_monthly=m.escrow.total_monthly if m.escrow else 0,
                preferred_source_bank=m.preferred_source_bank,
                preferred_source_account=m.preferred_source_account,
                status=m.status.value if hasattr(m.status, 'value') else str(m.status),
                market_value=m.market_value,
                equity=m.equity,
                is_paid_this_period=m.is_paid_this_period,
            )
            for name, m in mortgage_dict.items()
        ]

    def resolve_heloc_accounts(self, info):
        """Resolve HELOC accounts."""
        heloc_dict = getattr(self, 'heloc_accounts', {})
        if not isinstance(heloc_dict, dict):
            heloc_dict = {}
        return [
            HELOCAccountType(
                id=name,
                account_name=name,
                credit_limit=h.credit_limit,
                balance=h.balance,
                available_credit=h.available_credit,
                interest_rate=h.interest_rate,
                draw_period_months=h.draw_period_months,
                total_term_months=h.total_term_months,
                start_date=h.start_date.isoformat() if h.start_date else None,
                draw_end_date=h.draw_end_date.isoformat() if h.draw_end_date else None,
                maturity_date=h.maturity_date.isoformat() if h.maturity_date else None,
                current_phase=h.current_phase.value if hasattr(h.current_phase, 'value') else str(h.current_phase),
                minimum_payment=h.calculate_minimum_payment(),
                monthly_interest=h.current_monthly_interest,
                payment_due_date=h.payment_due_date,
                preferred_source_bank=h.preferred_source_bank,
                preferred_source_account=h.preferred_source_account,
                is_paid_this_period=h.is_paid_this_period,
            )
            for name, h in heloc_dict.items()
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
    due_month = graphene.Int()
    bill_type = graphene.String()
    frequency = graphene.String()
    min_amount = graphene.Float()
    max_amount = graphene.Float()
    next_due_date = graphene.String()
    preferred_source_bank = graphene.String()
    preferred_source_account = graphene.String()
    is_paid_this_period = graphene.Boolean()
    estimated_amount = graphene.Float()
    actual_amount = graphene.Float()
    has_actual_amount = graphene.Boolean()
    carryover_balance = graphene.Float()
    effective_amount = graphene.Float()
    is_account_linked = graphene.Boolean()
    linked_bank_name = graphene.String()
    linked_account_name = graphene.String()
    linked_account_type = graphene.String()
    start_date = graphene.String()


def _iso(d):
    """ISO-format a date, passing None through."""
    return d.isoformat() if d else None


def _next_occurrence(d):
    """ISO-format a next due/pay date; one-time items that already happened
    report date.max, which is shown as no next date."""
    return None if d is None or d == date.max else d.isoformat()


def _parse_date(value: str | None, field: str = "date"):
    """Parse a YYYY-MM-DD string (None/'' -> None) with a friendly error."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field} '{value}'. Use YYYY-MM-DD.")


def _income_to_type(income) -> 'IncomeSourceType':
    """Convert an IncomeSource object to an IncomeSourceType GraphQL object."""
    return IncomeSourceType(
        id=income.source_name,
        source_name=income.source_name,
        amount=income.amount,
        frequency=income.frequency.value if hasattr(income.frequency, 'value') else str(income.frequency),
        pay_dates=income.pay_date,
        next_pay_date=_next_occurrence(income.get_next_pay_date(date.today() - timedelta(days=1))),
        distribution=_serialize_distribution(income.distribution),
        start_date=_iso(getattr(income, 'start_date', None)),
    )


def _bill_to_type(bill) -> 'BillType':
    """Convert a Bill object to a BillType GraphQL object."""
    carryover = getattr(bill, 'carryover_balance', 0.0) or 0.0
    effective = getattr(bill, 'effective_amount', bill.amount)
    is_linked = isinstance(bill, AccountLinkedBill)
    return BillType(
        id=bill.bill_name,
        bill_name=bill.bill_name,
        amount=bill.amount,
        due_date=bill.due_date,
        due_month=getattr(bill, 'due_month', None),
        bill_type=bill.bill_type.value if hasattr(bill.bill_type, 'value') else str(bill.bill_type),
        frequency=bill.frequency.value if hasattr(bill.frequency, 'value') else str(bill.frequency),
        min_amount=getattr(bill, 'min_amount', None),
        max_amount=getattr(bill, 'max_amount', None),
        next_due_date=_next_occurrence(bill.get_next_due_date(date.today() - timedelta(days=1))),
        preferred_source_bank=bill.preferred_source_bank,
        preferred_source_account=bill.preferred_source_account,
        is_paid_this_period=getattr(bill, 'is_paid_this_period', False),
        estimated_amount=getattr(bill, 'estimated_amount', None),
        actual_amount=getattr(bill, '_actual_amount', None),
        has_actual_amount=getattr(bill, 'has_actual_amount', False),
        carryover_balance=carryover,
        effective_amount=effective,
        is_account_linked=is_linked,
        linked_bank_name=getattr(bill, 'linked_bank_name', None) if is_linked else None,
        linked_account_name=bill.linked_account.account_name if is_linked else None,
        linked_account_type=getattr(bill, 'linked_account_type', None) if is_linked else None,
        start_date=_iso(getattr(bill, 'start_date', None)),
    )


class CreditPaymentDueType(graphene.ObjectType):
    """Represents a credit card payment that is due."""
    id = graphene.String()
    bank_name = graphene.String()
    account_name = graphene.String()
    balance = graphene.Float()
    minimum_payment = graphene.Float()
    payment_due_date = graphene.Int()
    interest_rate = graphene.Float()
    credit_limit = graphene.Float()
    available_credit = graphene.Float()
    status = graphene.String()
    is_paid_this_period = graphene.Boolean()
    last_payment_amount = graphene.Float()
    last_payment_date = graphene.String()


class BalanceHistoryType(graphene.ObjectType):
    """Represents a historical balance record."""
    account_name = graphene.String()
    bank_name = graphene.String()
    account_type = graphene.String()
    balance = graphene.Float()
    previous_balance = graphene.Float()
    recorded_at = graphene.String()
    notes = graphene.String()


def _serialize_distribution(dist):
    """Safely convert a distribution to a JSON-serializable dict."""
    if dist is None:
        return None
    if isinstance(dist, dict):
        return dist
    if hasattr(dist, 'to_simple_dict'):
        return dist.to_simple_dict()
    if hasattr(dist, '__todict__'):
        return dist.__todict__()
    return None


class IncomeSourceType(graphene.ObjectType):
    """Represents an income source in GraphQL."""
    id = graphene.String()
    source_name = graphene.String()
    amount = graphene.Float()
    frequency = graphene.String()
    pay_dates = graphene.List(graphene.Int)  # List of pay dates (e.g., [15, 31] for semimonthly)
    next_pay_date = graphene.String()
    distribution = graphene.JSONString()
    start_date = graphene.String()

    def resolve_distribution(self, info):
        dist = getattr(self, 'distribution', None)
        return _serialize_distribution(dist)

    def resolve_frequency(self, info):
        freq = getattr(self, 'frequency', None)
        if freq is None:
            return None
        return freq.value if hasattr(freq, 'value') else freq

    def resolve_pay_dates(self, info):
        pd = getattr(self, 'pay_date', None) or getattr(self, 'pay_dates', None)
        if pd is None:
            return []
        return pd

    def resolve_next_pay_date(self, info):
        npd = getattr(self, 'next_pay_date', None)
        if npd is not None:
            return npd
        # Raw IncomeSource object — compute it
        if hasattr(self, 'get_next_pay_date'):
            return _next_occurrence(self.get_next_pay_date(date.today() - timedelta(days=1)))
        return None


class SimplefinStatusType(graphene.ObjectType):
    """SimpleFIN Bridge connection status."""
    is_connected = graphene.Boolean()
    created_at = graphene.String()
    last_sync_at = graphene.String()
    mapped_account_count = graphene.Int()


class SimplefinSyncedAccountType(graphene.ObjectType):
    """An account that is mapped/synced via SimpleFIN."""
    bank_name = graphene.String()
    account_name = graphene.String()
    account_type = graphene.String()
    sfin_name = graphene.String()
    sfin_org = graphene.String()


class SimplefinAccountType(graphene.ObjectType):
    """An account from SimpleFIN Bridge."""
    id = graphene.String()
    name = graphene.String()
    org_name = graphene.String()
    org_domain = graphene.String()
    currency = graphene.String()
    balance = graphene.Float()
    available_balance = graphene.Float()
    balance_date = graphene.String()
    mapped_bank_name = graphene.String()
    mapped_account_name = graphene.String()
    mapped_account_type = graphene.String()


class SimplefinTransactionType(graphene.ObjectType):
    """A transaction from SimpleFIN Bridge (read-only/informational)."""
    id = graphene.String()
    posted = graphene.String()  # ISO date string
    amount = graphene.Float()
    description = graphene.String()
    payee = graphene.String()
    memo = graphene.String()


class BalanceSnapshotType(graphene.ObjectType):
    """Represents a balance snapshot on a specific date."""
    date = graphene.String()
    balances = graphene.JSONString()
    credit_balances = graphene.JSONString()
    mortgage_balances = graphene.JSONString()
    heloc_balances = graphene.JSONString()
    total = graphene.Float()
    net_total = graphene.Float()


class CalendarEventType(graphene.ObjectType):
    """A single financial event on a calendar day."""
    event_type = graphene.String()          # INCOME, BILL_PAYMENT, CREDIT_PAYMENT, MORTGAGE_PAYMENT, etc.
    description = graphene.String()
    amount = graphene.Float()
    source_bank = graphene.String()
    source_account = graphene.String()
    status = graphene.String()              # ok, deferred, insufficient_funds


class CalendarDayType(graphene.ObjectType):
    """All events and balances for a single calendar day."""
    date = graphene.String()
    events = graphene.List(CalendarEventType)
    balances = graphene.JSONString()         # {account_key: balance} after events
    credit_balances = graphene.JSONString()
    mortgage_balances = graphene.JSONString()
    heloc_balances = graphene.JSONString()
    total = graphene.Float()
    net_total = graphene.Float()


class ProjectionType(graphene.ObjectType):
    """Represents a full projection."""
    start_date = graphene.String()
    end_date = graphene.String()
    snapshots = graphene.List(BalanceSnapshotType)
    calendar_days = graphene.List(CalendarDayType)
    final_balances = graphene.JSONString()
    credit_final_balances = graphene.JSONString()
    mortgage_final_balances = graphene.JSONString()
    heloc_final_balances = graphene.JSONString()
    total_final_balance = graphene.Float()
    total_credit_balance = graphene.Float()
    total_mortgage_balance = graphene.Float()
    total_heloc_balance = graphene.Float()
    net_final_balance = graphene.Float()
    total_income = graphene.Float()
    total_expenses = graphene.Float()
    net_change = graphene.Float()


class PaymentPlanType(graphene.ObjectType):
    """Represents a payment plan."""
    strategy = graphene.JSONString()
    discretionary_funds = graphene.Float()
    total_interest = graphene.Float()
    interest_charged = graphene.Float()
    interest_earned = graphene.Float()
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

    def resolve_upcoming_bills_30_days(self, info):
        bills = self.upcoming_bills_30_days
        if not bills:
            return []
        return [bill if isinstance(bill, BillType) else _bill_to_type(bill) for bill in bills]

    def resolve_upcoming_income_30_days(self, info):
        incomes = self.upcoming_income_30_days
        if not incomes:
            return []
        return [i if isinstance(i, IncomeSourceType) else _income_to_type(i) for i in incomes]


# ==================== New Enhancement Types ====================

class SafeToSpendType(graphene.ObjectType):
    """Discretionary funds over the next two pay periods."""
    safe_to_spend = graphene.Float()
    total_checking = graphene.Float()
    committed_bills = graphene.Float()
    upcoming_income = graphene.Float()
    next_income_date = graphene.String()
    horizon_date = graphene.String()


class NetWorthSnapshotType(graphene.ObjectType):
    """A point-in-time net worth snapshot."""
    snapshot_date = graphene.String()
    total_assets = graphene.Float()
    total_liabilities = graphene.Float()
    net_worth = graphene.Float()


class BillPaymentHistoryType(graphene.ObjectType):
    """A recorded bill payment."""
    bill_name = graphene.String()
    amount_paid = graphene.Float()
    source_bank = graphene.String()
    source_account = graphene.String()
    payment_date = graphene.String()


class DebtPayoffStrategyType(graphene.ObjectType):
    """Result of a debt payoff strategy simulation."""
    strategy = graphene.String()
    months_to_payoff = graphene.Int()
    total_interest_paid = graphene.Float()
    total_paid = graphene.Float()
    payoff_order = graphene.List(graphene.String)
    monthly_breakdown = graphene.JSONString()
    pays_off = graphene.Boolean()
    remaining_balance = graphene.Float()


class DebtPayoffComparisonType(graphene.ObjectType):
    """Comparison of debt payoff strategies."""
    minimum = graphene.Field(DebtPayoffStrategyType)
    avalanche = graphene.Field(DebtPayoffStrategyType)
    snowball = graphene.Field(DebtPayoffStrategyType)


class LatePaymentType(graphene.ObjectType):
    """A payment the simulation could not make on its due date."""
    date = graphene.String()
    name = graphene.String()
    amount = graphene.Float()


class OutcomeSummaryType(graphene.ObjectType):
    """Headline numbers for one simulated plan (see payment_insights.summarize_simulation)."""
    ending_cash = graphene.Float()
    ending_debt = graphene.Float()
    net_position = graphene.Float(description="Cash minus all debt at the end of the window")
    net_change = graphene.Float(description="Change in cash minus debt over the window")
    lowest_checking = graphene.Float()
    lowest_checking_date = graphene.String()
    lowest_checking_account = graphene.String()
    interest_charged = graphene.Float()
    interest_earned = graphene.Float()
    payments_on_time = graphene.Int()
    late_payments = graphene.List(LatePaymentType)
    pending_deferred_interest = graphene.Float(
        description="Deferred interest unpaid 0% promos would trigger after the window")


class WhatIfResultType(graphene.ObjectType):
    """Result of a what-if scenario."""
    baseline_final_balance = graphene.Float()
    scenario_final_balance = graphene.Float()
    difference = graphene.Float()
    baseline_snapshots = graphene.JSONString()
    scenario_snapshots = graphene.JSONString()
    baseline = graphene.Field(OutcomeSummaryType)
    scenario = graphene.Field(OutcomeSummaryType)
    changes = graphene.List(graphene.String, description="Plain-language differences vs. the current plan")


class InsightType(graphene.ObjectType):
    """One ranked recommendation. impact > 0 = money saved/gained, < 0 = at risk."""
    severity = graphene.String(description="urgent | warning | savings | tip | good")
    category = graphene.String(description="late | cushion | promo | timing | group | optimizer | status")
    title = graphene.String()
    detail = graphene.String()
    impact = graphene.Float()
    date = graphene.String()


class BillTimingType(graphene.ObjectType):
    """When to pay one upcoming bill and what paying early/late changes."""
    name = graphene.String()
    kind = graphene.String(description="bill | floating | credit | mortgage | heloc | group")
    due_date = graphene.String()
    amount = graphene.Float()
    estimated = graphene.Boolean()
    source_bank = graphene.String()
    source_account = graphene.String()
    status = graphene.String(description="on_time | late | already_paid (paying on the due date)")
    plan_status = graphene.String(description="Same, when following the optimized plan")
    funded_by = graphene.String(description="Paycheck date on/before the due date that covers it")
    pay_early_date = graphene.String()
    days_early = graphene.Int()
    early_savings = graphene.Float()
    cushion_if_early = graphene.Float(description="Lowest balance left in the source account if paid early")
    shortfall = graphene.Float()
    fixes = graphene.List(graphene.String)
    advice = graphene.String()


class GroupPayoffType(graphene.ObjectType):
    months = graphene.Int()
    interest = graphene.Float()
    pays_off = graphene.Boolean()
    extra_monthly = graphene.Float()


class GroupMemberOutlookType(graphene.ObjectType):
    account_name = graphene.String()
    balance = graphene.Float()
    apr = graphene.Float()
    allocation_method = graphene.String()
    next_payment_share = graphene.Float()
    monthly_interest = graphene.Float()


class GroupOutlookType(graphene.ObjectType):
    """How a bill group's payment is split and what a different split would change."""
    group_name = graphene.String()
    payment = graphene.Float()
    total_balance = graphene.Float()
    monthly_interest = graphene.Float()
    members = graphene.List(GroupMemberOutlookType)
    current = graphene.Field(GroupPayoffType)
    highest_rate_first = graphene.Field(GroupPayoffType)
    with_extra = graphene.Field(GroupPayoffType)
    reallocation_savings = graphene.Float()
    highest_rate_member = graphene.String()
    suggested_fixed_amount = graphene.Float()


class PromoOutlookType(graphene.ObjectType):
    card = graphene.String()
    bank = graphene.String()
    promo_name = graphene.String()
    balance = graphene.Float()
    expires = graphene.String()
    days_left = graphene.Int()
    monthly_needed = graphene.Float()
    scheduled_in_window = graphene.Float()
    on_track = graphene.Boolean(description="null when the promo expires after the analysis window")
    shortfall = graphene.Float()
    interest_at_risk = graphene.Float()
    apr_after = graphene.Float()


class OptimizerMoveType(graphene.ObjectType):
    date = graphene.String()
    type = graphene.String()
    title = graphene.String()
    why = graphene.String()
    description = graphene.String()
    amount = graphene.Float()


class PaymentInsightsType(graphene.ObjectType):
    """Paying on due dates vs. the optimized plan, with ranked recommendations."""
    start_date = graphene.String()
    end_date = graphene.String()
    days = graphene.Int()
    headline = graphene.String()
    on_due_date = graphene.Field(OutcomeSummaryType)
    optimized = graphene.Field(OutcomeSummaryType)
    net_benefit = graphene.Float()
    changes = graphene.List(graphene.String)
    insights = graphene.List(InsightType)
    bill_timing = graphene.List(BillTimingType)
    groups = graphene.List(GroupOutlookType)
    promos = graphene.List(PromoOutlookType)
    optimizer_moves = graphene.List(OptimizerMoveType)


class BillGroupMemberType(graphene.ObjectType):
    """A single member (credit/loan account) in a bill group."""
    bank_name = graphene.String()
    account_name = graphene.String()
    allocation_method = graphene.String()
    fixed_amount = graphene.Float()
    balance = graphene.Float()
    interest_rate = graphene.Float()


class BillGroupType(graphene.ObjectType):
    """Represents a bill group / bundled payment."""
    group_name = graphene.String()
    total_payment = graphene.Float()
    due_date = graphene.Int()
    frequency = graphene.String()
    group_type = graphene.String()
    preferred_source_bank = graphene.String()
    preferred_source_account = graphene.String()
    is_paid_this_period = graphene.Boolean()
    members = graphene.List(BillGroupMemberType)
    total_balance = graphene.Float()
    member_count = graphene.Int()


# ==================== Queries ====================

class Query(ExtQuery, graphene.ObjectType):
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
    payment_insights = graphene.Field(
        PaymentInsightsType,
        days=graphene.Int(default_value=90),
        description="Plain-language payment recommendations: on-time vs. early vs. optimized"
    )
    balance_history = graphene.List(
        BalanceHistoryType,
        bank_name=graphene.String(required=True),
        account_name=graphene.String(required=True),
        limit=graphene.Int(default_value=50),
        description="Get balance history for an account"
    )

    # Credit Payment Queries
    credit_payments_due = graphene.List(
        CreditPaymentDueType,
        description="Get all credit card payments that are due (accounts with balance > 0)"
    )

    # SimpleFIN Queries
    simplefin_status = graphene.Field(
        SimplefinStatusType,
        description="Get SimpleFIN Bridge connection status"
    )
    simplefin_accounts = graphene.List(
        SimplefinAccountType,
        description="Fetch live accounts from SimpleFIN Bridge (requires active connection)"
    )
    simplefin_synced_accounts = graphene.List(
        SimplefinSyncedAccountType,
        description="Get list of local accounts that are mapped to SimpleFIN"
    )
    simplefin_transactions = graphene.List(
        SimplefinTransactionType,
        bank_name=graphene.String(required=True),
        account_name=graphene.String(required=True),
        days=graphene.Int(default_value=30),
        description="Fetch recent transactions from SimpleFIN for a synced account"
    )
    credit_promo_offers = graphene.List(
        PromoOfferType,
        bank_name=graphene.String(required=True),
        account_name=graphene.String(required=True),
        description="Get all promo offers for a credit account"
    )

    # ── New Enhancement Queries ──
    safe_to_spend = graphene.Field(SafeToSpendType, description="How much is safe to spend before next income")
    net_worth_history = graphene.List(NetWorthSnapshotType, limit=graphene.Int(default_value=90), description="Net worth history snapshots")
    bill_payment_history = graphene.List(
        BillPaymentHistoryType,
        bill_name=graphene.String(),
        limit=graphene.Int(default_value=50),
        description="Get payment history for a specific bill or all bills"
    )
    debt_payoff_comparison = graphene.Field(
        DebtPayoffComparisonType,
        extra_monthly=graphene.Float(default_value=0),
        description="Compare debt payoff strategies"
    )
    what_if_scenario = graphene.Field(
        WhatIfResultType,
        modifications=graphene.JSONString(required=True),
        days=graphene.Int(default_value=90),
        description="Run a what-if scenario"
    )

    # Bill Group Queries
    all_bill_groups = graphene.List(
        BillGroupType,
        description="Get all bill groups (bundled payments)"
    )
    bill_group = graphene.Field(
        BillGroupType,
        group_name=graphene.String(required=True),
        description="Get a specific bill group by name"
    )

    def resolve_simplefin_status(self, info):
        """Get SimpleFIN connection status."""
        from models.simplefin import get_simplefin_connection, get_simplefin_mappings
        conn = get_simplefin_connection()
        if not conn:
            return SimplefinStatusType(
                is_connected=False,
                created_at=None,
                last_sync_at=None,
                mapped_account_count=0,
            )
        mappings = get_simplefin_mappings()
        return SimplefinStatusType(
            is_connected=True,
            created_at=conn.get('created_at'),
            last_sync_at=conn.get('last_sync_at'),
            mapped_account_count=len(mappings),
        )

    def resolve_simplefin_accounts(self, info):
        """Fetch live accounts from SimpleFIN and enrich with mapping info."""
        from models.simplefin import (
            get_simplefin_connection, get_simplefin_mappings, SimplefinClient
        )
        conn = get_simplefin_connection()
        if not conn:
            return []

        try:
            sfin_accounts = SimplefinClient.fetch_accounts(conn['access_url'])
        except ValueError:
            return []

        mappings = get_simplefin_mappings()
        result = []
        for acc in sfin_accounts:
            mapping = mappings.get(acc.id, {})
            bal_date = None
            if acc.balance_date:
                try:
                    bal_date = datetime.fromtimestamp(acc.balance_date, tz=None).isoformat()
                except Exception:
                    pass
            result.append(SimplefinAccountType(
                id=acc.id,
                name=acc.name,
                org_name=acc.org.name,
                org_domain=acc.org.domain,
                currency=acc.currency,
                balance=acc.balance,
                available_balance=acc.available_balance,
                balance_date=bal_date,
                mapped_bank_name=mapping.get('bank_name'),
                mapped_account_name=mapping.get('account_name'),
                mapped_account_type=mapping.get('account_type'),
            ))
        return result

    def resolve_simplefin_synced_accounts(self, info):
        """Get list of local accounts that are mapped to SimpleFIN."""
        from models.simplefin import get_simplefin_connection, get_simplefin_mappings
        conn = get_simplefin_connection()
        if not conn:
            return []
        mappings = get_simplefin_mappings()
        return [
            SimplefinSyncedAccountType(
                bank_name=m.get('bank_name'),
                account_name=m.get('account_name'),
                account_type=m.get('account_type'),
                sfin_name=m.get('sfin_name'),
                sfin_org=m.get('sfin_org'),
            )
            for m in mappings.values()
        ]

    def resolve_simplefin_transactions(self, info, bank_name, account_name, days=30):
        """Fetch recent transactions from SimpleFIN for a synced account."""
        from models.simplefin import get_simplefin_connection, get_simplefin_mappings, SimplefinClient
        import time

        conn = get_simplefin_connection()
        if not conn:
            return []

        mappings = get_simplefin_mappings()
        # Find the SimpleFIN account ID that maps to this local account
        sfin_id = None
        for sid, m in mappings.items():
            if m.get('bank_name') == bank_name and m.get('account_name') == account_name:
                sfin_id = sid
                break

        if not sfin_id:
            return []

        # Fetch with transactions (start_date = days ago)
        start_ts = int(time.time()) - (days * 86400)
        try:
            accounts = SimplefinClient.fetch_accounts(conn['access_url'], start_date=start_ts)
        except Exception:
            return []

        # Find the matching account
        for acc in accounts:
            if acc.id == sfin_id:
                result = []
                for txn in acc.transactions:
                    posted_date = ''
                    if txn.posted:
                        try:
                            from datetime import datetime as dt, timezone as tz
                            posted_date = dt.fromtimestamp(txn.posted, tz.utc).strftime('%Y-%m-%d')
                        except Exception:
                            posted_date = str(txn.posted)
                    result.append(SimplefinTransactionType(
                        id=txn.id,
                        posted=posted_date,
                        amount=txn.amount,
                        description=txn.description,
                        payee=txn.payee,
                        memo=txn.memo,
                    ))
                # Sort newest first
                result.sort(key=lambda t: t.posted or '', reverse=True)
                return result
        return []

    def resolve_credit_promo_offers(self, info, bank_name, account_name):
        """Get all promo offers for a credit account."""
        manager = info.context.get('manager')
        if not manager:
            return []

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return []

        acc = bank.credit_accounts.get(account_name)
        if not acc:
            return []

        result = []
        for p in getattr(acc, 'active_promos', []):
            promo_bal = acc.promo_balance.get(p.promo_name, 0.0)
            result.append(PromoOfferType(
                promo_name=p.promo_name,
                months_interest_free=p.months_interest_free,
                purchase_limit=p.purchase_limit,
                start_date=p.start_date.isoformat() if p.start_date else None,
                end_date=p.end_date.isoformat() if p.end_date else None,
                amount_used=p.amount_used,
                promo_balance=promo_bal,
                is_active=p.is_active,
                days_remaining=p.days_remaining,
                interest_charged=p.interest_charged,
            ))
        return result

    def resolve_credit_payments_due(self, info):
        """Get credit card payments due across all banks."""
        manager = info.context.get('manager')
        if not manager:
            return []

        # Build set of grouped account keys so we can exclude them
        grouped_keys = manager.get_grouped_account_keys() if hasattr(manager, 'get_grouped_account_keys') else set()

        payments = []
        for bank in manager.banks:
            for name, acc in bank.credit_accounts.items():
                # Skip accounts managed by a bill group
                if (bank.name, name) in grouped_keys:
                    continue
                if acc.balance > 0:
                    # Find the linked bill for this credit account
                    linked_bill = None
                    for bill in manager.bills:
                        if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'credit':
                            if bill.linked_bank_name == bank.name and bill.linked_account.account_name == name:
                                linked_bill = bill
                                break

                    is_paid = linked_bill.is_paid_this_period if linked_bill else False
                    last_amount = None
                    last_date = None
                    if linked_bill and linked_bill.payment_history:
                        last_payment = linked_bill.payment_history[-1]
                        last_amount = last_payment.get('amount_paid')
                        pd = last_payment.get('date')
                        last_date = pd.isoformat() if hasattr(pd, 'isoformat') else str(pd) if pd else None

                    key = f"{bank.name}:{name}"
                    payments.append(CreditPaymentDueType(
                        id=key,
                        bank_name=bank.name,
                        account_name=name,
                        balance=acc.balance,
                        minimum_payment=acc.calculate_minimum_payment(),
                        payment_due_date=acc.payment_due_date,
                        interest_rate=acc.interest_rate,
                        credit_limit=acc.credit_limit,
                        available_credit=acc.available_credit,
                        status=acc.status.value if hasattr(acc.status, 'value') else str(acc.status),
                        is_paid_this_period=is_paid,
                        last_payment_amount=last_amount,
                        last_payment_date=last_date,
                    ))
        return payments

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
        """Get all bills (excludes GroupLinkedBill — use allBillGroups for those)."""
        manager = info.context.get('manager')
        if manager:
            return [_bill_to_type(bill) for bill in manager.bills if not isinstance(bill, GroupLinkedBill)]
        return []

    def resolve_upcoming_bills(self, info, days):
        """Get upcoming bills (excludes GroupLinkedBill — use allBillGroups for those)."""
        manager = info.context.get('manager')
        if manager:
            return [_bill_to_type(bill) for bill in manager.get_upcoming_bills(days) if not isinstance(bill, GroupLinkedBill)]
        return []

    def resolve_all_income(self, info):
        """Get all income sources."""
        manager = info.context.get('manager')
        if manager:
            return [_income_to_type(income) for income in manager.income_sources]
        return []

    def resolve_upcoming_income(self, info, days):
        """Get upcoming income."""
        manager = info.context.get('manager')
        if manager:
            return [_income_to_type(income) for income in manager.get_upcoming_income(days)]
        return []

    def resolve_snapshot(self, info):
        """Get current financial snapshot."""
        manager = info.context.get('manager')
        if not manager:
            return None

        # Keep the net worth history current (recorded at most once per day)
        manager.record_net_worth_snapshot()

        # Zero-balance credit cards have a $0 linked bill — not worth listing
        upcoming = [
            b for b in manager.get_upcoming_bills(30)
            if not (isinstance(b, AccountLinkedBill) and b.effective_amount <= 0)
        ]
        return FinancialSnapshotType(
            timestamp=datetime.now().isoformat(),
            banks=manager.banks,
            total_assets=manager.get_total_assets(),
            total_liabilities=manager.get_total_liabilities(),
            net_worth=manager.get_net_worth(),
            upcoming_bills_30_days=upcoming,
            upcoming_income_30_days=manager.get_upcoming_income(30)
        )

    def resolve_balance_on_date(self, info, **kwargs):
        """Get balance on specific date."""
        manager = info.context.get('manager')
        if not manager:
            return None
        target_date = _parse_date(kwargs['date'])
        return manager.get_balance_on_date(target_date)

    def resolve_projection(self, info, days):
        """Get projection."""
        manager = info.context.get('manager')
        if not manager:
            return None

        end_date = date.today() + timedelta(days=days)
        start_bank_total = sum(acc.balance for bank in manager.banks for acc in bank.get_all_accounts())
        result = manager.project_balances(end_date=end_date)

        snapshots = []
        for snap in result['snapshots']:
            bank_total = sum(snap['balances'].values())
            credit_total = sum(snap.get('credit_balances', {}).values())
            mortgage_total = sum(snap.get('mortgage_balances', {}).values())
            heloc_total = sum(snap.get('heloc_balances', {}).values())
            net = bank_total - credit_total - mortgage_total - heloc_total
            snapshots.append(BalanceSnapshotType(
                date=snap['date'].isoformat(),
                balances=snap['balances'],
                credit_balances=snap.get('credit_balances', {}),
                mortgage_balances=snap.get('mortgage_balances', {}),
                heloc_balances=snap.get('heloc_balances', {}),
                total=bank_total,
                net_total=net,
            ))

        # Build calendar days: group cash_flow events by date and pair with balances
        from collections import defaultdict
        events_by_date = defaultdict(list)
        for cf in result['cash_flow']:
            cf_date = cf['date'].isoformat() if hasattr(cf['date'], 'isoformat') else str(cf['date'])
            # Skip "already paid" markers — they're internal bookkeeping
            if cf['type'] in ('BILL_ALREADY_PAID', 'MORTGAGE_ALREADY_PAID', 'HELOC_ALREADY_PAID', 'BILL_GROUP_ALREADY_PAID'):
                continue
            status = 'ok'
            if cf['type'] in ('BILL_DEFERRED', 'CREDIT_PAYMENT_DEFERRED', 'MORTGAGE_DEFERRED', 'HELOC_PAYMENT_DEFERRED', 'BILL_GROUP_DEFERRED'):
                status = 'deferred'
            # Optimization events use from_bank/from_account instead of bank/account
            source_bank = cf.get('bank', cf.get('from_bank', ''))
            source_account = cf.get('account', cf.get('from_account', ''))
            events_by_date[cf_date].append(CalendarEventType(
                event_type=cf['type'],
                description=cf.get('description', ''),
                amount=cf['amount'],
                source_bank=source_bank,
                source_account=source_account,
                status=status,
            ))

        # Build a snapshot lookup by date
        snap_lookup = {}
        for snap in result['snapshots']:
            snap_date = snap['date'].isoformat() if hasattr(snap['date'], 'isoformat') else str(snap['date'])
            snap_lookup[snap_date] = snap

        calendar_days = []
        for snap in result['snapshots']:
            snap_date = snap['date'].isoformat() if hasattr(snap['date'], 'isoformat') else str(snap['date'])
            day_events = events_by_date.get(snap_date, [])
            if day_events:  # Only include days that have events
                bank_total = sum(snap['balances'].values())
                credit_total = sum(snap.get('credit_balances', {}).values())
                mortgage_total = sum(snap.get('mortgage_balances', {}).values())
                heloc_total = sum(snap.get('heloc_balances', {}).values())
                net = bank_total - credit_total - mortgage_total - heloc_total
                calendar_days.append(CalendarDayType(
                    date=snap_date,
                    events=day_events,
                    balances=snap['balances'],
                    credit_balances=snap.get('credit_balances', {}),
                    mortgage_balances=snap.get('mortgage_balances', {}),
                    heloc_balances=snap.get('heloc_balances', {}),
                    total=bank_total,
                    net_total=net,
                ))

        # Calculate totals
        total_income = sum(cf['amount'] for cf in result['cash_flow'] if cf['type'] == 'INCOME')
        expense_types = ('BILL_PAYMENT', 'MORTGAGE_PAYMENT', 'CREDIT_PAYMENT', 'HELOC_PAYMENT',
                         'BILL_GROUP_PAYMENT', 'EXTRA_CREDIT_PAYMENT', 'PROMO_PAYOFF')
        total_expenses = sum(-cf['amount'] for cf in result['cash_flow']
                             if cf['type'] in expense_types)

        # Final balances for all account types
        final_bank = result['final_balances']
        final_credit = result.get('credit_final_balances', {})
        final_mortgage = result.get('mortgage_final_balances', {})
        final_heloc = result.get('heloc_final_balances', {})
        total_bank = sum(final_bank.values())
        total_credit = sum(final_credit.values())
        total_mortgage = sum(final_mortgage.values())
        total_heloc = sum(final_heloc.values())
        net_final = total_bank - total_credit - total_mortgage - total_heloc
        # Change in cash (checking + savings). Summing cash-flow entries would
        # count internal transfers (sweeps, HELOC parking) as income.
        net_change = total_bank - start_bank_total

        return ProjectionType(
            start_date=result['start_date'].isoformat(),
            end_date=result['end_date'].isoformat(),
            snapshots=snapshots,
            calendar_days=calendar_days,
            final_balances=final_bank,
            credit_final_balances=final_credit,
            mortgage_final_balances=final_mortgage,
            heloc_final_balances=final_heloc,
            total_final_balance=total_bank,
            total_credit_balance=total_credit,
            total_mortgage_balance=total_mortgage,
            total_heloc_balance=total_heloc,
            net_final_balance=net_final,
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

        # Convert any date objects in strategy to ISO strings for JSON
        serializable_strategy = {}
        for key, val in plan.strategy.items():
            if isinstance(val, dict):
                entry = {}
                for k, v in val.items():
                    entry[k] = v.isoformat() if isinstance(v, date) else v
                serializable_strategy[key] = entry
            else:
                serializable_strategy[key] = val.isoformat() if isinstance(val, date) else val

        return PaymentPlanType(
            strategy=serializable_strategy,
            discretionary_funds=plan.final_discretionary,
            total_interest=plan.total_interest_paid,
            interest_charged=plan.total_interest_paid,
            interest_earned=plan.estimated_interest_earned,
            total_fees=plan.total_fees,
            violations=plan.violations
        )

    def resolve_payment_insights(self, info, days=90):
        """Payment recommendations for the next `days` days (capped at 365)."""
        manager = info.context.get('manager')
        if not manager:
            return None
        out = manager.payment_insights(days=max(7, min(days, 365)))
        comparison = out.pop('comparison')
        return {**out, 'on_due_date': comparison['on_due_date'], 'optimized': comparison['optimized'],
                'net_benefit': comparison['net_benefit'], 'changes': comparison['changes']}

    def resolve_balance_history(self, info, bank_name, account_name, limit=50):
        """Get balance history for an account."""
        try:
            from models.database import get_session, BankModel, BankAccountModel, CreditAccountModel
            from sqlalchemy import text
            session = get_session()
            try:
                # Check if balance_history table exists
                result = session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='balance_history'"
                )).fetchone()
                if not result:
                    return []

                rows = session.execute(text(
                    "SELECT bank_name, account_name, account_type, balance, previous_balance, recorded_at, notes "
                    "FROM balance_history WHERE bank_name = :bn AND account_name = :an "
                    "ORDER BY recorded_at DESC LIMIT :lim"
                ), {"bn": bank_name, "an": account_name, "lim": limit}).fetchall()
                return [
                    BalanceHistoryType(
                        bank_name=r[0], account_name=r[1], account_type=r[2],
                        balance=r[3], previous_balance=r[4], recorded_at=r[5], notes=r[6]
                    )
                    for r in rows
                ]
            finally:
                session.close()
        except Exception:
            return []

    # ── New Enhancement Resolvers ──

    def resolve_safe_to_spend(self, info):
        """Calculate safe-to-spend amount."""
        manager = info.context.get('manager')
        if not manager:
            return SafeToSpendType(safe_to_spend=0, total_checking=0, committed_bills=0,
                                   upcoming_income=0, next_income_date='', horizon_date='')
        result = manager.calculate_safe_to_spend()
        return SafeToSpendType(**result)

    def resolve_net_worth_history(self, info, limit=90):
        """Get net worth history snapshots."""
        try:
            from models.database import get_session
            from sqlalchemy import text
            session = get_session()
            try:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS net_worth_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_assets REAL NOT NULL,
                        total_liabilities REAL NOT NULL,
                        net_worth REAL NOT NULL,
                        snapshot_date TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))
                session.commit()
                rows = session.execute(text(
                    "SELECT snapshot_date, total_assets, total_liabilities, net_worth "
                    "FROM net_worth_snapshots ORDER BY snapshot_date DESC LIMIT :lim"
                ), {"lim": limit}).fetchall()
                return [
                    NetWorthSnapshotType(
                        snapshot_date=r[0], total_assets=r[1],
                        total_liabilities=r[2], net_worth=r[3]
                    )
                    for r in reversed(rows)
                ]
            finally:
                session.close()
        except Exception:
            return []

    def resolve_bill_payment_history(self, info, bill_name=None, limit=50):
        """Get bill payment history."""
        try:
            from models.database import get_session
            from sqlalchemy import text
            session = get_session()
            try:
                if bill_name:
                    rows = session.execute(text("""
                        SELECT b.bill_name, bp.amount_paid, bp.source_bank, bp.source_account, bp.payment_date
                        FROM bill_payments bp
                        JOIN bills b ON b.id = bp.bill_id
                        WHERE b.bill_name = :name
                        ORDER BY bp.payment_date DESC LIMIT :lim
                    """), {"name": bill_name, "lim": limit}).fetchall()
                else:
                    rows = session.execute(text("""
                        SELECT b.bill_name, bp.amount_paid, bp.source_bank, bp.source_account, bp.payment_date
                        FROM bill_payments bp
                        JOIN bills b ON b.id = bp.bill_id
                        ORDER BY bp.payment_date DESC LIMIT :lim
                    """), {"lim": limit}).fetchall()
                return [
                    BillPaymentHistoryType(
                        bill_name=r[0], amount_paid=r[1], source_bank=r[2],
                        source_account=r[3], payment_date=str(r[4])
                    )
                    for r in rows
                ]
            finally:
                session.close()
        except Exception:
            return []

    def resolve_debt_payoff_comparison(self, info, extra_monthly=0):
        """Compare debt payoff strategies."""
        manager = info.context.get('manager')
        if not manager:
            return None
        from models.debt_estimator import DebtPayoffEstimator, DebtInfo

        # Build set of grouped account keys
        grouped_keys = manager.get_grouped_account_keys() if hasattr(manager, 'get_grouped_account_keys') else set()

        # Build a set of paid credit account keys from linked bills
        paid_credit_keys = set()
        for bill in manager.bills:
            if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'credit':
                if bill.is_paid_this_period:
                    paid_credit_keys.add(f"{bill.linked_bank_name}:{bill.linked_account.account_name}")

        debts = []
        for bank in manager.banks:
            for credit in bank.get_all_credit_accounts():
                if credit.balance <= 0:
                    continue
                key = f"{bank.name}:{credit.account_name}"
                # Skip paid debts
                if key in paid_credit_keys:
                    continue
                # Skip grouped accounts — added via bill group below
                if (bank.name, credit.account_name) in grouped_keys:
                    continue
                debts.append(DebtInfo(
                    name=key,
                    balance=credit.balance,
                    interest_rate=credit.interest_rate,
                    minimum_payment=credit.calculate_minimum_payment()
                ))
            # Exclude mortgages — 30-year terms break the estimator
            for heloc in bank.get_all_heloc_accounts():
                if heloc.balance > 0 and not getattr(heloc, 'is_paid_this_period', False):
                    debts.append(DebtInfo(
                        name=f"{bank.name}:{heloc.account_name}",
                        balance=heloc.balance,
                        interest_rate=heloc.interest_rate,
                        minimum_payment=heloc.calculate_minimum_payment()
                    ))

        # Add bill groups as single grouped debts
        for group in manager.bill_groups:
            if group.is_paid_this_period:
                continue
            total_balance = group.get_total_balance(manager.banks)
            if total_balance <= 0:
                continue
            # Compute weighted average interest rate from members
            details = group.get_member_details(manager.banks)
            weighted_rate = 0.0
            if total_balance > 0:
                for d in details:
                    if d['balance'] > 0:
                        weighted_rate += d['interest_rate'] * (d['balance'] / total_balance)
            debts.append(DebtInfo(
                name=f"Group:{group.group_name}",
                balance=total_balance,
                interest_rate=weighted_rate,
                minimum_payment=group.total_payment
            ))

        if not debts:
            return None
        results = DebtPayoffEstimator.estimate(debts, extra_monthly)
        def _to_type(r):
            return DebtPayoffStrategyType(
                strategy=r.strategy,
                months_to_payoff=r.months_to_payoff,
                total_interest_paid=r.total_interest_paid,
                total_paid=r.total_paid,
                payoff_order=r.payoff_order,
                monthly_breakdown=r.monthly_breakdown,
                pays_off=getattr(r, 'pays_off', True),
                remaining_balance=getattr(r, 'remaining_balance', 0.0),
            )
        return DebtPayoffComparisonType(
            minimum=_to_type(results['minimum']),
            avalanche=_to_type(results['avalanche']),
            snowball=_to_type(results['snowball']),
        )

    def resolve_what_if_scenario(self, info, modifications, days=90):
        """Run a what-if scenario."""
        manager = info.context.get('manager')
        if not manager:
            return None
        import json
        mods = json.loads(modifications) if isinstance(modifications, str) else modifications
        # Cap days at 365 to prevent extremely long simulations
        days = min(days, 365)
        result = manager.run_what_if_scenario(mods, days)

        def _plain(snaps):
            # Round-trip through json to turn dates (incl. nested) into strings
            return json.loads(json.dumps(snaps, default=str))

        return WhatIfResultType(
            baseline_final_balance=result['baseline_final_balance'],
            scenario_final_balance=result['scenario_final_balance'],
            difference=result['difference'],
            baseline_snapshots=_plain(result['baseline_snapshots']),
            scenario_snapshots=_plain(result['scenario_snapshots']),
            baseline=result['baseline_summary'],
            scenario=result['scenario_summary'],
            changes=result['changes'],
        )

    def resolve_all_bill_groups(self, info):
        """Get all bill groups."""
        manager = info.context.get('manager')
        if not manager:
            return []
        return [_group_to_type(g, manager.banks) for g in manager.get_all_bill_groups()]

    def resolve_bill_group(self, info, group_name):
        """Get a specific bill group by name."""
        manager = info.context.get('manager')
        if not manager:
            return None
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if group:
            return _group_to_type(group, manager.banks)
        return None


def _group_to_type(group, banks):
    """Convert a BillGroup to BillGroupType."""
    details = group.get_member_details(banks)
    members = [
        BillGroupMemberType(
            bank_name=d['bank_name'],
            account_name=d['account_name'],
            allocation_method=d['allocation_method'],
            fixed_amount=d['fixed_amount'],
            balance=d['balance'],
            interest_rate=d['interest_rate'],
        )
        for d in details
    ]
    return BillGroupType(
        group_name=group.group_name,
        total_payment=group.total_payment,
        due_date=group.due_date,
        frequency=group.frequency.value if hasattr(group.frequency, 'value') else str(group.frequency),
        group_type=group.group_type,
        preferred_source_bank=group.preferred_source_bank,
        preferred_source_account=group.preferred_source_account,
        is_paid_this_period=group.is_paid_this_period,
        members=members,
        total_balance=group.get_total_balance(banks),
        member_count=len(group.members),
    )


# ==================== Mutations ====================

def _find_bank(manager, name):
    return next((b for b in manager.banks if b.name == name), None)


def _take_payment(manager, src_bank: str, src_acct: str, amount: float, description: str, pay_date):
    """
    Move money out of a payment source. A checking/savings source is withdrawn
    from; a credit card source is charged. No source (both empty) moves nothing.

    Returns an undo callable that restores the source if a later step fails.
    Raises ValueError on an unknown source or insufficient funds/credit.
    """
    if not src_bank and not src_acct:
        return lambda: None
    if not (src_bank and src_acct):
        raise ValueError("Specify both a source bank and a source account")
    bank = _find_bank(manager, src_bank)
    if not bank:
        raise ValueError(f"Source bank '{src_bank}' not found")
    if amount <= 0:
        return lambda: None

    if src_acct in bank.accounts:
        acc = bank.accounts[src_acct]
        move = acc.withdraw
    elif src_acct in bank.credit_accounts:
        acc = bank.credit_accounts[src_acct]
        move = acc.make_purchase
    else:
        raise ValueError(f"Source account '{src_acct}' not found in '{src_bank}'")

    before = (acc.balance, getattr(acc, 'regular_balance', None), len(acc.transaction_history))
    move(amount, description=description, transaction_date=pay_date)

    def undo():
        acc.balance = before[0]
        if before[1] is not None:
            acc.regular_balance = before[1]
        del acc.transaction_history[before[2]:]

    return undo


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
            manager.save_to_database()
            return CreateBank(bank=bank, success=True, message=f"Bank '{name}' created")
        except Exception as e:
            return CreateBank(success=False, message=str(e))


class CreateAccount(graphene.Mutation):
    """Create a checking/savings account or a credit card in a bank."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        account_type = graphene.String(default_value="checking")
        balance = graphene.Float(default_value=0.0)
        interest_rate = graphene.Float(default_value=0.0)
        credit_limit = graphene.Float()
        payment_due_date = graphene.Int()
        statement_date = graphene.Int()
        interest_accrual_date = graphene.Int()

    account = graphene.Field(BankAccountType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, account_type, balance, interest_rate,
               credit_limit=None, payment_due_date=None, statement_date=None, interest_accrual_date=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateAccount(success=False, message="Manager not available")

        try:
            bank = _find_bank(manager, bank_name)
            if not bank:
                return CreateAccount(success=False, message=f"Bank '{bank_name}' not found")
            for day, label in ((payment_due_date, "Payment due day"), (statement_date, "Statement day"),
                               (interest_accrual_date, "Interest day")):
                if day is not None and not (1 <= day <= 31):
                    return CreateAccount(success=False, message=f"{label} must be between 1 and 31")

            if account_type == "credit":
                if not credit_limit or credit_limit <= 0:
                    return CreateAccount(success=False, message="A credit limit greater than 0 is required for credit cards")
                if balance < 0 or balance > credit_limit:
                    return CreateAccount(success=False, message="Balance owed must be between 0 and the credit limit")
                card = bank.add_credit_account(account_name, credit_limit, interest_rate,
                                               payment_due_date=payment_due_date, statement_date=statement_date)
                card.balance = balance
                card.regular_balance = balance
                account = BankAccountType(id=account_name, account_name=account_name, account_type="credit",
                                          balance=balance, interest_rate=interest_rate)
            elif account_type in ("checking", "savings"):
                acc = bank.add_account(account_type, account_name, balance, interest_rate, interest_accrual_date)
                account = BankAccountType(id=account_name, account_name=account_name,
                                          account_type=acc.account_type.value, balance=acc.balance,
                                          interest_rate=acc.interest_rate,
                                          interest_accrual_date=acc.interest_accrual_date)
            else:
                return CreateAccount(success=False, message=f"Unsupported account type '{account_type}'. "
                                     "Use checking, savings, or credit (HELOCs use createHelocAccount).")

            manager.save_to_database()
            return CreateAccount(account=account, success=True, message=f"Account '{account_name}' created")
        except Exception as e:
            return CreateAccount(success=False, message=str(e))


class CreateBill(graphene.Mutation):
    """Create a new fixed or floating (variable) bill."""

    class Arguments:
        bill_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        due_date = graphene.Int(required=True)
        frequency = graphene.String(default_value="monthly")
        due_month = graphene.Int()
        bill_type = graphene.String(default_value="fixed")
        min_amount = graphene.Float()
        max_amount = graphene.Float()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()
        start_date = graphene.String()

    bill = graphene.Field(BillType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, amount, due_date, frequency, due_month=None, bill_type="fixed",
               min_amount=None, max_amount=None, preferred_source_bank=None, preferred_source_account=None,
               start_date=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateBill(success=False, message="Manager not available")

        try:
            if any(b.bill_name == bill_name for b in manager.bills):
                return CreateBill(success=False, message=f"A bill named '{bill_name}' already exists")
            extra = {}
            anchor = _parse_date(start_date, "start date")
            if anchor:
                extra['start_date'] = anchor
            common = dict(
                due_date=due_date, frequency=frequency, due_month=due_month,
                preferred_source_bank=preferred_source_bank or None,
                preferred_source_account=preferred_source_account or None,
                **extra,
            )
            if bill_type == "floating":
                bill = FloatingBill(bill_name, estimated_amount=amount,
                                    min_amount=min_amount, max_amount=max_amount, **common)
            elif bill_type == "fixed":
                bill = Bill(bill_name, amount, **common)
            else:
                return CreateBill(success=False, message=f"Unsupported bill type '{bill_type}'. Use fixed or floating.")
            manager.bills.append(bill)
            manager.save_to_database()
            return CreateBill(bill=_bill_to_type(bill), success=True, message=f"Bill '{bill_name}' created")
        except Exception as e:
            return CreateBill(success=False, message=str(e))


class CreateIncomeSource(graphene.Mutation):
    """Create a new income source."""

    class Arguments:
        source_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        frequency = graphene.String(default_value="monthly")
        pay_dates = graphene.List(graphene.Int, default_value=[1])  # List of pay dates (e.g., [15, 31] for semimonthly)
        distribution = graphene.JSONString(default_value={})
        start_date = graphene.String()

    income = graphene.Field(IncomeSourceType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, source_name, amount, frequency, pay_dates, distribution, start_date=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateIncomeSource(success=False, message="Manager not available")

        try:
            if any(i.source_name == source_name for i in manager.income_sources):
                return CreateIncomeSource(success=False, message=f"An income source named '{source_name}' already exists")
            anchor = _parse_date(start_date, "start date")
            extra = {'start_date': anchor} if anchor else {}
            income = IncomeSource(source_name, amount, frequency, pay_dates, distribution or None, **extra)
            manager.income_sources.append(income)
            manager.save_to_database()
            return CreateIncomeSource(income=_income_to_type(income), success=True,
                                      message=f"Income '{source_name}' created")
        except KeyError:
            return CreateIncomeSource(success=False, message=f"Unknown frequency '{frequency}'")
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

            if account_name not in bank.accounts:
                return UpdateAccountBalance(success=False, message=f"Account '{account_name}' not found in '{bank_name}'")
            bank.update_account_balance(account_name, new_balance)
            manager.save_to_database()
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


class DeleteBank(graphene.Mutation):
    """Delete a bank."""
    class Arguments:
        name = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name):
        manager = info.context.get('manager')
        if not manager:
            return DeleteBank(success=False, message="Manager not available")
        bank = next((b for b in manager.banks if b.name == name), None)
        if not bank:
            return DeleteBank(success=False, message=f"Bank '{name}' not found")
        manager.banks.remove(bank)
        manager.save_to_database()
        return DeleteBank(success=True, message=f"Bank '{name}' deleted")


class DeleteBill(graphene.Mutation):
    """Delete a bill."""
    class Arguments:
        bill_name = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name):
        manager = info.context.get('manager')
        if not manager:
            return DeleteBill(success=False, message="Manager not available")
        bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
        if not bill:
            return DeleteBill(success=False, message=f"Bill '{bill_name}' not found")
        manager.bills.remove(bill)
        manager.save_to_database()
        return DeleteBill(success=True, message=f"Bill '{bill_name}' deleted")


class DeleteIncome(graphene.Mutation):
    """Delete an income source."""
    class Arguments:
        source_name = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, source_name):
        manager = info.context.get('manager')
        if not manager:
            return DeleteIncome(success=False, message="Manager not available")
        income = next((i for i in manager.income_sources if i.source_name == source_name), None)
        if not income:
            return DeleteIncome(success=False, message=f"Income '{source_name}' not found")
        manager.income_sources.remove(income)
        manager.save_to_database()
        return DeleteIncome(success=True, message=f"Income '{source_name}' deleted")


class UpdateCreditBalance(graphene.Mutation):
    """Update credit account balance."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        new_balance = graphene.Float(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, new_balance):
        manager = info.context.get('manager')
        if not manager:
            return UpdateCreditBalance(success=False, message="Manager not available")
        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return UpdateCreditBalance(success=False, message=f"Bank '{bank_name}' not found")
        result = bank.update_credit_balance(account_name, new_balance)
        if result:
            manager.save_to_database()
            return UpdateCreditBalance(success=True, message="Credit balance updated")
        return UpdateCreditBalance(success=False, message=f"Credit account '{account_name}' not found")


class UpdateBill(graphene.Mutation):
    """Update a bill. Omitted fields are unchanged; an empty string clears a preferred source."""
    class Arguments:
        bill_name = graphene.String(required=True)
        amount = graphene.Float()
        due_date = graphene.Int()
        frequency = graphene.String()
        due_month = graphene.Int()
        start_date = graphene.String()
        min_amount = graphene.Float()
        max_amount = graphene.Float()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, amount=None, due_date=None, frequency=None, due_month=None,
               start_date=None, min_amount=None, max_amount=None,
               preferred_source_bank=None, preferred_source_account=None):
        manager = info.context.get('manager')
        if not manager:
            return UpdateBill(success=False, message="Manager not available")
        bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
        if not bill:
            return UpdateBill(success=False, message=f"Bill '{bill_name}' not found")
        linked = isinstance(bill, (AccountLinkedBill, GroupLinkedBill))
        if linked and any(v is not None for v in (amount, due_date, frequency, due_month, min_amount, max_amount)):
            return UpdateBill(success=False, message=(
                f"'{bill_name}' is generated from its account/group — change the amount and due day there"))
        try:
            if amount is not None:
                if amount <= 0:
                    return UpdateBill(success=False, message="Amount must be positive")
                if isinstance(bill, FloatingBill):
                    bill.estimated_amount = amount
                    if not bill.has_actual_amount:
                        bill.amount = amount
                else:
                    bill.amount = amount
            if due_date is not None:
                if not (1 <= due_date <= 31):
                    return UpdateBill(success=False, message="Due day must be between 1 and 31")
                bill.due_date = due_date
            if frequency is not None:
                from models.types import BillFrequency
                bill.frequency = BillFrequency[frequency.upper()]
            if due_month is not None:
                if not (1 <= due_month <= 12):
                    return UpdateBill(success=False, message="Due month must be between 1 and 12")
                bill.due_month = due_month
            if start_date is not None:
                bill.start_date = _parse_date(start_date, "start date")
            if isinstance(bill, FloatingBill):
                if min_amount is not None:
                    bill.min_amount = min_amount
                if max_amount is not None:
                    bill.max_amount = max_amount
            if preferred_source_bank is not None:
                bill.preferred_source_bank = preferred_source_bank or None
            if preferred_source_account is not None:
                bill.preferred_source_account = preferred_source_account or None
        except KeyError:
            return UpdateBill(success=False, message=f"Unknown frequency '{frequency}'")
        except ValueError as e:
            return UpdateBill(success=False, message=str(e))
        manager.save_to_database()
        return UpdateBill(success=True, message=f"Bill '{bill_name}' updated")


class UpdateIncome(graphene.Mutation):
    """Update an income source."""
    class Arguments:
        source_name = graphene.String(required=True)
        amount = graphene.Float()
        frequency = graphene.String()
        pay_dates = graphene.List(graphene.Int)
        distribution = graphene.JSONString()
        start_date = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, source_name, amount=None, frequency=None, pay_dates=None, distribution=None,
               start_date=None):
        manager = info.context.get('manager')
        if not manager:
            return UpdateIncome(success=False, message="Manager not available")
        income = next((i for i in manager.income_sources if i.source_name == source_name), None)
        if not income:
            return UpdateIncome(success=False, message=f"Income '{source_name}' not found")
        try:
            if amount is not None:
                if amount <= 0:
                    return UpdateIncome(success=False, message="Income amount must be positive")
                income.amount = amount
            if frequency is not None:
                from models.income_source import IncomeFrequency
                income.frequency = IncomeFrequency[frequency.upper()]
            if pay_dates is not None:
                income.pay_date = pay_dates
            if start_date is not None:
                income.start_date = _parse_date(start_date, "start date")
            if distribution is not None:
                # distribution is a dict like {"Account Name": 500.0, "Other Account": null}
                if isinstance(distribution, str):
                    import json
                    distribution = json.loads(distribution)
                income.distribution = DistributionType.__fromdict__(distribution) if distribution else None
        except KeyError:
            return UpdateIncome(success=False, message=f"Unknown frequency '{frequency}'")
        except ValueError as e:
            return UpdateIncome(success=False, message=str(e))
        manager.save_to_database()
        return UpdateIncome(success=True, message=f"Income '{source_name}' updated")


class DeleteAccount(graphene.Mutation):
    """Delete an account from a bank."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        account_type = graphene.String(default_value="bank")  # 'bank', 'credit', 'mortgage'
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, account_type):
        manager = info.context.get('manager')
        if not manager:
            return DeleteAccount(success=False, message="Manager not available")
        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return DeleteAccount(success=False, message=f"Bank '{bank_name}' not found")
        if account_type == "credit":
            if account_name in bank.credit_accounts:
                del bank.credit_accounts[account_name]
                manager.save_to_database()
                return DeleteAccount(success=True, message=f"Credit account '{account_name}' deleted")
        elif account_type == "mortgage":
            if account_name in bank.mortgage_accounts:
                del bank.mortgage_accounts[account_name]
                manager.save_to_database()
                return DeleteAccount(success=True, message=f"Mortgage account '{account_name}' deleted")
        elif account_type == "heloc":
            if account_name in bank.heloc_accounts:
                del bank.heloc_accounts[account_name]
                manager.save_to_database()
                return DeleteAccount(success=True, message=f"HELOC account '{account_name}' deleted")
        else:
            if account_name in bank.accounts:
                del bank.accounts[account_name]
                manager.save_to_database()
                return DeleteAccount(success=True, message=f"Account '{account_name}' deleted")
        return DeleteAccount(success=False, message=f"Account '{account_name}' not found")


class MarkBillPaid(graphene.Mutation):
    """
    Mark a bill as paid for the current period. Works for regular bills and
    for account-linked bills (credit/mortgage/HELOC payments). The money comes
    out of the source account (or the bill's preferred source); paying from a
    credit card charges the card.

    With moveMoney: false the bill is only recorded as paid — use it when the
    payment already happened and your balances already reflect it.
    """
    class Arguments:
        bill_name = graphene.String(required=True)
        amount_paid = graphene.Float()
        source_bank = graphene.String()
        source_account = graphene.String()
        payment_date = graphene.String()  # ISO date string
        move_money = graphene.Boolean(default_value=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, amount_paid=None, source_bank=None, source_account=None, payment_date=None,
               move_money=True):
        manager = info.context.get('manager')
        if not manager:
            return MarkBillPaid(success=False, message="Manager not available")
        bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
        if not bill:
            return MarkBillPaid(success=False, message=f"Bill '{bill_name}' not found")
        try:
            pay_date = _parse_date(payment_date, "payment date") or date.today()
        except ValueError as e:
            return MarkBillPaid(success=False, message=str(e))
        src_bank = source_bank or bill.preferred_source_bank or ''
        src_acct = source_account or bill.preferred_source_account or ''
        pay_amount = amount_paid if amount_paid is not None else bill.effective_amount
        if pay_amount < 0:
            return MarkBillPaid(success=False, message="Amount paid cannot be negative")
        if not move_money:
            manager.record_bill_paid(bill, pay_amount, pay_date, src_bank, src_acct)
            manager.save_to_database()
            return MarkBillPaid(success=True, message=f"Bill '{bill_name}' recorded as paid")

        if isinstance(bill, AccountLinkedBill) and pay_amount > bill.linked_account_balance + 0.005:
            return MarkBillPaid(success=False, message=(
                f"Payment exceeds the balance owed (${bill.linked_account_balance:,.2f})"))

        try:
            undo = _take_payment(manager, src_bank, src_acct, pay_amount, f"Bill payment: {bill_name}", pay_date)
        except ValueError as e:
            return MarkBillPaid(success=False, message=str(e))

        try:
            if isinstance(bill, GroupLinkedBill):
                bill.mark_paid(src_bank, src_acct, amount_paid=pay_amount, payment_date=pay_date, banks=manager.banks)
            else:
                bill.mark_paid(src_bank, src_acct, amount_paid=pay_amount, payment_date=pay_date)
        except ValueError as e:
            undo()
            return MarkBillPaid(success=False, message=f"Payment error: {e}")

        # Persist all state changes (balances, paid flag, payment history)
        manager.save_to_database()

        return MarkBillPaid(success=True, message=f"Bill '{bill_name}' marked as paid")


class ResetBillPeriod(graphene.Mutation):
    """Reset a bill's paid status for new period."""
    class Arguments:
        bill_name = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name):
        manager = info.context.get('manager')
        if not manager:
            return ResetBillPeriod(success=False, message="Manager not available")
        bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
        if not bill:
            return ResetBillPeriod(success=False, message=f"Bill '{bill_name}' not found")
        bill.reset_period()
        manager.save_to_database()
        return ResetBillPeriod(success=True, message=f"Bill '{bill_name}' reset for new period")


class SetFloatingBillAmount(graphene.Mutation):
    """Set the actual amount for a floating/variable bill."""
    class Arguments:
        bill_name = graphene.String(required=True)
        actual_amount = graphene.Float(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, actual_amount):
        manager = info.context.get('manager')
        if not manager:
            return SetFloatingBillAmount(success=False, message="Manager not available")
        bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
        if not bill:
            return SetFloatingBillAmount(success=False, message=f"Bill '{bill_name}' not found")
        if not hasattr(bill, 'set_actual_amount'):
            return SetFloatingBillAmount(success=False, message=f"Bill '{bill_name}' is not a floating bill")
        try:
            bill.set_actual_amount(actual_amount)
            manager.save_to_database()
            return SetFloatingBillAmount(success=True, message=f"Actual amount set to ${actual_amount:.2f}")
        except ValueError as e:
            return SetFloatingBillAmount(success=False, message=str(e))


class MarkCreditPaymentPaid(graphene.Mutation):
    """Record a credit card payment and mark the card's payment paid for the current period."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        amount_paid = graphene.Float(required=True)
        source_bank = graphene.String()
        source_account = graphene.String()
        payment_date = graphene.String()  # ISO date string
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, amount_paid, source_bank=None, source_account=None, payment_date=None):
        manager = info.context.get('manager')
        if not manager:
            return MarkCreditPaymentPaid(success=False, message="Manager not available")

        # Find the bank and credit account
        bank = _find_bank(manager, bank_name)
        if not bank:
            return MarkCreditPaymentPaid(success=False, message=f"Bank '{bank_name}' not found")
        acc = bank.credit_accounts.get(account_name)
        if not acc:
            return MarkCreditPaymentPaid(success=False, message=f"Credit account '{account_name}' not found")
        try:
            pay_date = _parse_date(payment_date, "payment date") or date.today()
        except ValueError as e:
            return MarkCreditPaymentPaid(success=False, message=str(e))
        if amount_paid <= 0:
            return MarkCreditPaymentPaid(success=False, message="Payment amount must be positive")
        if amount_paid > acc.balance + 0.005:
            return MarkCreditPaymentPaid(success=False, message=f"Payment exceeds balance owed (${acc.balance:,.2f})")
        if source_bank == bank_name and source_account == account_name:
            return MarkCreditPaymentPaid(success=False, message="A card can't pay itself")

        # Find the linked bill for this credit account (absent if the card is in a bill group)
        linked_bill = next((
            b for b in manager.bills
            if isinstance(b, AccountLinkedBill) and b.linked_account_type == 'credit'
            and b.linked_bank_name == bank_name and b.linked_account.account_name == account_name
        ), None)
        src_bank = source_bank or (linked_bill.preferred_source_bank if linked_bill else None) or ''
        src_acct = source_account or (linked_bill.preferred_source_account if linked_bill else None) or ''

        try:
            undo = _take_payment(manager, src_bank, src_acct, amount_paid,
                                 f"Credit card payment: {account_name}", pay_date)
        except ValueError as e:
            return MarkCreditPaymentPaid(success=False, message=str(e))

        try:
            if linked_bill:
                # Pays the card, tracks carryover vs. the minimum, and marks the bill paid
                linked_bill.mark_paid(src_bank, src_acct, amount_paid=amount_paid, payment_date=pay_date)
            else:
                acc.make_payment(amount_paid, description="Credit card payment", transaction_date=pay_date)
        except ValueError as e:
            undo()
            return MarkCreditPaymentPaid(success=False, message=str(e))

        # Persist all state changes
        manager.save_to_database()

        return MarkCreditPaymentPaid(
            success=True,
            message=f"Credit payment of ${amount_paid:.2f} recorded for {account_name} (balance: ${acc.balance:.2f})"
        )


class ResetCreditPaymentPeriod(graphene.Mutation):
    """Reset a credit card payment's paid status for new period."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name):
        manager = info.context.get('manager')
        if not manager:
            return ResetCreditPaymentPeriod(success=False, message="Manager not available")

        # Find the linked bill for this credit account and reset it
        for bill in manager.bills:
            if isinstance(bill, AccountLinkedBill) and bill.linked_account_type == 'credit':
                if bill.linked_bank_name == bank_name and bill.linked_account.account_name == account_name:
                    bill.reset_period()
                    manager.save_to_database()
                    return ResetCreditPaymentPeriod(success=True, message=f"Credit payment for {account_name} reset for new period")

        return ResetCreditPaymentPeriod(success=False, message=f"No payment found for credit account '{account_name}' at '{bank_name}'")


class RecordBalanceUpdate(graphene.Mutation):
    """Record a balance update with history tracking."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        new_balance = graphene.Float(required=True)
        account_type = graphene.String(default_value="bank")  # bank, credit, mortgage
        notes = graphene.String(default_value="")
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, new_balance, account_type="bank", notes=""):
        manager = info.context.get('manager')
        if not manager:
            return RecordBalanceUpdate(success=False, message="Manager not available")
        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return RecordBalanceUpdate(success=False, message=f"Bank '{bank_name}' not found")

        # Get previous balance
        prev_balance = 0.0
        if account_type == "credit":
            acc = bank.credit_accounts.get(account_name)
            if acc:
                prev_balance = acc.balance
                bank.update_credit_balance(account_name, new_balance)
            else:
                return RecordBalanceUpdate(success=False, message=f"Credit account '{account_name}' not found")
        elif account_type == "mortgage":
            acc = bank.mortgage_accounts.get(account_name)
            if acc:
                prev_balance = acc.current_principal
                acc.current_principal = new_balance
            else:
                return RecordBalanceUpdate(success=False, message=f"Mortgage '{account_name}' not found")
        elif account_type == "heloc":
            acc = bank.heloc_accounts.get(account_name)
            if acc:
                prev_balance = acc.balance
                acc.balance = new_balance
            else:
                return RecordBalanceUpdate(success=False, message=f"HELOC '{account_name}' not found")
        else:
            acc = bank.accounts.get(account_name)
            if acc:
                prev_balance = acc.balance
                bank.update_account_balance(account_name, new_balance)
            else:
                return RecordBalanceUpdate(success=False, message=f"Account '{account_name}' not found")

        # Record history
        try:
            from models.database import get_session
            from sqlalchemy import text
            session = get_session()
            try:
                # Create table if not exists
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS balance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bank_name TEXT NOT NULL,
                        account_name TEXT NOT NULL,
                        account_type TEXT NOT NULL,
                        balance REAL NOT NULL,
                        previous_balance REAL,
                        recorded_at TEXT NOT NULL,
                        notes TEXT
                    )
                """))
                session.execute(text("""
                    INSERT INTO balance_history (bank_name, account_name, account_type, balance, previous_balance, recorded_at, notes)
                    VALUES (:bn, :an, :at, :bal, :prev, :ts, :notes)
                """), {
                    "bn": bank_name, "an": account_name, "at": account_type,
                    "bal": new_balance, "prev": prev_balance,
                    "ts": datetime.now().isoformat(), "notes": notes or f"Updated from ${prev_balance:.2f} to ${new_balance:.2f}"
                })
                session.commit()
            finally:
                session.close()
        except Exception:
            pass

        manager.save_to_database()
        return RecordBalanceUpdate(success=True, message=f"Balance updated and recorded (${prev_balance:.2f} -> ${new_balance:.2f})")


class SetupSimplefin(graphene.Mutation):
    """Claim a SimpleFIN setup token and store the access URL."""
    class Arguments:
        setup_token = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, setup_token):
        from models.simplefin import SimplefinClient, save_simplefin_connection
        try:
            access_url = SimplefinClient.claim_setup_token(setup_token)
            save_simplefin_connection(access_url)
            return SetupSimplefin(success=True, message="SimpleFIN Bridge connected successfully")
        except ValueError as e:
            return SetupSimplefin(success=False, message=str(e))
        except Exception as e:
            return SetupSimplefin(success=False, message=f"Unexpected error: {e}")


class SyncSimplefinBalances(graphene.Mutation):
    """Fetch latest balances from SimpleFIN and update mapped accounts."""
    success = graphene.Boolean()
    message = graphene.String()
    accounts_updated = graphene.Int()
    accounts_skipped = graphene.Int()
    errors = graphene.List(graphene.String)
    details = graphene.JSONString()

    def mutate(self, info):
        manager = info.context.get('manager')
        if not manager:
            return SyncSimplefinBalances(success=False, message="Manager not available")

        from models.simplefin import (
            get_simplefin_connection, get_simplefin_mappings,
            SimplefinClient, update_simplefin_last_sync
        )

        conn = get_simplefin_connection()
        if not conn:
            return SyncSimplefinBalances(
                success=False, message="SimpleFIN is not connected. Set up a connection first."
            )

        mappings = get_simplefin_mappings()
        if not mappings:
            return SyncSimplefinBalances(
                success=False,
                message="No accounts mapped. Map SimpleFIN accounts to local accounts first."
            )

        result = SimplefinClient.sync_balances(conn['access_url'], mappings, manager)

        # Invalidate cached payment plan since balances changed
        if result.accounts_updated > 0 and hasattr(manager, 'invalidate_plan_cache'):
            manager.invalidate_plan_cache()

        update_simplefin_last_sync()

        # Count unchanged vs unmapped from details
        unchanged_count = sum(1 for d in result.details if d.get('status') == 'unchanged')
        unmapped_count = result.accounts_skipped - unchanged_count

        msg = f"Updated {result.accounts_updated} account(s)"
        if unchanged_count:
            msg += f", {unchanged_count} unchanged"
        if unmapped_count > 0:
            msg += f", {unmapped_count} unmapped"
        if result.errors:
            msg += f", {len(result.errors)} error(s)"

        return SyncSimplefinBalances(
            success=result.success,
            message=msg,
            accounts_updated=result.accounts_updated,
            accounts_skipped=result.accounts_skipped,
            errors=result.errors if result.errors else None,
            details=result.details if result.details else None,
        )


class MapSimplefinAccount(graphene.Mutation):
    """Map a SimpleFIN account to a local bank account."""
    class Arguments:
        simplefin_account_id = graphene.String(required=True)
        simplefin_account_name = graphene.String(required=True)
        simplefin_org_name = graphene.String(required=True)
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        account_type = graphene.String(required=True)  # bank, credit, mortgage
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, simplefin_account_id, simplefin_account_name,
               simplefin_org_name, bank_name, account_name, account_type):
        from models.simplefin import save_simplefin_mapping
        try:
            save_simplefin_mapping(
                simplefin_account_id, simplefin_account_name, simplefin_org_name,
                bank_name, account_name, account_type
            )
            return MapSimplefinAccount(
                success=True,
                message=f"Mapped '{simplefin_account_name}' → {bank_name}/{account_name}"
            )
        except Exception as e:
            return MapSimplefinAccount(success=False, message=str(e))


class UnmapSimplefinAccount(graphene.Mutation):
    """Remove a SimpleFIN account mapping."""
    class Arguments:
        simplefin_account_id = graphene.String(required=True)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, simplefin_account_id):
        from models.simplefin import remove_simplefin_mapping
        remove_simplefin_mapping(simplefin_account_id)
        return UnmapSimplefinAccount(success=True, message="Mapping removed")


class RemoveSimplefinConnection(graphene.Mutation):
    """Disconnect SimpleFIN Bridge and remove all mappings."""
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info):
        from models.simplefin import remove_simplefin_connection
        remove_simplefin_connection()
        return RemoveSimplefinConnection(success=True, message="SimpleFIN Bridge disconnected")


class AutoResetPeriods(graphene.Mutation):
    """Auto-reset bill periods that have rolled over."""
    success = graphene.Boolean()
    reset_count = graphene.Int()
    message = graphene.String()

    def mutate(self, info):
        manager = info.context.get('manager')
        if not manager:
            return AutoResetPeriods(success=False, reset_count=0, message="No manager")
        count = manager.auto_reset_periods()
        return AutoResetPeriods(success=True, reset_count=count, message=f"Reset {count} bill period(s)")


class RecordNetWorthSnapshot(graphene.Mutation):
    """Record current net worth snapshot."""
    success = graphene.Boolean()
    snapshot = graphene.Field(NetWorthSnapshotType)

    def mutate(self, info):
        manager = info.context.get('manager')
        if not manager:
            return RecordNetWorthSnapshot(success=False, snapshot=None)
        result = manager.record_net_worth_snapshot()
        if result:
            return RecordNetWorthSnapshot(
                success=True,
                snapshot=NetWorthSnapshotType(**result)
            )
        return RecordNetWorthSnapshot(success=False, snapshot=None)


class CreateBillGroup(graphene.Mutation):
    """Create a new bill group."""
    class Arguments:
        group_name = graphene.String(required=True)
        total_payment = graphene.Float(required=True)
        due_date = graphene.Int(required=True)
        frequency = graphene.String(default_value="monthly")
        group_type = graphene.String(default_value="student_loan")
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()

    bill_group = graphene.Field(BillGroupType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name, total_payment, due_date,
               frequency="monthly", group_type="student_loan",
               preferred_source_bank=None, preferred_source_account=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateBillGroup(success=False, message="Manager not available")
        try:
            from models.bill_group import BillGroup
            group = BillGroup(
                group_name=group_name,
                total_payment=total_payment,
                due_date=due_date,
                frequency=frequency,
                group_type=group_type,
                preferred_source_bank=preferred_source_bank,
                preferred_source_account=preferred_source_account,
            )
            manager.add_bill_group(group)
            manager.save_to_database()
            return CreateBillGroup(
                bill_group=_group_to_type(group, manager.banks),
                success=True,
                message=f"Bill group '{group_name}' created"
            )
        except Exception as e:
            return CreateBillGroup(success=False, message=str(e))


class UpdateBillGroup(graphene.Mutation):
    """Update an existing bill group."""
    class Arguments:
        group_name = graphene.String(required=True)
        total_payment = graphene.Float()
        due_date = graphene.Int()
        frequency = graphene.String()
        group_type = graphene.String()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()

    bill_group = graphene.Field(BillGroupType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name, **kwargs):
        manager = info.context.get('manager')
        if not manager:
            return UpdateBillGroup(success=False, message="Manager not available")
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if not group:
            return UpdateBillGroup(success=False, message=f"Bill group '{group_name}' not found")
        try:
            if 'total_payment' in kwargs and kwargs['total_payment'] is not None:
                group.total_payment = kwargs['total_payment']
            if 'due_date' in kwargs and kwargs['due_date'] is not None:
                group.due_date = kwargs['due_date']
            if 'frequency' in kwargs and kwargs['frequency'] is not None:
                from models.types import BillFrequency
                group.frequency = BillFrequency(kwargs['frequency'])
            if 'group_type' in kwargs and kwargs['group_type'] is not None:
                group.group_type = kwargs['group_type']
            if 'preferred_source_bank' in kwargs:
                group.preferred_source_bank = kwargs['preferred_source_bank']
            if 'preferred_source_account' in kwargs:
                group.preferred_source_account = kwargs['preferred_source_account']
            manager.save_to_database()
            return UpdateBillGroup(
                bill_group=_group_to_type(group, manager.banks),
                success=True,
                message=f"Bill group '{group_name}' updated"
            )
        except Exception as e:
            return UpdateBillGroup(success=False, message=str(e))


class DeleteBillGroup(graphene.Mutation):
    """Delete a bill group."""
    class Arguments:
        group_name = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name):
        manager = info.context.get('manager')
        if not manager:
            return DeleteBillGroup(success=False, message="Manager not available")
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if not group:
            return DeleteBillGroup(success=False, message=f"Bill group '{group_name}' not found")
        manager.remove_bill_group(group)
        manager.save_to_database()
        return DeleteBillGroup(success=True, message=f"Bill group '{group_name}' deleted")


class AddBillGroupMember(graphene.Mutation):
    """Add a credit/loan account to a bill group."""
    class Arguments:
        group_name = graphene.String(required=True)
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        allocation_method = graphene.String(default_value="proportional")
        fixed_amount = graphene.Float(default_value=0.0)

    bill_group = graphene.Field(BillGroupType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name, bank_name, account_name,
               allocation_method="proportional", fixed_amount=0.0):
        manager = info.context.get('manager')
        if not manager:
            return AddBillGroupMember(success=False, message="Manager not available")
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if not group:
            return AddBillGroupMember(success=False, message=f"Bill group '{group_name}' not found")
        bank = _find_bank(manager, bank_name)
        if not bank or account_name not in bank.credit_accounts:
            return AddBillGroupMember(success=False, message=f"Credit account '{account_name}' not found at '{bank_name}'")
        for other in manager.bill_groups:
            if other is not group and (bank_name, account_name) in other.get_grouped_account_keys():
                return AddBillGroupMember(success=False, message=f"'{account_name}' already belongs to group '{other.group_name}'")
        try:
            from models.types import AllocationMethod
            group.add_member(
                bank_name=bank_name,
                account_name=account_name,
                allocation_method=AllocationMethod(allocation_method),
                fixed_amount=fixed_amount,
            )
            manager.save_to_database()
            return AddBillGroupMember(
                bill_group=_group_to_type(group, manager.banks),
                success=True,
                message=f"Added '{account_name}' to group '{group_name}'"
            )
        except Exception as e:
            return AddBillGroupMember(success=False, message=str(e))


class RemoveBillGroupMember(graphene.Mutation):
    """Remove a credit/loan account from a bill group."""
    class Arguments:
        group_name = graphene.String(required=True)
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)

    bill_group = graphene.Field(BillGroupType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name, bank_name, account_name):
        manager = info.context.get('manager')
        if not manager:
            return RemoveBillGroupMember(success=False, message="Manager not available")
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if not group:
            return RemoveBillGroupMember(success=False, message=f"Bill group '{group_name}' not found")
        if group.remove_member(bank_name, account_name):
            manager.save_to_database()
            return RemoveBillGroupMember(
                bill_group=_group_to_type(group, manager.banks),
                success=True,
                message=f"Removed '{account_name}' from group '{group_name}'"
            )
        return RemoveBillGroupMember(
            success=False,
            message=f"Account '{account_name}' at '{bank_name}' not found in group '{group_name}'"
        )


class MarkBillGroupPaid(graphene.Mutation):
    """
    Pay a bill group for the current period: withdraws from the source (or the
    group's preferred source) and distributes the payment across member accounts.
    """
    class Arguments:
        group_name = graphene.String(required=True)
        amount_paid = graphene.Float()
        source_bank = graphene.String()
        source_account = graphene.String()
        payment_date = graphene.String()  # ISO date string

    bill_group = graphene.Field(BillGroupType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, group_name, amount_paid=None, source_bank=None, source_account=None, payment_date=None):
        manager = info.context.get('manager')
        if not manager:
            return MarkBillGroupPaid(success=False, message="Manager not available")
        group = next((g for g in manager.bill_groups if g.group_name == group_name), None)
        if not group:
            return MarkBillGroupPaid(success=False, message=f"Bill group '{group_name}' not found")
        manager.refresh()
        group_bill = next((b for b in manager.bills
                           if isinstance(b, GroupLinkedBill) and b.linked_group is group), None)
        try:
            pay_date = _parse_date(payment_date, "payment date") or date.today()
        except ValueError as e:
            return MarkBillGroupPaid(success=False, message=str(e))
        pay_amount = amount_paid if amount_paid is not None else group_bill.effective_amount
        if pay_amount < 0:
            return MarkBillGroupPaid(success=False, message="Amount paid cannot be negative")
        total_owed = group.get_total_balance(manager.banks)
        if pay_amount > total_owed + 0.005:
            return MarkBillGroupPaid(success=False, message=f"Payment exceeds the group's total balance (${total_owed:,.2f})")
        src_bank = source_bank or group.preferred_source_bank or ''
        src_acct = source_account or group.preferred_source_account or ''

        try:
            undo = _take_payment(manager, src_bank, src_acct, pay_amount, f"Group payment: {group_name}", pay_date)
        except ValueError as e:
            return MarkBillGroupPaid(success=False, message=str(e))
        try:
            group_bill.mark_paid(src_bank, src_acct, amount_paid=pay_amount, payment_date=pay_date, banks=manager.banks)
        except ValueError as e:
            undo()
            return MarkBillGroupPaid(success=False, message=f"Payment error: {e}")

        manager.save_to_database()
        return MarkBillGroupPaid(
            bill_group=_group_to_type(group, manager.banks),
            success=True,
            message=f"Bill group '{group_name}' paid (${pay_amount:,.2f})"
        )


class CreateHelocAccount(graphene.Mutation):
    """Create a new HELOC account."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        credit_limit = graphene.Float(required=True)
        interest_rate = graphene.Float()
        draw_period_months = graphene.Int()
        total_term_months = graphene.Int()
        start_date = graphene.String()
        current_balance = graphene.Float()
        payment_due_date = graphene.Int()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, credit_limit,
               interest_rate=0.0, draw_period_months=180, total_term_months=360,
               start_date=None, current_balance=0.0, payment_due_date=1,
               preferred_source_bank=None, preferred_source_account=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateHelocAccount(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return CreateHelocAccount(success=False, message=f"Bank '{bank_name}' not found")

        try:
            sd = _parse_date(start_date, "start date")
            bank.add_heloc_account(
                account_name=account_name,
                credit_limit=credit_limit,
                interest_rate=interest_rate or 0.0,
                draw_period_months=draw_period_months or 180,
                total_term_months=total_term_months or 360,
                start_date=sd,
                current_balance=current_balance or 0.0,
                payment_due_date=payment_due_date or 1,
                preferred_source_bank=preferred_source_bank,
                preferred_source_account=preferred_source_account,
            )
            manager.save_to_database()
            return CreateHelocAccount(success=True, message=f"HELOC account '{account_name}' created")
        except Exception as e:
            return CreateHelocAccount(success=False, message=str(e))


class CreateMortgageAccount(graphene.Mutation):
    """Create a new mortgage account."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        original_principal = graphene.Float(required=True)
        current_principal = graphene.Float()
        interest_rate = graphene.Float()
        loan_term_months = graphene.Int()
        payment_due_date = graphene.Int()
        start_date = graphene.String()
        escrow_property_tax = graphene.Float()
        escrow_insurance = graphene.Float()
        escrow_pmi = graphene.Float()
        escrow_hoa = graphene.Float()
        escrow_other = graphene.Float()
        market_value = graphene.Float()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, original_principal, current_principal=None,
               interest_rate=0.0, loan_term_months=360, payment_due_date=1, start_date=None,
               escrow_property_tax=0.0, escrow_insurance=0.0, escrow_pmi=0.0, escrow_hoa=0.0,
               escrow_other=0.0, market_value=None, preferred_source_bank=None, preferred_source_account=None):
        manager = info.context.get('manager')
        if not manager:
            return CreateMortgageAccount(success=False, message="Manager not available")

        bank = _find_bank(manager, bank_name)
        if not bank:
            return CreateMortgageAccount(success=False, message=f"Bank '{bank_name}' not found")

        try:
            from models.mortgage_account import EscrowBreakdown
            if current_principal is not None and current_principal > original_principal:
                return CreateMortgageAccount(success=False, message="Current principal can't exceed the original loan amount")
            escrow_parts = (escrow_property_tax, escrow_insurance, escrow_pmi, escrow_hoa, escrow_other)
            if any((v or 0) < 0 for v in escrow_parts):
                return CreateMortgageAccount(success=False, message="Escrow amounts can't be negative")
            if market_value is not None and market_value < 0:
                return CreateMortgageAccount(success=False, message="Market value can't be negative")
            if bool(preferred_source_bank) != bool(preferred_source_account):
                return CreateMortgageAccount(success=False, message="Choose both a payment source bank and account, or neither")
            sd = _parse_date(start_date, "start date")
            mortgage = bank.add_mortgage_account(
                account_name=account_name,
                original_principal=original_principal,
                interest_rate=interest_rate or 0.0,
                loan_term_months=loan_term_months or 360,
                current_principal=current_principal,
                payment_due_date=payment_due_date or 1,
                escrow=EscrowBreakdown(*(v or 0.0 for v in escrow_parts)),
                preferred_source_bank=preferred_source_bank or None,
                preferred_source_account=preferred_source_account or None,
            )
            if sd:
                mortgage.start_date = sd
            mortgage.market_value = market_value
            manager.save_to_database()
            return CreateMortgageAccount(
                success=True,
                message=f"Mortgage '{account_name}' created (${mortgage.total_monthly_payment:,.2f}/month)"
            )
        except Exception as e:
            return CreateMortgageAccount(success=False, message=str(e))


class ConvertCreditToHeloc(graphene.Mutation):
    """Convert a credit card account to a HELOC account."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        draw_period_months = graphene.Int(required=True)
        total_term_months = graphene.Int(required=True)
        start_date = graphene.String()
        new_account_name = graphene.String()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, draw_period_months, total_term_months,
               start_date=None, new_account_name=None):
        manager = info.context.get('manager')
        if not manager:
            return ConvertCreditToHeloc(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return ConvertCreditToHeloc(success=False, message=f"Bank '{bank_name}' not found")

        credit = bank.credit_accounts.get(account_name)
        if not credit:
            return ConvertCreditToHeloc(success=False, message=f"Credit account '{account_name}' not found")

        try:
            sd = _parse_date(start_date, "start date")
            heloc_name = new_account_name or account_name
            if heloc_name in bank.heloc_accounts:
                return ConvertCreditToHeloc(success=False, message=f"HELOC '{heloc_name}' already exists in '{bank_name}'")

            bank.add_heloc_account(
                account_name=heloc_name,
                credit_limit=credit.credit_limit,
                interest_rate=credit.interest_rate,
                draw_period_months=draw_period_months,
                total_term_months=total_term_months,
                start_date=sd,
                current_balance=credit.balance,
                payment_due_date=credit.payment_due_date or 1,
            )

            # Remove the old credit account (save_to_database prunes its DB row
            # and swaps its linked bill for the new HELOC's)
            del bank.credit_accounts[account_name]

            manager.save_to_database()
            return ConvertCreditToHeloc(success=True, message=f"Converted '{account_name}' to HELOC '{heloc_name}'")
        except Exception as e:
            return ConvertCreditToHeloc(success=False, message=str(e))


class UpdateMortgageMarketValue(graphene.Mutation):
    """Update the current market value of a mortgaged property."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        market_value = graphene.Float(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, market_value):
        manager = info.context.get('manager')
        if not manager:
            return UpdateMortgageMarketValue(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return UpdateMortgageMarketValue(success=False, message=f"Bank '{bank_name}' not found")

        mortgage = bank.mortgage_accounts.get(account_name)
        if not mortgage:
            return UpdateMortgageMarketValue(success=False, message=f"Mortgage '{account_name}' not found")

        mortgage.market_value = market_value
        manager.save_to_database()
        equity = mortgage.equity
        return UpdateMortgageMarketValue(
            success=True,
            message=f"Market value set to ${market_value:,.2f}. Equity: ${equity:,.2f}"
        )


class AddPromoOffer(graphene.Mutation):
    """Add a promotional offer to a credit account."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        promo_name = graphene.String(required=True)
        months_interest_free = graphene.Int(required=True)
        purchase_limit = graphene.Float()
        promo_balance = graphene.Float()
        start_date = graphene.String()
        end_date = graphene.String()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, promo_name, months_interest_free,
               purchase_limit=None, promo_balance=None, start_date=None, end_date=None):
        manager = info.context.get('manager')
        if not manager:
            return AddPromoOffer(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return AddPromoOffer(success=False, message=f"Bank '{bank_name}' not found")

        acc = bank.credit_accounts.get(account_name)
        if not acc:
            return AddPromoOffer(success=False, message=f"Credit account '{account_name}' not found")

        if any(p.promo_name == promo_name for p in acc.active_promos):
            return AddPromoOffer(success=False, message=f"Promo '{promo_name}' already exists")

        try:
            from datetime import date as date_cls
            sd = date_cls.fromisoformat(start_date) if start_date else None
            ed = date_cls.fromisoformat(end_date) if end_date else None
            from models.credit_card_account import PromoOffer
            promo = PromoOffer(
                promo_name=promo_name,
                months_interest_free=months_interest_free,
                purchase_limit=purchase_limit,
                start_date=sd,
                end_date=ed,
            )
            acc.active_promos.append(promo)
            bal = promo_balance if promo_balance is not None else 0.0
            acc.promo_balance[promo_name] = bal
            promo.amount_used = bal
            if bal > 0:
                acc.regular_balance = max(0, acc.regular_balance - bal)
            manager.save_to_database()
            return AddPromoOffer(success=True, message=f"Promo '{promo_name}' added with balance ${bal:.2f}")
        except Exception as e:
            return AddPromoOffer(success=False, message=str(e))


class UpdatePromoOffer(graphene.Mutation):
    """Update the balance allocation of a promo offer."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        promo_name = graphene.String(required=True)
        promo_balance = graphene.Float()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, promo_name, promo_balance=None):
        manager = info.context.get('manager')
        if not manager:
            return UpdatePromoOffer(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return UpdatePromoOffer(success=False, message=f"Bank '{bank_name}' not found")

        acc = bank.credit_accounts.get(account_name)
        if not acc:
            return UpdatePromoOffer(success=False, message=f"Credit account '{account_name}' not found")

        promo = next((p for p in acc.active_promos if p.promo_name == promo_name), None)
        if not promo:
            return UpdatePromoOffer(success=False, message=f"Promo '{promo_name}' not found")

        if promo_balance is not None:
            old_bal = acc.promo_balance.get(promo_name, 0.0)
            delta = promo_balance - old_bal
            acc.promo_balance[promo_name] = promo_balance
            promo.amount_used = promo_balance
            acc.regular_balance = max(0, acc.regular_balance - delta)

        manager.save_to_database()
        return UpdatePromoOffer(success=True, message=f"Promo '{promo_name}' updated")


class RemovePromoOffer(graphene.Mutation):
    """Remove a promo offer from a credit account."""
    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        promo_name = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bank_name, account_name, promo_name):
        manager = info.context.get('manager')
        if not manager:
            return RemovePromoOffer(success=False, message="Manager not available")

        bank = next((b for b in manager.banks if b.name == bank_name), None)
        if not bank:
            return RemovePromoOffer(success=False, message=f"Bank '{bank_name}' not found")

        acc = bank.credit_accounts.get(account_name)
        if not acc:
            return RemovePromoOffer(success=False, message=f"Credit account '{account_name}' not found")

        promo = next((p for p in acc.active_promos if p.promo_name == promo_name), None)
        if not promo:
            return RemovePromoOffer(success=False, message=f"Promo '{promo_name}' not found")

        promo_bal = acc.promo_balance.pop(promo_name, 0.0)
        acc.regular_balance += promo_bal
        acc.active_promos.remove(promo)

        manager.save_to_database()
        return RemovePromoOffer(success=True, message=f"Promo '{promo_name}' removed")


class Mutation(ExtMutation, graphene.ObjectType):
    """Root mutation for the GraphQL API."""

    create_bank = CreateBank.Field()
    create_account = CreateAccount.Field()
    create_bill = CreateBill.Field()
    create_income_source = CreateIncomeSource.Field()
    update_account_balance = UpdateAccountBalance.Field()
    update_credit_balance = UpdateCreditBalance.Field()
    update_bill = UpdateBill.Field()
    update_income = UpdateIncome.Field()
    delete_bank = DeleteBank.Field()
    delete_account = DeleteAccount.Field()
    delete_bill = DeleteBill.Field()
    delete_income = DeleteIncome.Field()
    mark_bill_paid = MarkBillPaid.Field()
    reset_bill_period = ResetBillPeriod.Field()
    set_floating_bill_amount = SetFloatingBillAmount.Field()
    mark_credit_payment_paid = MarkCreditPaymentPaid.Field()
    reset_credit_payment_period = ResetCreditPaymentPeriod.Field()
    record_balance_update = RecordBalanceUpdate.Field()
    save_database = SaveDatabase.Field()
    load_database = LoadDatabase.Field()
    setup_simplefin = SetupSimplefin.Field()
    sync_simplefin_balances = SyncSimplefinBalances.Field()
    map_simplefin_account = MapSimplefinAccount.Field()
    unmap_simplefin_account = UnmapSimplefinAccount.Field()
    remove_simplefin_connection = RemoveSimplefinConnection.Field()
    auto_reset_periods = AutoResetPeriods.Field()
    record_net_worth_snapshot = RecordNetWorthSnapshot.Field()
    create_bill_group = CreateBillGroup.Field()
    update_bill_group = UpdateBillGroup.Field()
    delete_bill_group = DeleteBillGroup.Field()
    add_bill_group_member = AddBillGroupMember.Field()
    remove_bill_group_member = RemoveBillGroupMember.Field()
    mark_bill_group_paid = MarkBillGroupPaid.Field()
    create_heloc_account = CreateHelocAccount.Field()
    create_mortgage_account = CreateMortgageAccount.Field()
    convert_credit_to_heloc = ConvertCreditToHeloc.Field()
    update_mortgage_market_value = UpdateMortgageMarketValue.Field()
    add_promo_offer = AddPromoOffer.Field()
    update_promo_offer = UpdatePromoOffer.Field()
    remove_promo_offer = RemovePromoOffer.Field()


# ==================== Schema ====================

schema = graphene.Schema(query=Query, mutation=Mutation)

