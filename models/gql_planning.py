"""
GraphQL for assets and net worth, the monthly plan (left to budget), the
financial health check, subscriptions and the year in review. Mixed into the
root schema through gql_ext. The work is done in models/assets.py and
models/planning.py.
"""

from __future__ import annotations

import graphene

from models import assets, planning


def _manager(info):
    return info.context.get('manager')


# ─────────────────────────────────────────────────────────────────────────
#  Assets & net worth
# ─────────────────────────────────────────────────────────────────────────

class AssetType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    kind = graphene.String(description="vehicle | investment | retirement | property | cash | valuables | other")
    kind_label = graphene.String()
    value = graphene.Float()
    notes = graphene.String()
    linked_bank = graphene.String()
    linked_account = graphene.String()
    loan_balance = graphene.Float(description="Owed on the linked loan account, if any")
    loan_kind = graphene.String()
    equity = graphene.Float()
    updated = graphene.String()


class AssetValuePointType(graphene.ObjectType):
    date = graphene.String()
    value = graphene.Float()


class KindValueType(graphene.ObjectType):
    kind = graphene.String()
    value = graphene.Float()


class HomeValueType(graphene.ObjectType):
    name = graphene.String()
    bank = graphene.String()
    value = graphene.Float()
    owed = graphene.Float()
    kind = graphene.String(description="Property (a mortgage's home) or Vehicle (an auto loan's)")
    loan_kind = graphene.String()


class NetWorthBreakdownType(graphene.ObjectType):
    cash = graphene.Float(description="Checking and savings accounts")
    assets_by_kind = graphene.List(KindValueType)
    debts = graphene.List(KindValueType)
    total_assets = graphene.Float()
    total_debt = graphene.Float()
    net_worth = graphene.Float()
    assets = graphene.List(AssetType)
    homes = graphene.List(HomeValueType, description="Home and vehicle values from loans, counted as assets")


class AssetKindType(graphene.ObjectType):
    kind = graphene.String()
    label = graphene.String()


