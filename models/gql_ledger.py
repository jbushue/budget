"""
GraphQL for the ledger: transactions, categories, rules, budgets and the
spending report. Mixed into the root schema through gql_ext.
"""

from __future__ import annotations

import json
from datetime import date

import graphene

from models import ledger


def _refresh_spending(info) -> None:
    """New transactions can change the learned everyday-spending average."""
    manager = info.context.get('manager')
    if manager:
        from models.app_settings import get_settings
        manager.apply_settings(get_settings())


def _date(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


def _json(value):
    if value in (None, ""):
        return None
    return json.loads(value) if isinstance(value, str) else value


# ─────────────────────────────────────────────────────────────────────────
#  Types
# ─────────────────────────────────────────────────────────────────────────

class LedgerTransactionType(graphene.ObjectType):
    id = graphene.Int()
    date = graphene.String()
    description = graphene.String()
    payee = graphene.String()
    amount = graphene.Float(description="Negative = money out")
    bank_name = graphene.String()
    account_name = graphene.String()
    category = graphene.String()
    source = graphene.String(description="simplefin | csv | manual")
    matched_bill = graphene.String()
    notes = graphene.String()


class TransactionPageType(graphene.ObjectType):
    items = graphene.List(LedgerTransactionType)
    total = graphene.Int()
    total_in = graphene.Float()
    total_out = graphene.Float()


class CategoryType(graphene.ObjectType):
    name = graphene.String()
    kind = graphene.String(description="expense | income | transfer")
    is_everyday = graphene.Boolean()
    monthly_budget = graphene.Float()
    color = graphene.String()


class CategoryRuleType(graphene.ObjectType):
    id = graphene.Int()
    pattern = graphene.String()
    category = graphene.String()
    priority = graphene.Int()


class BudgetLineType(graphene.ObjectType):
    category = graphene.String()
    color = graphene.String()
    is_everyday = graphene.Boolean()
    budget = graphene.Float()
    spent = graphene.Float()
    remaining = graphene.Float()
    percent = graphene.Float()
    projected = graphene.Float(description="Spending at this pace by month end")
    status = graphene.String(description="ok | warning | over | no_budget")


class BudgetStatusType(graphene.ObjectType):
    month = graphene.String()
    days_elapsed = graphene.Int()
    days_in_month = graphene.Int()
    lines = graphene.List(BudgetLineType)
    total_budget = graphene.Float()
    total_spent = graphene.Float()
    total_budgeted_spent = graphene.Float()
    uncategorized_spent = graphene.Float()
    income = graphene.Float()


class SpendingMonthType(graphene.ObjectType):
    month = graphene.String()
    income = graphene.Float()
    spending = graphene.Float()
    net = graphene.Float()
    by_category = graphene.JSONString(description="{category: amount}, largest first")


class SpendingReportType(graphene.ObjectType):
    months = graphene.List(SpendingMonthType)
    colors = graphene.JSONString()


class CsvPreviewRowType(graphene.ObjectType):
    date = graphene.String()
    description = graphene.String()
    amount = graphene.Float()
    category = graphene.String()


class CsvPreviewType(graphene.ObjectType):
    columns = graphene.List(graphene.String)
    mapping = graphene.JSONString()
    rows = graphene.List(CsvPreviewRowType)
    row_count = graphene.Int()
    errors = graphene.List(graphene.String)


class ImportResultType(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    imported = graphene.Int()
    duplicates = graphene.Int()
    matched_bills = graphene.Int()
    errors = graphene.List(graphene.String)


# ─────────────────────────────────────────────────────────────────────────
#  Mutations
# ─────────────────────────────────────────────────────────────────────────

class TxnResult(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    transaction = graphene.Field(LedgerTransactionType)


class AddLedgerTransaction(graphene.Mutation):
    class Arguments:
        date = graphene.String(required=True)
        description = graphene.String(required=True)
        amount = graphene.Float(required=True, description="Negative = money out")
        bank_name = graphene.String()
        account_name = graphene.String()
        category = graphene.String()
        notes = graphene.String()

    Output = TxnResult

    def mutate(self, info, date, description, amount, bank_name="", account_name="", category=None, notes=""):
        try:
            t = ledger.add_transaction(_date(date), description, amount, bank_name or "", account_name or "",
                                       category or None, notes or "")
        except ValueError as e:
            return TxnResult(success=False, message=str(e))
        _refresh_spending(info)
        return TxnResult(success=True, message="Transaction added", transaction=t)


class UpdateLedgerTransaction(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        category = graphene.String(description="Empty string = uncategorized")
        notes = graphene.String()
        description = graphene.String()
        amount = graphene.Float()
        date = graphene.String()
        create_rule = graphene.Boolean(description="Also categorize future/similar transactions the same way")

    Output = TxnResult

    def mutate(self, info, id, category=None, notes=None, description=None, amount=None, date=None,
               create_rule=False):
        fields = {"notes": notes, "description": description, "amount": amount, "txn_date": _date(date)}
        if category is not None:
            fields["category"] = category
        try:
            t = ledger.update_transaction(id, **fields)
            msg = "Saved"
            if create_rule and category:
                key = ledger.normalize_payee(t["description"])
                if len(key) >= 3:
                    r = ledger.add_rule(key, category)
                    msg = f"Saved — rule added for '{key}' ({r.get('applied', 0)} other transactions updated)"
        except ValueError as e:
            return TxnResult(success=False, message=str(e))
        _refresh_spending(info)
        return TxnResult(success=True, message=msg, transaction=t)


class DeleteLedgerTransaction(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            ledger.delete_transaction(id)
        except ValueError as e:
            return DeleteLedgerTransaction(success=False, message=str(e))
        _refresh_spending(info)
        return DeleteLedgerTransaction(success=True, message="Deleted")


class ImportCsvTransactions(graphene.Mutation):
    """Import a bank CSV. With preview=true nothing is saved; returns the first rows."""
    class Arguments:
        content = graphene.String(required=True)
        bank_name = graphene.String(required=True)
        account_name = graphene.String(required=True)
        mapping = graphene.JSONString(description='{"date": 0, "description": 2, "amount": 4} or debit/credit')
        invert = graphene.Boolean(description="Flip signs (file shows purchases as positive)")
        date_format = graphene.String()
        preview = graphene.Boolean()

    result = graphene.Field(ImportResultType)
    preview_data = graphene.Field(CsvPreviewType)

    def mutate(self, info, content, bank_name, account_name, mapping=None, invert=False, date_format=None,
               preview=False):
        mapping = _json(mapping)
        try:
            if preview:
                parsed = ledger.parse_csv(content, mapping, bool(invert), date_format or None)
                rules, cats = ledger.list_rules(), ledger._category_map()
                rows = [{"date": r["date"].isoformat(), "description": r["description"], "amount": r["amount"],
                         "category": ledger.categorize(r["description"], r["amount"], rules, cats)}
                        for r in parsed["rows"][:15]]
                return ImportCsvTransactions(preview_data=CsvPreviewType(
                    columns=parsed["columns"], mapping=parsed["mapping"], rows=rows,
                    row_count=len(parsed["rows"]), errors=parsed["errors"][:20]))
            out = ledger.import_csv(content, bank_name, account_name, mapping, bool(invert), date_format or None)
        except ValueError as e:
            return ImportCsvTransactions(result=ImportResultType(success=False, message=str(e)))
        matched = _after_import(info)
        return ImportCsvTransactions(result=ImportResultType(
            success=True, imported=out["imported"], duplicates=out["duplicates"], matched_bills=matched,
            errors=out["errors"][:20],
            message=f"Imported {out['imported']} transactions ({out['duplicates']} already there)"))


class ImportSimplefinTransactions(graphene.Mutation):
    class Arguments:
        days = graphene.Int()

    result = graphene.Field(ImportResultType)

    def mutate(self, info, days=90):
        try:
            out = ledger.import_simplefin(max(1, min(days or 90, 365)))
        except Exception as e:
            return ImportSimplefinTransactions(result=ImportResultType(success=False, message=str(e)))
        matched = _after_import(info)
        return ImportSimplefinTransactions(result=ImportResultType(
            success=True, imported=out["imported"], duplicates=out["duplicates"], matched_bills=matched,
            errors=out["errors"][:20],
            message=f"Imported {out['imported']} new transactions ({out['duplicates']} already there)"))


def _after_import(info) -> int:
    """Refresh learned spending and (Phase 3) auto-match bills. Returns bills matched."""
    matched = 0
    manager = info.context.get('manager')
    if manager:
        try:
            from models.bill_matching import auto_match
            matched = auto_match(manager)
        except ImportError:
            pass
    _refresh_spending(info)
    return matched


class CategoryResult(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    category = graphene.Field(CategoryType)


class SaveCategory(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        kind = graphene.String()
        is_everyday = graphene.Boolean()
        monthly_budget = graphene.Float()
        color = graphene.String()
        rename_from = graphene.String()

    Output = CategoryResult

    def mutate(self, info, name, kind="expense", is_everyday=False, monthly_budget=None, color=None,
               rename_from=None):
        try:
            c = ledger.upsert_category(name, kind or "expense", bool(is_everyday), monthly_budget, color,
                                       rename_from or None)
        except ValueError as e:
            return CategoryResult(success=False, message=str(e))
        _refresh_spending(info)
        return CategoryResult(success=True, message="Category saved", category=c)


class DeleteCategory(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name):
        try:
            ledger.delete_category(name)
        except ValueError as e:
            return DeleteCategory(success=False, message=str(e))
        _refresh_spending(info)
        return DeleteCategory(success=True, message=f"Deleted '{name}'; its transactions are now uncategorized")


class SetCategoryBudget(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        monthly_budget = graphene.Float(description="Omit or 0 to remove the budget")

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, name, monthly_budget=None):
        try:
            ledger.set_budget(name, monthly_budget or None)
        except ValueError as e:
            return SetCategoryBudget(success=False, message=str(e))
        return SetCategoryBudget(success=True, message="Budget saved")


class AddCategoryRule(graphene.Mutation):
    class Arguments:
        pattern = graphene.String(required=True)
        category = graphene.String(required=True)
        priority = graphene.Int()

    success = graphene.Boolean()
    message = graphene.String()
    rule = graphene.Field(CategoryRuleType)

    def mutate(self, info, pattern, category, priority=0):
        try:
            r = ledger.add_rule(pattern, category, priority or 0)
        except ValueError as e:
            return AddCategoryRule(success=False, message=str(e))
        _refresh_spending(info)
        return AddCategoryRule(success=True, rule=r,
                               message=f"Rule added; {r.get('applied', 0)} transactions recategorized")


class DeleteCategoryRule(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            ledger.delete_rule(id)
        except ValueError as e:
            return DeleteCategoryRule(success=False, message=str(e))
        return DeleteCategoryRule(success=True, message="Rule deleted")


class RecategorizeTransactions(graphene.Mutation):
    class Arguments:
        only_uncategorized = graphene.Boolean()

    success = graphene.Boolean()
    message = graphene.String()
    changed = graphene.Int()

    def mutate(self, info, only_uncategorized=True):
        n = ledger.recategorize(only_uncategorized=bool(only_uncategorized))
        _refresh_spending(info)
        return RecategorizeTransactions(success=True, changed=n, message=f"{n} transactions recategorized")


# ─────────────────────────────────────────────────────────────────────────
#  Roots
# ─────────────────────────────────────────────────────────────────────────

class LedgerQuery(graphene.ObjectType):
    ledger_transactions = graphene.Field(
        TransactionPageType,
        text=graphene.String(), category=graphene.String(), account=graphene.String(description="bank:account"),
        date_from=graphene.String(), date_to=graphene.String(), uncategorized=graphene.Boolean(),
        limit=graphene.Int(), offset=graphene.Int())
    categories = graphene.List(CategoryType)
    category_rules = graphene.List(CategoryRuleType)
    budget_status = graphene.Field(BudgetStatusType, month=graphene.String(description="YYYY-MM"))
    spending_report = graphene.Field(SpendingReportType, months=graphene.Int())
    learned_everyday_weekly = graphene.Float(description="Average weekly everyday spending (null = not enough history)")

    def resolve_ledger_transactions(self, info, text="", category=None, account="", date_from=None, date_to=None,
                                    uncategorized=False, limit=100, offset=0):
        return ledger.search_transactions(text or "", category or None, account or "", _date(date_from),
                                          _date(date_to), bool(uncategorized), limit or 100, offset or 0)

    def resolve_categories(self, info):
        return ledger.list_categories()

    def resolve_category_rules(self, info):
        return ledger.list_rules()

    def resolve_budget_status(self, info, month=None):
        return ledger.budget_status(month or None)

    def resolve_spending_report(self, info, months=6):
        return ledger.spending_report(months or 6)

    def resolve_learned_everyday_weekly(self, info):
        return ledger.learned_everyday_weekly()


class LedgerMutation(graphene.ObjectType):
    add_ledger_transaction = AddLedgerTransaction.Field()
    update_ledger_transaction = UpdateLedgerTransaction.Field()
    delete_ledger_transaction = DeleteLedgerTransaction.Field()
    import_csv_transactions = ImportCsvTransactions.Field()
    import_simplefin_transactions = ImportSimplefinTransactions.Field()
    save_category = SaveCategory.Field()
    delete_category = DeleteCategory.Field()
    set_category_budget = SetCategoryBudget.Field()
    add_category_rule = AddCategoryRule.Field()
    delete_category_rule = DeleteCategoryRule.Field()
    recategorize_transactions = RecategorizeTransactions.Field()
