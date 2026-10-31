"""
GraphQL for editing banks and accounts after they're created (every
setting, renaming, moving an account to another bank). Mixed into the root
schema through gql_ext. The work is done in models/account_edit.py.
"""

from __future__ import annotations

import graphene

from models import account_edit


class EditResult(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    name = graphene.String(description="The bank's / account's name after the change")


class UpdateAccount(graphene.Mutation):
    """
    Edit any account. Only the arguments given change. Day fields take 0 to
    clear them (interest day, statement day); market value 0 clears it; an
    empty pay-from bank clears the pay-from account.
    """

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        account_type = graphene.String(required=True, description="checking | savings | credit | mortgage | heloc")
        new_name = graphene.String()
        new_bank_name = graphene.String(description="Move the account to this bank")
        new_account_type = graphene.String(description="checking <-> savings")
        balance = graphene.Float(description="Balance (owed, for cards and HELOCs)")
        interest_rate = graphene.Float()
        interest_accrual_date = graphene.Int()
        credit_limit = graphene.Float()
        payment_due_date = graphene.Int()
        statement_date = graphene.Int()
        status = graphene.String(description="Cards: active | closed | frozen")
        original_principal = graphene.Float()
        current_principal = graphene.Float()
        loan_term_months = graphene.Int()
        start_date = graphene.String()
        escrow_property_tax = graphene.Float()
        escrow_insurance = graphene.Float()
        escrow_pmi = graphene.Float()
        escrow_hoa = graphene.Float()
        escrow_other = graphene.Float()
        market_value = graphene.Float()
        preferred_source_bank = graphene.String()
        preferred_source_account = graphene.String()
        draw_period_months = graphene.Int()
        total_term_months = graphene.Int()

    Output = EditResult

    def mutate(self, info, bank_name, account_name, account_type, new_name=None, new_bank_name=None,
               new_account_type=None, **fields):
        manager = info.context.get('manager')
        if not manager:
            return EditResult(success=False, message="Manager not available")
        changes = dict(fields, name=new_name, bank_name=new_bank_name, account_type=new_account_type)
        try:
            name = account_edit.update_account(manager, account_type, bank_name, account_name, changes)
        except account_edit.EditError as e:
            return EditResult(success=False, message=str(e))
        if not manager.save_to_database():
            return EditResult(success=False, message="Changed, but saving to the database failed")
        return EditResult(success=True, message=f"Saved {name}", name=name)


class UpdateBank(graphene.Mutation):
    """Rename a bank (everything that refers to it follows) and/or change its type."""

    class Arguments:
        name = graphene.String(required=True)
        new_name = graphene.String()
        bank_type = graphene.String(description="traditional | credit_issuer | mortgage_lender")

    Output = EditResult

    def mutate(self, info, name, new_name=None, bank_type=None):
        manager = info.context.get('manager')
        if not manager:
            return EditResult(success=False, message="Manager not available")
        try:
            name = account_edit.update_bank(manager, name, new_name, bank_type)
        except account_edit.EditError as e:
            return EditResult(success=False, message=str(e))
        if not manager.save_to_database():
            return EditResult(success=False, message="Changed, but saving to the database failed")
        return EditResult(success=True, message=f"Saved {name}", name=name)


class AccountsMutation(graphene.ObjectType):
    update_account = UpdateAccount.Field()
    update_bank = UpdateBank.Field()
