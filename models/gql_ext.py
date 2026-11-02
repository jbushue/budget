"""
GraphQL types, queries and mutations for the planning features:
settings and the dashboard summary (and, as they're added, transactions,
budgets, goals, and alerts — see the other gql_ext_* sections below).

Mixed into the root Query/Mutation in graphql_schema.py.
"""

from __future__ import annotations

import graphene

from models import app_settings
from models.gql_accounts import AccountsMutation
from models.gql_bills import BillsMutation, BillsQuery
from models.gql_goals import GoalsMutation, GoalsQuery
from models.gql_ledger import LedgerMutation, LedgerQuery
from models.gql_planning import PlanningMutation, PlanningQuery
from models.gql_tools import ToolsMutation, ToolsQuery


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
    other_money = graphene.JSONString(description="Benefits, other cash, savings and investments outside checking")
    near_lowest = graphene.Float(description="Lowest checking before the second paycheck")
    parked_at_lowest = graphene.Float(description="Of the lowest point, money the plan keeps in savings or puts toward debt early")
    held_for_later = graphene.Float(description="Money kept for bills after the next paycheck")
    held_for = graphene.JSONString(description="The biggest payments that money is kept for")
    plan_series = graphene.JSONString(description="Checking each day of the look-ahead, following the plan (money it parks counted)")
    lookahead_days = graphene.Int()
    plan_goal = graphene.String(description="The plan the app follows")
    plan_target = graphene.String()


# ─────────────────────────────────────────────────────────────────────────
#  Alerts
# ─────────────────────────────────────────────────────────────────────────

class AlertType(graphene.ObjectType):
    key = graphene.String(description="Pass to dismissAlert")
    severity = graphene.String(description="danger | warning | info")
    title = graphene.String()
    detail = graphene.String()
    link = graphene.String(description="Page in the web UI to deal with it")
    date = graphene.String()


class DismissAlert(graphene.Mutation):
    """Hide an alert. `days` snoozes it; omit to hide it until the situation changes."""
    class Arguments:
        key = graphene.String(required=True)
        days = graphene.Int()

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, key, days=None):
        from models import alerts
        alerts.dismiss(key, days)
        return DismissAlert(success=True, message="Dismissed")


class SendDigestEmail(graphene.Mutation):
    """Send the daily digest email now (to test the SMTP settings)."""
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info):
        from models import alerts
        manager = _manager(info)
        if not manager:
            return SendDigestEmail(success=False, message="Manager not available")
        try:
            return SendDigestEmail(success=True, message=alerts.send_digest(manager, force=True))
        except Exception as e:
            return SendDigestEmail(success=False, message=f"Couldn't send: {e}")


class SendTestPush(graphene.Mutation):
    """Send a test push notification (to check the ntfy settings)."""
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info):
        from models import notify
        try:
            return SendTestPush(success=True, message=notify.send_test())
        except (ValueError, OSError) as e:
            return SendTestPush(success=False, message=str(e))


# ─────────────────────────────────────────────────────────────────────────
#  Roots
# ─────────────────────────────────────────────────────────────────────────

class ExtQuery(LedgerQuery, GoalsQuery, PlanningQuery, ToolsQuery, BillsQuery, graphene.ObjectType):
    settings = graphene.JSONString(description="App settings (secrets omitted)")
    dashboard_summary = graphene.Field(DashboardSummaryType)
    alerts = graphene.List(AlertType, include_dismissed=graphene.Boolean())
    digest_preview = graphene.String(description="Today's digest email text")
    digest_html = graphene.String(description="Today's digest email as HTML (what the email looks like)")
    account_kinds = graphene.JSONString(description="Kinds of bank account and how the planner treats each")
    job_status = graphene.JSONString(description="Last result of each background job")
    activity = graphene.JSONString(limit=graphene.Int(), before_id=graphene.Int(), username=graphene.String(),
                                   description="Who changed what, newest first")

    def resolve_activity(self, info, limit=50, before_id=None, username=None):
        from models import activity
        return activity.recent(limit or 50, before_id, username or None)

    def resolve_job_status(self, info):
        from models import jobs
        return jobs.status()

    def resolve_settings(self, info):
        return app_settings.public_settings()

    def resolve_dashboard_summary(self, info):
        manager = _manager(info)
        if not manager:
            return None
        from models.dashboard import build_dashboard
        return build_dashboard(manager)

    def resolve_alerts(self, info, include_dismissed=False):
        manager = _manager(info)
        if not manager:
            return []
        from models.alerts import build_alerts
        return build_alerts(manager, include_dismissed=bool(include_dismissed))

    def resolve_account_kinds(self, info):
        from models.types import ACCOUNT_KINDS
        return [dict(v, value=k) for k, v in ACCOUNT_KINDS.items()]

    def resolve_digest_html(self, info):
        manager = _manager(info)
        if not manager:
            return None
        from models.alerts import digest_html
        return digest_html(manager)

    def resolve_digest_preview(self, info):
        manager = _manager(info)
        if not manager:
            return None
        from models.alerts import digest_text
        subject, body = digest_text(manager)
        return f"Subject: {subject}\n\n{body}"


class ExtMutation(LedgerMutation, GoalsMutation, AccountsMutation, PlanningMutation, ToolsMutation,
                  BillsMutation, graphene.ObjectType):
    update_settings = UpdateSettings.Field()
    dismiss_alert = DismissAlert.Field()
    send_digest_email = SendDigestEmail.Field()
    send_test_push = SendTestPush.Field()
