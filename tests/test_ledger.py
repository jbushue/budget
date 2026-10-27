"""Tests for the ledger: categories, rules, CSV import, budgets, learned spending."""

from datetime import date, timedelta

import pytest

from models import ledger
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date(2026, 3, 20)


class TestCategorize:

    def test_keywords_match_at_word_start(self, temp_db):  # noqa: F811
        assert ledger.categorize("KROGER #123 COLUMBUS OH", -50) == "Groceries"
        assert ledger.categorize("Starbucks coffee", -5) == "Dining"
        # "coffee" must not hit the "fee" keyword, "parent" must not hit "rent"
        assert ledger.categorize("Local Coffee Roasters", -12) == "Dining"
        assert ledger.categorize("Parent teacher assoc", -10) != "Housing"
        assert ledger.categorize("Monthly service fee", -12) == "Fees & Interest"

    def test_user_rules_win_and_income_fallback(self, temp_db):  # noqa: F811
        ledger.add_rule("kroger", "Household")
        assert ledger.categorize("KROGER FUEL", -40) == "Household"
        assert ledger.categorize("ACME CORP", 1500) == "Income"
        assert ledger.categorize("Something odd", -3) is None

    def test_normalize_payee(self):
        assert ledger.normalize_payee("POS DEBIT KROGER #1234 COLUMBUS OH 10/12") == "kroger columbus"
        assert ledger.normalize_payee("NETFLIX.COM 866-579-7172 CA") == "netflix com"


class TestCsvImport:
    CHASE = (
        "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
        "03/01/2026,03/02/2026,KROGER #55,Groceries,Sale,-82.15,\n"
        "03/03/2026,03/03/2026,SHELL OIL 123,Gas,Sale,-40.00,\n"
        "03/05/2026,03/05/2026,PAYROLL ACME,,,2000.00,\n"
        "bad,03/05/2026,BROKEN,,,1,\n"
    )

    def test_detects_columns_and_imports(self, temp_db):  # noqa: F811
        parsed = ledger.parse_csv(self.CHASE)
        assert parsed["mapping"]["date"] == 0 and parsed["mapping"]["description"] == 2
        assert parsed["mapping"]["amount"] == 5
        assert len(parsed["rows"]) == 3 and len(parsed["errors"]) == 1

        out = ledger.import_csv(self.CHASE, "Chase", "Checking")
        assert out["imported"] == 3
        cats = {t["description"]: t["category"] for t in ledger.search_transactions()["items"]}
        assert cats == {"KROGER #55": "Groceries", "SHELL OIL 123": "Gas & Transport", "PAYROLL ACME": "Income"}

    def test_reimport_skips_duplicates(self, temp_db):  # noqa: F811
        ledger.import_csv(self.CHASE, "Chase", "Checking")
        again = ledger.import_csv(self.CHASE, "Chase", "Checking")
        assert again == {"imported": 0, "duplicates": 3, "errors": again["errors"]}

    def test_debit_credit_columns_and_parentheses(self, temp_db):  # noqa: F811
        csv_text = ("Date,Details,Debit,Credit\n"
                    "2026-03-01,ALDI 77,\"$1,020.50\",\n"
                    "2026-03-02,Refund,,15.00\n"
                    "2026-03-03,Fee,(5.00),\n")
        rows = ledger.parse_csv(csv_text)["rows"]
        assert [r["amount"] for r in rows] == [-1020.5, 15.0, -5.0]

    def test_invert_and_missing_columns(self, temp_db):  # noqa: F811
        rows = ledger.parse_csv("Date,Name,Amount\n01/02/2026,Target,25.00\n", invert=True)["rows"]
        assert rows[0]["amount"] == -25.0
        with pytest.raises(ValueError):
            ledger.parse_csv("Foo,Bar\n1,2\n")