class AssetResult(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    asset = graphene.Field(AssetType)


def _snapshot(manager):
    try:
        manager.record_net_worth_snapshot()
    except Exception:  # noqa: BLE001 - the history is a nicety
        pass


class SaveAsset(graphene.Mutation):
    """Add an asset (no id) or edit one. A changed value is added to its value history."""
    class Arguments:
        id = graphene.Int()
        name = graphene.String(required=True)
        kind = graphene.String()
        value = graphene.Float(required=True)
        notes = graphene.String()
        linked_bank = graphene.String(description="Loan against it (with linkedAccount); empty for none")
        linked_account = graphene.String()

    Output = AssetResult

    def mutate(self, info, name, value, id=None, kind="other", notes="", linked_bank="", linked_account=""):
        manager = _manager(info)
        try:
            a = assets.save_asset(name, kind or "other", value, notes or "", linked_bank or "", linked_account or "",
                                  asset_id=id, manager=manager)
        except ValueError as e:
            return AssetResult(success=False, message=str(e))
        if manager:
            _snapshot(manager)
        return AssetResult(success=True, message=f"Saved {a['name']}", asset=a)


class DeleteAsset(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            assets.delete_asset(id)
        except ValueError as e:
            return DeleteAsset(success=False, message=str(e))
        manager = _manager(info)
        if manager:
            _snapshot(manager)
        return DeleteAsset(success=True, message="Deleted")


# ─────────────────────────────────────────────────────────────────────────
#  Monthly plan, health, subscriptions, year in review
# ─────────────────────────────────────────────────────────────────────────

class MonthlyPlanType(graphene.ObjectType):
    income = graphene.Float(description="Expected income in a typical month")
    bills = graphene.Float(description="All bills, as a monthly amount")
    debt_payments = graphene.Float(description="The part of bills that pays cards and loans")
    budgets = graphene.Float(description="Category budgets")
    goal_saving = graphene.Float(description="What goals need each month to finish on time")
    left_to_budget = graphene.Float()
    status = graphene.String(description="unassigned | balanced | over")


class HealthFactorType(graphene.ObjectType):
    key = graphene.String()
    label = graphene.String()
    score = graphene.Int(description="0-100")
    value = graphene.String()
    detail = graphene.String()
    tip = graphene.String(description="What to do about it (empty when it's good)")
    status = graphene.String(description="good | fair | poor")
    weight = graphene.Int()


class HealthCheckType(graphene.ObjectType):
    score = graphene.Int(description="0-100; null until there's enough data")
    grade = graphene.String()
    factors = graphene.List(HealthFactorType)
    top_tips = graphene.List(graphene.String)


class SubscriptionType(graphene.ObjectType):
    name = graphene.String()
    source = graphene.String(description="bill (transactions matched to a bill) | payee | scheduled (bill, no transactions yet)")
    frequency = graphene.String()
    amount = graphene.Float(description="Latest charge")
    usual_amount = graphene.Float()
    monthly_cost = graphene.Float()
    yearly_cost = graphene.Float()
    last_date = graphene.String()
    next_expected = graphene.String()
    category = graphene.String()
    count = graphene.Int()
    price_increase = graphene.Float(description="Latest charge minus the usual amount, when it went up >5%")


class SubscriptionsType(graphene.ObjectType):
    items = graphene.List(SubscriptionType)
    monthly_total = graphene.Float()
    yearly_total = graphene.Float()
    price_increases = graphene.List(graphene.String)


class ReviewMonthType(graphene.ObjectType):
    month = graphene.String()
    income = graphene.Float()
    spending = graphene.Float()
    net = graphene.Float()


class ReviewCategoryType(graphene.ObjectType):
    name = graphene.String()
    amount = graphene.Float()
    color = graphene.String()
    share = graphene.Float(description="% of the year's spending")


class ReviewAmountType(graphene.ObjectType):
    name = graphene.String()
    amount = graphene.Float()


class ReviewTagType(graphene.ObjectType):
    tag = graphene.String()
    amount = graphene.Float()


class ReviewPurchaseType(graphene.ObjectType):
    date = graphene.String()
    description = graphene.String()
    amount = graphene.Float()
    category = graphene.String()


class YearReviewType(graphene.ObjectType):
    year = graphene.Int()
    has_data = graphene.Boolean()
    income = graphene.Float()
    spending = graphene.Float()
    saved = graphene.Float()
    savings_rate = graphene.Float()
    months = graphene.List(ReviewMonthType)
    average_monthly_spending = graphene.Float()
    biggest_month = graphene.String()
    top_categories = graphene.List(ReviewCategoryType)
    top_payees = graphene.List(ReviewAmountType)
    largest_purchases = graphene.List(ReviewPurchaseType)
    by_tag = graphene.List(ReviewTagType)
    transaction_count = graphene.Int()


# ─────────────────────────────────────────────────────────────────────────
#  Roots
# ─────────────────────────────────────────────────────────────────────────

class PlanningQuery(graphene.ObjectType):
    assets = graphene.List(AssetType)
    asset_kinds = graphene.List(AssetKindType)
    asset_history = graphene.List(AssetValuePointType, id=graphene.Int(required=True))
    net_worth_breakdown = graphene.Field(NetWorthBreakdownType)
    monthly_plan = graphene.Field(MonthlyPlanType)
    health_check = graphene.Field(HealthCheckType)
    subscriptions = graphene.Field(SubscriptionsType)
    year_review = graphene.Field(YearReviewType, year=graphene.Int())

    def resolve_assets(self, info):
        return assets.list_assets(_manager(info))

    def resolve_asset_kinds(self, info):
        return [{"kind": k, "label": v} for k, v in assets.KINDS.items()]

    def resolve_asset_history(self, info, id):
        return assets.asset_history(id)

    def resolve_net_worth_breakdown(self, info):
        manager = _manager(info)
        return assets.net_worth_breakdown(manager) if manager else None

    def resolve_monthly_plan(self, info):
        manager = _manager(info)
        return planning.monthly_plan(manager) if manager else None

    def resolve_health_check(self, info):
        manager = _manager(info)
        return planning.health_check(manager) if manager else None

    def resolve_subscriptions(self, info):
        manager = _manager(info)
        return planning.subscriptions(manager) if manager else None

    def resolve_year_review(self, info, year=None):
        return planning.year_review(year or None)


class PlanningMutation(graphene.ObjectType):
    save_asset = SaveAsset.Field()
    delete_asset = DeleteAsset.Field()
