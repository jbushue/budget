"""
GraphQL for the tools in models/tools.py: transfers, promo purchases and
payments, extra mortgage principal and the mortgage calculator, one-pass
balance updates, resetting a floating bill, payment-strategy comparison,
the monthly projection summary, and database info. Mixed into the root
schema through gql_ext.
"""

from __future__ import annotations

import graphene

from models import tools


def _manager(info):
    return info.context.get('manager')


class ToolResult(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()


def _run(fn, *args, **kwargs) -> ToolResult:
    """Run a tool against the shared manager and save; any ToolError becomes the message."""
    try:
        message = fn(*args, **kwargs)
    except tools.ToolError as e:
        return ToolResult(success=False, message=str(e))
    except ValueError as e:
        return ToolResult(success=False, message=str(e))
    manager = args[0]
    manager.invalidate_plan_cache()
    if not manager.save_to_database():
        return ToolResult(success=False, message="Changed, but saving to the database failed")
    return ToolResult(success=True, message=message)


def _no_manager():
    return ToolResult(success=False, message="Manager not available")


# ── mutations ────────────────────────────────────────────────────────────

class TransferMoney(graphene.Mutation):
    """Move money between two checking/savings accounts."""

    class Arguments:
        from_bank = graphene.String(required=True)
        from_account = graphene.String(required=True)
        to_bank = graphene.String(required=True)
        to_account = graphene.String(required=True)
        amount = graphene.Float(required=True)
        note = graphene.String()

    Output = ToolResult

    def mutate(self, info, from_bank, from_account, to_bank, to_account, amount, note=""):
        m = _manager(info)
        return _run(tools.transfer, m, from_bank, from_account, to_bank, to_account, amount, note or "") if m else _no_manager()


class RecordPromoPurchase(graphene.Mutation):
    """Charge a purchase to a card's promotional offer."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        promo_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        description = graphene.String()

    Output = ToolResult

    def mutate(self, info, bank_name, account_name, promo_name, amount, description=""):
        m = _manager(info)
        return _run(tools.promo_purchase, m, bank_name, account_name, promo_name, amount, description or "") if m else _no_manager()


class PayPromoBalance(graphene.Mutation):
    """Pay down a promo balance from a checking/savings account."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        promo_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        source_bank = graphene.String(required=True)
        source_account = graphene.String(required=True)

    Output = ToolResult

    def mutate(self, info, bank_name, account_name, promo_name, amount, source_bank, source_account):
        m = _manager(info)
        return _run(tools.promo_payment, m, bank_name, account_name, promo_name, amount,
                    source_bank, source_account) if m else _no_manager()


class PayExtraPrincipal(graphene.Mutation):
    """Pay extra toward a mortgage's principal (optionally from a cash account)."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        amount = graphene.Float(required=True)
        source_bank = graphene.String()
        source_account = graphene.String()

    Output = ToolResult

    def mutate(self, info, bank_name, account_name, amount, source_bank="", source_account=""):
        m = _manager(info)
        return _run(tools.extra_principal, m, bank_name, account_name, amount,
                    source_bank or "", source_account or "") if m else _no_manager()


class BalanceInput(graphene.InputObjectType):
    bank = graphene.String(required=True)
    account = graphene.String(required=True)
    kind = graphene.String(required=True, description="bank | credit | mortgage | heloc")
    balance = graphene.Float(required=True)


class UpdateBalances(graphene.Mutation):
    """Set many balances in one go (a balance check-in). Unchanged ones are skipped."""

    class Arguments:
        updates = graphene.List(graphene.NonNull(BalanceInput), required=True)

    Output = ToolResult

    def mutate(self, info, updates):
        m = _manager(info)
        if not m:
            return _no_manager()

        def apply(manager, rows):
            n = tools.update_balances(manager, [dict(r) for r in rows])
            return f"Updated {n} balance{'' if n == 1 else 's'}" if n else "No balances changed"
        return _run(apply, m, updates)


class ResetBillToEstimate(graphene.Mutation):
    """Drop a floating bill's entered amount and go back to its estimate."""

    class Arguments:
        bill_name = graphene.String(required=True)

    Output = ToolResult

    def mutate(self, info, bill_name):
        m = _manager(info)
        return _run(tools.reset_bill_to_estimate, m, bill_name) if m else _no_manager()


class ToolsMutation(graphene.ObjectType):
    transfer_money = TransferMoney.Field()
    record_promo_purchase = RecordPromoPurchase.Field()
    pay_promo_balance = PayPromoBalance.Field()
    pay_extra_principal = PayExtraPrincipal.Field()
    update_balances = UpdateBalances.Field()
    reset_bill_to_estimate = ResetBillToEstimate.Field()


# ── queries ──────────────────────────────────────────────────────────────

class AmortizationRowType(graphene.ObjectType):
    month = graphene.Int()
    date = graphene.String()
    payment = graphene.Float()
    principal = graphene.Float()
    interest = graphene.Float()
    escrow = graphene.Float()
    principal_remaining = graphene.Float()


class AmortizationYearType(graphene.ObjectType):
    year = graphene.Int()
    principal = graphene.Float()
    interest = graphene.Float()
    escrow = graphene.Float()
    end_balance = graphene.Float()


class MortgageDetailsType(graphene.ObjectType):
    balance = graphene.Float()
    rate = graphene.Float()
    monthly_payment = graphene.Float()
    principal_and_interest = graphene.Float()
    escrow = graphene.Float()
    next_interest = graphene.Float()
    next_principal = graphene.Float()
    remaining_months = graphene.Int()
    payoff_date = graphene.String()
    interest_remaining = graphene.Float()
    equity = graphene.Float()
    ltv = graphene.Float()
    market_value = graphene.Float()
    extra_monthly = graphene.Float()
    months_saved = graphene.Int()
    interest_saved = graphene.Float()
    new_payoff_date = graphene.String()
    schedule = graphene.List(AmortizationRowType, description="The next 12 payments")
    years = graphene.List(AmortizationYearType, description="Every remaining year, summed")


class ExtraPaymentType(graphene.ObjectType):
    date = graphene.String()
    account = graphene.String()
    amount = graphene.Float()


class StrategyType(graphene.ObjectType):
    goal = graphene.String()
    label = graphene.String()
    final_cash = graphene.Float()
    ending_debt = graphene.Float()
    outcome = graphene.Float()
    lowest_checking = graphene.Float()
    late = graphene.Int()
    interest_paid = graphene.Float()
    interest_earned = graphene.Float()
    fees = graphene.Float()
    problems = graphene.Int()
    extra_payments = graphene.List(ExtraPaymentType)
    extra_total = graphene.Float()


class MonthSummaryType(graphene.ObjectType):
    month = graphene.String()
    income = graphene.Float()
    payments = graphene.Float()
    spending = graphene.Float()
    interest = graphene.Float()
    fees = graphene.Float()
    net = graphene.Float()
    end_cash = graphene.Float()
    end_debt = graphene.Float()


class TableCountType(graphene.ObjectType):
    table = graphene.String()
    label = graphene.String()
    rows = graphene.Int()


class DatabaseInfoType(graphene.ObjectType):
    path = graphene.String(description="Only shown to admins")
    size_bytes = graphene.Float()
    tables = graphene.List(TableCountType)


class ReportKindType(graphene.ObjectType):
    key = graphene.String()
    description = graphene.String()


class ToolsQuery(graphene.ObjectType):
    mortgage_details = graphene.Field(MortgageDetailsType, bank_name=graphene.String(required=True),
                                      account_name=graphene.String(required=True), extra_monthly=graphene.Float())
    compare_strategies = graphene.List(StrategyType, days=graphene.Int(), target_account=graphene.String(),
                                       description="The optimizer's plan under each goal, side by side")
    strategy_targets = graphene.List(graphene.String, description="Cards with a balance (for the payoff goal)")
    monthly_projection = graphene.List(MonthSummaryType, days=graphene.Int())
    database_info = graphene.Field(DatabaseInfoType)
    report_kinds = graphene.List(ReportKindType)
    debt_boost = graphene.JSONString(days=graphene.Int(), strategy=graphene.String(), monthly=graphene.Float(),
                                     description="Most you can safely put toward debt each month, and what it saves")
    due_date_moves = graphene.JSONString(days=graphene.Int(),
                                         description="Bills whose due date would be better right after a payday")
    purchase_planner = graphene.JSONString(amount=graphene.Float(), days=graphene.Int(),
                                           description="How much you can spend each day ahead; when a purchase fits")

    def resolve_mortgage_details(self, info, bank_name, account_name, extra_monthly=0.0):
        m = _manager(info)
        if not m:
            return None
        try:
            return tools.mortgage_details(m, bank_name, account_name, extra_monthly or 0.0)
        except tools.ToolError as e:
            raise Exception(str(e))

    def resolve_compare_strategies(self, info, days=90, target_account=""):
        m = _manager(info)
        if not m:
            return []
        try:
            return tools.compare_strategies(m, days or 90, target_account or "")
        except tools.ToolError as e:
            raise Exception(str(e))

    def resolve_strategy_targets(self, info):
        m = _manager(info)
        return tools.credit_targets(m) if m else []

    def resolve_monthly_projection(self, info, days=180):
        from models.report_export import monthly_summary
        m = _manager(info)
        return monthly_summary(m, max(30, min(days or 180, 365))) if m else []

    def resolve_database_info(self, info):
        from models import auth, web_routes
        data = tools.database_info()
        try:
            user = web_routes.current_user()
        except RuntimeError:  # outside a request
            user = None
        if auth.has_users() and not (user and user.get("is_admin")):
            data["path"] = None
        return data

    def resolve_report_kinds(self, info):
        from models.report_export import REPORTS
        return [{"key": k, "description": v} for k, v in REPORTS.items()]

    def resolve_debt_boost(self, info, days=180, strategy="avalanche", monthly=None):
        from models import optimizer_plus
        m = _manager(info)
        if not m:
            return None
        try:
            return optimizer_plus.debt_boost(m, max(30, min(days or 180, 730)), strategy or "avalanche", monthly)
        except ValueError as e:
            raise Exception(str(e))

    def resolve_due_date_moves(self, info, days=100):
        from models import optimizer_plus
        m = _manager(info)
        return optimizer_plus.due_date_moves(m, max(62, min(days or 100, 180))) if m else None

    def resolve_purchase_planner(self, info, amount=0.0, days=60):
        from models import optimizer_plus
        m = _manager(info)
        if not m:
            return None
        try:
            return optimizer_plus.purchase_planner(m, amount or 0.0, max(14, min(days or 60, 365)))
        except ValueError as e:
            raise Exception(str(e))