class TestCategoriesAndBudgets:

    def test_rename_moves_transactions_and_rules(self, temp_db):  # noqa: F811
        ledger.add_transaction(TODAY, "Kroger", -10, category="Groceries")
        ledger.add_rule("kroger", "Groceries")
        ledger.upsert_category("Food", "expense", True, 400, rename_from="Groceries")
        assert ledger.search_transactions()["items"][0]["category"] == "Food"
        assert ledger.list_rules()[0]["category"] == "Food"
        ledger.delete_category("Food")
        assert ledger.search_transactions()["items"][0]["category"] is None
        assert ledger.list_rules() == []

    def test_budget_status_projects_pace(self, temp_db):  # noqa: F811
        ledger.set_budget("Groceries", 300)
        ledger.add_transaction(date(2026, 3, 2), "Kroger", -150, category="Groceries")
        ledger.add_transaction(date(2026, 3, 9), "Kroger refund", 20, category="Groceries")
        ledger.add_transaction(date(2026, 3, 10), "Amazon", -60, category="Shopping")
        ledger.add_transaction(date(2026, 3, 11), "Mystery", -7)
        ledger.add_transaction(date(2026, 2, 27), "Kroger", -999, category="Groceries")  # last month
        s = ledger.budget_status("2026-03", today=TODAY)
        g = next(line for line in s["lines"] if line["category"] == "Groceries")
        assert g["spent"] == 130 and g["remaining"] == 170
        # 130 over 20 days -> ~201 by month end: still ok
        assert g["status"] == "ok" and g["projected"] == pytest.approx(130 / 20 * 31, abs=0.01)
        shopping = next(line for line in s["lines"] if line["category"] == "Shopping")
        assert shopping["status"] == "no_budget"
        assert s["uncategorized_spent"] == 7
        ledger.set_budget("Groceries", 150)
        g = next(line for line in ledger.budget_status("2026-03", today=TODAY)["lines"]
                 if line["category"] == "Groceries")
        assert g["status"] == "warning"

    def test_spending_report_skips_transfers(self, temp_db):  # noqa: F811
        ledger.add_transaction(date(2026, 3, 1), "Payroll", 2000, category="Income")
        ledger.add_transaction(date(2026, 3, 2), "Kroger", -100, category="Groceries")
        ledger.add_transaction(date(2026, 3, 3), "To savings", -500, category="Transfer")
        r = ledger.spending_report(2, today=TODAY)
        march = r["months"][-1]
        assert (march["income"], march["spending"], march["net"]) == (2000, 100, 1900)
        assert march["by_category"] == {"Groceries": 100}


class TestLearnedSpending:

    def test_needs_three_weeks(self, temp_db):  # noqa: F811
        ledger.add_transaction(TODAY - timedelta(days=10), "Kroger", -100, category="Groceries")
        assert ledger.learned_everyday_weekly(today=TODAY) is None

    def test_averages_everyday_only(self, temp_db):  # noqa: F811
        for week in range(8):
            ledger.add_transaction(TODAY - timedelta(days=7 * week + 1), "Kroger", -100, category="Groceries")
        ledger.add_transaction(TODAY - timedelta(days=3), "Rent", -1500, category="Housing")  # not everyday
        t = ledger.add_transaction(TODAY - timedelta(days=4), "Kroger", -700, category="Groceries")
        ledger.update_transaction(t["id"], matched_bill="Grocery bill")  # already a bill
        weekly = ledger.learned_everyday_weekly(today=TODAY)
        assert weekly == pytest.approx(800 / ((TODAY - (TODAY - timedelta(days=50))).days / 7), abs=0.01)


class TestLedgerApi:

    def test_add_update_rule_and_learned_mode(self, api):  # noqa: F811
        d = api('mutation { addLedgerTransaction(date: "2026-03-01", description: "TRADER JOES #9", amount: -45) '
                '{ success transaction { id category } } }')["addLedgerTransaction"]
        assert d["success"] and d["transaction"]["category"] == "Groceries"
        api('mutation { addLedgerTransaction(date: "2026-03-02", description: "CORNER STORE 1", amount: -9) '
            '{ success } }')
        page = api('{ ledgerTransactions(uncategorized: true) { total items { id description } } }')
        assert page["ledgerTransactions"]["total"] == 1
        tid = page["ledgerTransactions"]["items"][0]["id"]
        u = api('mutation($id: Int!) { updateLedgerTransaction(id: $id, category: "Household", createRule: true) '
                '{ success message } }', id=tid)["updateLedgerTransaction"]
        assert u["success"] and "corner store" in u["message"]
        assert api('{ categoryRules { pattern category } }')["categoryRules"] == [
            {"pattern": "corner store", "category": "Household"}]

        api('mutation { setCategoryBudget(name: "Groceries", monthlyBudget: 400) { success } }')
        b = api('{ budgetStatus(month: "2026-03") { lines { category budget spent } } }')["budgetStatus"]["lines"]
        assert {"category": "Groceries", "budget": 400, "spent": 45} in b

        # Learned mode falls back to manual without enough history
        api('mutation { updateSettings(changes: "{\\"spending_mode\\": \\"learned\\", \\"everyday_weekly\\": 70}") '
            '{ success } }')
        assert api.manager.everyday_spending["mode"] == "manual"

    def test_csv_preview_then_import(self, api):  # noqa: F811
        content = TestCsvImport.CHASE
        p = api('mutation($c: String!) { importCsvTransactions(content: $c, bankName: "B", accountName: "Chk", '
                'preview: true) { previewData { columns mapping rowCount errors rows { description category } } } }',
                c=content)["importCsvTransactions"]["previewData"]
        assert p["rowCount"] == 3 and p["rows"][0]["category"] == "Groceries"
        assert api('{ ledgerTransactions { total } }')["ledgerTransactions"]["total"] == 0
        r = api('mutation($c: String!, $m: JSONString) { importCsvTransactions(content: $c, bankName: "B", '
                'accountName: "Chk", mapping: $m) { result { success imported duplicates message } } }',
                c=content, m=p["mapping"])["importCsvTransactions"]["result"]
        assert r["success"] and r["imported"] == 3
