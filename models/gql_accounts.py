"""
GraphQL for editing banks and accounts after they're created (every
setting, renaming, moving an account to another bank). Mixed into the root
schema through gql_ext. The work is done in models/account_edit.py.
"""

from __future__ import annotations

import graphene

from models import account_edit, min_payment


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
        account_type = graphene.String(required=True, description="checking | savings | ebt | hsa | ... | credit | mortgage | heloc")
        new_name = graphene.String()
        new_bank_name = graphene.String(description="Move the account to this bank")
        new_account_type = graphene.String(description="Change a bank account to another kind (checking, savings, ebt, ...)")
        balance = graphene.Float(description="Balance (owed, for cards and HELOCs)")
        interest_rate = graphene.Float()
        interest_accrual_date = graphene.Int()
        refill_amount = graphene.Float(description="Added each month (EBT benefits, HSA contributions)")
        refill_day = graphene.Int(description="Day of month the refill lands; 0 clears")
        weekly_spending = graphene.Float(description="Spent from this account each week")
        offsets_everyday = graphene.Boolean(description="That spending replaces part of everyday spending")
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
        loan_kind = graphene.String(description="Loans: mortgage | auto | student | personal | other")
        payment_override = graphene.Float(description="Loans: the lender's monthly payment; 0 = calculated")
        value_as_of = graphene.String(description="Loans: date the home/vehicle value was right")
        depreciation_rate = graphene.Float(description="Auto loans: % of the vehicle's value lost a year")
        payments_start = graphene.String(description="Student loans: first payment (YYYY-MM-DD); '' clears")
        subsidized = graphene.Boolean(description="Student loans: no interest before payments start")

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


class ConvertCreditToLoan(graphene.Mutation):
    """
    Turn a card-style account into a loan (student, auto, personal, other):
    same name, bank, balance, APR and due day; the term keeps today's
    minimum payment unless one is given. Loan group membership, the payment
    bill, balance history and the SimpleFIN link carry over.
    """

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        loan_kind = graphene.String(default_value="student")
        term_months = graphene.Int()
        payments_start = graphene.String()
        subsidized = graphene.Boolean()

    Output = EditResult

    def mutate(self, info, bank_name, account_name, loan_kind="student", term_months=None,
               payments_start=None, subsidized=False):
        manager = info.context.get('manager')
        if not manager:
            return EditResult(success=False, message="Manager not available")
        try:
            loan = account_edit.convert_credit_to_loan(manager, bank_name, account_name, loan_kind,
                                                       term_months, payments_start or None, bool(subsidized))
        except account_edit.EditError as e:
            return EditResult(success=False, message=str(e))
        if not manager.save_to_database():
            return EditResult(success=False, message="Changed, but saving to the database failed")
        return EditResult(success=True, name=account_name, message=(
            f"{account_name} is now a {loan.kind_label.lower()}: ${loan.total_monthly_payment:,.2f} a month "
            f"for {loan.remaining_months} months"))


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


class MinRuleOption(graphene.ObjectType):
    rule = graphene.JSONString()
    label = graphene.String()
    amount = graphene.Float(description="The minimum this rule gives on the statement entered")
    off = graphene.Float(description="How far that is from the statement's minimum (close matches only)")


class MinPaymentMatch(graphene.ObjectType):
    best = graphene.JSONString(description="The rule to use (null: none can be told from this statement)")
    best_label = graphene.String()
    matches = graphene.List(MinRuleOption, description="Every rule that gives this minimum, best first")
    ambiguous = graphene.Boolean(description="More than one rule fits; another statement can tell them apart")
    close = graphene.Boolean(description="No rule fits exactly; best is the nearest one")
    message = graphene.String()
    balance_used = graphene.Float()
    interest_used = graphene.Float()
    interest_estimated = graphene.Boolean()
    current_rule_label = graphene.String()
    current_minimum = graphene.Float(description="What the current rule gives on this statement")


def _card(manager, bank_name, account_name):
    bank = next((b for b in manager.banks if b.name == bank_name), None)
    card = bank.credit_accounts.get(account_name) if bank else None
    if card is None:
        raise account_edit.EditError(f"Card '{account_name}' not found in {bank_name}")
    return card


class AccountsQuery(graphene.ObjectType):
    minimum_payment_match = graphene.Field(
        MinPaymentMatch, bank_name=graphene.String(required=True), account_name=graphene.String(required=True),
        minimum_payment=graphene.Float(required=True),
        statement_balance=graphene.Float(description="Default: the card's balance now"),
        interest_charged=graphene.Float(description="Interest on the statement. Default: estimated from the APR"),
        description="Which minimum payment rules give the minimum on a statement (nothing is saved)")

    def resolve_minimum_payment_match(self, info, bank_name, account_name, minimum_payment,
                                      statement_balance=None, interest_charged=None):
        card = _card(info.context['manager'], bank_name, account_name)
        balance = card.balance if statement_balance is None else float(statement_balance)
        estimated = interest_charged is None
        if estimated:
            promo = sum(card.promo_balance.values())
            interest = round(min_payment.monthly_interest(balance - promo, card.interest_rate), 2)
        else:
            interest = max(0.0, float(interest_charged))
        try:
            found = min_payment.match(float(minimum_payment), balance, interest, interest_known=not estimated)
        except ValueError as e:
            raise account_edit.EditError(str(e)) from None
        current = getattr(card, "min_rule", None)
        return MinPaymentMatch(
            best=found["best"], best_label=min_payment.describe(found["best"]) if found["best"] else None,
            matches=[MinRuleOption(rule=m["rule"], label=m["label"], amount=m["amount"], off=m.get("off"))
                     for m in found["matches"]],
            ambiguous=found["ambiguous"], close=found.get("close", False), message=found["message"], balance_used=balance,
            interest_used=interest, interest_estimated=estimated,
            current_rule_label=min_payment.describe(current) + ("" if current else " (default)"),
            current_minimum=min_payment.amount(current, balance, interest))


class SetMinimumPaymentRule(graphene.Mutation):
    """Use a minimum payment rule for a card (from minimumPaymentMatch); no rule = the default."""

    class Arguments:
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        rule = graphene.JSONString(description='e.g. {"pct": 1, "interest": true, "floor": 25} or {"fixed": 75}')

    Output = EditResult

    def mutate(self, info, bank_name, account_name, rule=None):
        manager = info.context.get('manager')
        if not manager:
            return EditResult(success=False, message="Manager not available")
        try:
            card = _card(manager, bank_name, account_name)
        except account_edit.EditError as e:
            return EditResult(success=False, message=str(e))
        clean = min_payment.normalize(rule) if rule else None
        if rule and clean is None:
            return EditResult(success=False, message="That isn't a valid minimum payment rule")
        card.min_rule = clean
        if not manager.save_to_database():
            return EditResult(success=False, message="Changed, but saving to the database failed")
        return EditResult(success=True, name=account_name,
                          message=f"{account_name}: minimum is {min_payment.describe(clean)}"
                                  f"{'' if clean else ' (default)'} — now ${card.calculate_minimum_payment():,.2f}")


class AccountsMutation(graphene.ObjectType):
    update_account = UpdateAccount.Field()
    convert_credit_to_loan = ConvertCreditToLoan.Field()
    update_bank = UpdateBank.Field()
    set_minimum_payment_rule = SetMinimumPaymentRule.Field()
