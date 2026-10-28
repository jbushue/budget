"""
GraphQL for savings goals / sinking funds, bill-payment matching, and
recurring-charge detection. Mixed into the root schema through gql_ext.
"""

from __future__ import annotations

from datetime import date

import graphene

from models import bill_matching, goals
from models.gql_ledger import LedgerTransactionType


def _manager(info):
    return info.context.get('manager')


def _date(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


class Result(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()


# ─────────────────────────────────────────────────────────────────────────
#  Types
# ─────────────────────────────────────────────────────────────────────────

class SavingsGoalType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    target_amount = graphene.Float()
    saved_amount = graphene.Float()
    remaining = graphene.Float()
    progress = graphene.Float(description="Percent saved, 0-100")
    target_date = graphene.String()
    months_left = graphene.Float()
    monthly_needed = graphene.Float()
    per_paycheck_needed = graphene.Float()
    on_track = graphene.Boolean()
    bank_name = graphene.String()
    account_name = graphene.String()
    in_checking = graphene.Boolean(description="Set aside in checking — reserved out of Safe to spend")
    linked_bill = graphene.String(description="Sinking fund for this bill")
    complete = graphene.Boolean()


class SinkingFundSuggestionType(graphene.ObjectType):
    bill_name = graphene.String()
    amount = graphene.Float()
    frequency = graphene.String()
    next_due = graphene.String()
    monthly = graphene.Float(description="Set aside this much per month to have it ready")


class BillMatchType(graphene.ObjectType):
    transaction = graphene.Field(LedgerTransactionType)
    bill_name = graphene.String()
    due_date = graphene.String()
    confidence = graphene.String(description="high | medium")
    reason = graphene.String()
    amount = graphene.Float()


class RecurringChargeType(graphene.ObjectType):
    key = graphene.String(description="Pass to dismissRecurringCharge")
    name = graphene.String()
    description = graphene.String()
    frequency = graphene.String()
    amount = graphene.Float()
    variable = graphene.Boolean()
    min_amount = graphene.Float()
    max_amount = graphene.Float()
    count = graphene.Int()
    last_date = graphene.String()
    next_expected = graphene.String()
    due_day = graphene.Int()
    category = graphene.String()
    monthly_cost = graphene.Float()


# ─────────────────────────────────────────────────────────────────────────
#  Mutations
# ─────────────────────────────────────────────────────────────────────────

class SaveSavingsGoal(graphene.Mutation):
    """Create a goal, or update one when `id` is given."""
    class Arguments:
        id = graphene.Int()
        name = graphene.String(required=True)
        target_amount = graphene.Float(required=True)
        target_date = graphene.String()
        bank_name = graphene.String()
        account_name = graphene.String()
        saved_amount = graphene.Float()

    Output = Result

    def mutate(self, info, name, target_amount, id=None, target_date=None, bank_name="", account_name="",
               saved_amount=None):
        try:
            goals.save_goal(name, target_amount, _date(target_date), bank_name or "", account_name or "",
                            saved_amount, goal_id=id)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message="Goal saved")


class ContributeToGoal(graphene.Mutation):
    """Record money set aside for a goal (negative = taken back out)."""
    class Arguments:
        id = graphene.Int(required=True)
        amount = graphene.Float(required=True)

    Output = Result

    def mutate(self, info, id, amount):
        try:
            g = goals.contribute(id, amount)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message=f"{g['name']}: ${g['saved_amount']:,.2f} set aside")


class DeleteSavingsGoal(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    Output = Result

    def mutate(self, info, id):
        try:
            goals.delete_goal(id)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message="Goal deleted")


class CreateSinkingFund(graphene.Mutation):
    class Arguments:
        bill_name = graphene.String(required=True)
        bank_name = graphene.String()
        account_name = graphene.String()
        saved_amount = graphene.Float()

    Output = Result

    def mutate(self, info, bill_name, bank_name="", account_name="", saved_amount=0.0):
        try:
            goals.create_sinking_fund(_manager(info), bill_name, bank_name or "", account_name or "",
                                      saved_amount or 0.0)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message=f"Sinking fund created for {bill_name}")


class ConfirmBillMatch(graphene.Mutation):
    """Record a transaction as a bill's payment (no money moves)."""
    class Arguments:
        transaction_id = graphene.Int(required=True)
        bill_name = graphene.String(required=True)

    Output = Result

    def mutate(self, info, transaction_id, bill_name):
        try:
            bill_matching.confirm_match(_manager(info), transaction_id, bill_name)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message=f"Recorded as the {bill_name} payment")


class IgnoreBillMatch(graphene.Mutation):
    """This transaction isn't a bill payment."""
    class Arguments:
        transaction_id = graphene.Int(required=True)

    Output = Result

    def mutate(self, info, transaction_id):
        try:
            bill_matching.ignore_match(transaction_id)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message="Got it — not a bill payment")


class UnmatchTransaction(graphene.Mutation):
    """Undo a bill match and remove the payment it recorded."""
    class Arguments:
        transaction_id = graphene.Int(required=True)

    Output = Result

    def mutate(self, info, transaction_id):
        try:
            bill_matching.unmatch(_manager(info), transaction_id)
        except ValueError as e:
            return Result(success=False, message=str(e))
        return Result(success=True, message="Match removed")


class RunBillMatching(graphene.Mutation):
    """Record high-confidence bill payments found in recent transactions."""
    success = graphene.Boolean()
    message = graphene.String()
    matched = graphene.Int()

    def mutate(self, info):
        n = bill_matching.auto_match(_manager(info))
        return RunBillMatching(success=True, matched=n, message=f"{n} bill payments recorded")


class DismissRecurringCharge(graphene.Mutation):
    class Arguments:
        key = graphene.String(required=True)

    Output = Result

    def mutate(self, info, key):
        bill_matching.dismiss_recurring(key)
        return Result(success=True, message="Dismissed")


# ─────────────────────────────────────────────────────────────────────────
#  Roots
# ─────────────────────────────────────────────────────────────────────────

class GoalsQuery(graphene.ObjectType):
    savings_goals = graphene.List(SavingsGoalType)
    sinking_fund_suggestions = graphene.List(SinkingFundSuggestionType)
    bill_match_suggestions = graphene.List(BillMatchType)
    recurring_charges = graphene.List(RecurringChargeType)

    def resolve_savings_goals(self, info):
        return goals.list_goals(_manager(info))

    def resolve_sinking_fund_suggestions(self, info):
        return goals.sinking_fund_suggestions(_manager(info))

    def resolve_bill_match_suggestions(self, info):
        return bill_matching.suggestions(_manager(info)) if _manager(info) else []

    def resolve_recurring_charges(self, info):
        return bill_matching.detect_recurring(_manager(info))


class GoalsMutation(graphene.ObjectType):
    save_savings_goal = SaveSavingsGoal.Field()
    contribute_to_goal = ContributeToGoal.Field()
    delete_savings_goal = DeleteSavingsGoal.Field()
    create_sinking_fund = CreateSinkingFund.Field()
    confirm_bill_match = ConfirmBillMatch.Field()
    ignore_bill_match = IgnoreBillMatch.Field()
    unmatch_transaction = UnmatchTransaction.Field()
    run_bill_matching = RunBillMatching.Field()
    dismiss_recurring_charge = DismissRecurringCharge.Field()
