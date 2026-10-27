"""
GraphQL types, queries and mutations for the planning features:
settings and the dashboard summary (and, as they're added, transactions,
budgets, goals, and alerts — see the other gql_ext_* sections below).

Mixed into the root Query/Mutation in graphql_schema.py.
"""

from __future__ import annotations

import graphene

from models import app_settings
from models.gql_goals import GoalsMutation, GoalsQuery
from models.gql_ledger import LedgerMutation, LedgerQuery


def _manager(info):
    return info.context.get('manager')


# ─────────────────────────────────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────────────────────────────────

class UpdateSettings(graphene.Mutation):
    """Change app settings. `changes` is a JSON object of {setting: value}."""
    class Arguments:
        changes = graphene.JSONString(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    settings = graphene.JSONString()

    def mutate(self, info, changes):
        import json
        data = json.loads(changes) if isinstance(changes, str) else (changes or {})
        if not isinstance(data, dict):
            return UpdateSettings(success=False, message="changes must be a JSON object")
        if "password_hash" in data:
            return UpdateSettings(success=False, message="Use the password settings to change the password")
        try:
            new = app_settings.update_settings(data)
        except ValueError as e:
            return UpdateSettings(success=False, message=str(e))
        manager = _manager(info)
        if manager:
            manager.apply_settings(new)
        return UpdateSettings(success=True, message="Settings saved", settings=app_settings.public_settings(new))


# ─────────────────────────────────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────────────────────────────────

class PeriodBillType(graphene.ObjectType):
    """A bill in the current pay period (or overdue)."""
    name = graphene.String()
    bill_name = graphene.String(description="Name to pass to markBillPaid")
    kind = graphene.String()
    due_date = graphene.String()
    amount = graphene.Float()
    status = graphene.String(description="paid | covered | covered_by_plan | short | overdue")
    short_by = graphene.Float()
    days_overdue = graphene.Int()
    source_account = graphene.String()


class DashboardIncomeType(graphene.ObjectType):
    date = graphene.String()
    name = graphene.String()
    amount = graphene.Float()


class DashboardInsightType(graphene.ObjectType):
    severity = graphene.String()
    category = graphene.String()
    title = graphene.String()
    detail = graphene.String()
    impact = graphene.Float()
    date = graphene.String()


class DashboardSummaryType(graphene.ObjectType):
    """Everything the top of the dashboard needs, from one simulation."""
    status = graphene.String(description="ok | warning | danger")
    status_title = graphene.String()
    status_detail = graphene.String()
    safe_to_spend = graphene.Float(description="Extra you can spend before going below your cushion")
    safe_per_day = graphene.Float()
    lowest_balance = graphene.Float()
    lowest_date = graphene.String()
    checking_now = graphene.Float()
    cushion = graphene.Float()
    overdue_total = graphene.Float()
    short_total = graphene.Float(description="Bills in the window that can't be paid (held back)")
    goal_reserves = graphene.Float()
    everyday_weekly = graphene.Float()
    spending_mode = graphene.String()
    next_payday = graphene.String()
    horizon = graphene.String()
    covered_through = graphene.String()
    bills_this_period = graphene.List(PeriodBillType)
    upcoming_income = graphene.List(DashboardIncomeType)
    insights = graphene.List(DashboardInsightType)
    headline = graphene.String()


# ─────────────────────────────────────────────────────────────────────────
#  Roots
# ─────────────────────────────────────────────────────────────────────────

class ExtQuery(LedgerQuery, GoalsQuery, graphene.ObjectType):
    settings = graphene.JSONString(description="App settings (secrets omitted)")
    dashboard_summary = graphene.Field(DashboardSummaryType)

    def resolve_settings(self, info):
        return app_settings.public_settings()

    def resolve_dashboard_summary(self, info):
        manager = _manager(info)
        if not manager:
            return None
        from models.dashboard import build_dashboard
        return build_dashboard(manager)


class ExtMutation(LedgerMutation, GoalsMutation, graphene.ObjectType):
    update_settings = UpdateSettings.Field()
