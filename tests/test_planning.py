"""Tests for splits, tags, filters and export, budget rollover and suggestions, assets and
net worth, the monthly plan, the health check, subscriptions and the year in review."""

from datetime import date, timedelta

import pytest

from models import assets, ledger, planning
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date(2026, 3, 20)


def _add(day, desc, amount, category=None, tags=None):
    return ledger.add_transaction(day, desc, amount, "B", "Chk", category, tags=tags)


class TestSplits:

    def test_split_counts_in_each_category(self, temp_db):  # noqa: F811
        t = _add(date(2026, 3, 5), "TARGET 123", -100, "Shopping")
        t = ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 60},
                                        {"category": "Household", "amount": 40, "note": "towels"}])
        assert t["category"] is None
        assert [(s["category"], s["amount"]) for s in t["splits"]] == [("Groceries", -60), ("Household", -40)]
        ledger.upsert_category("Groceries", "expense", True, 500)
        lines = {line["category"]: line for line in ledger.budget_status("2026-03", TODAY)["lines"]}
        assert lines["Groceries"]["spent"] == 60
        # Category filter finds it through its split; the uncategorized filter doesn't
        assert ledger.search_transactions(category="Household")["total"] == 1
        assert ledger.search_transactions(uncategorized=True)["total"] == 0

    def test_split_must_add_up_and_can_be_removed(self, temp_db):  # noqa: F811
        t = _add(date(2026, 3, 5), "COSTCO", -100, "Groceries")
        with pytest.raises(ValueError):
            ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 60},
                                        {"category": "Household", "amount": 30}])
        with pytest.raises(ValueError):
            ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 100}])
        ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 70}, {"category": "Household", "amount": 30}])
        with pytest.raises(ValueError):
            ledger.update_transaction(t["id"], amount=-120)
        t = ledger.set_splits(t["id"], [])
        assert t["category"] == "Groceries" and t["splits"] == []

    def test_one_category_replaces_split(self, temp_db):  # noqa: F811
        t = _add(date(2026, 3, 5), "COSTCO", -100)
        ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 70}, {"category": "Household", "amount": 30}])
        t = ledger.update_transaction(t["id"], category="Groceries")
        assert t["category"] == "Groceries" and not t["splits"]

    def test_split_export_has_a_row_per_part(self, temp_db):  # noqa: F811
        t = _add(date(2026, 3, 5), "COSTCO", -100, tags=["Trip 2026", "family"])
        ledger.set_splits(t["id"], [{"category": "Groceries", "amount": 70}, {"category": "Household", "amount": 30}])
        _add(date(2026, 3, 1), "PAYCHECK", 2000, "Income")
        lines = ledger.export_csv().strip().splitlines()
        assert lines[0].startswith("Date,Description,Amount,Category")
        assert len(lines) == 4 and "PAYCHECK" in lines[1]  # oldest first
        assert "trip-2026" in lines[2] and "Groceries" in lines[2] and "-70" in lines[2]


class TestTagsAndFilters:

    def test_tags_are_cleaned_and_filterable(self, temp_db):  # noqa: F811
        a = _add(date(2026, 3, 5), "HOTEL", -300, tags=["Vacation", "  Beach Trip "])
        _add(date(2026, 3, 6), "DINER", -25, tags="vacation")
        _add(date(2026, 3, 7), "GAS", -40)
        assert a["tags"] == ["vacation", "beach-trip"]
        assert {t["tag"]: t["count"] for t in ledger.list_tags()} == {"vacation": 2, "beach-trip": 1}
        assert ledger.search_transactions(tag="vacation")["total"] == 2
        assert ledger.search_transactions(tag="beach")["total"] == 0  # whole tags only
        ledger.update_transaction(a["id"], tags=[])
        assert ledger.search_transactions(tag="beach-trip")["total"] == 0

    def test_amount_and_direction_filters(self, temp_db):  # noqa: F811
        _add(date(2026, 3, 5), "BIG", -300)
        _add(date(2026, 3, 6), "SMALL", -20)
        _add(date(2026, 3, 7), "REFUND", 50)
        assert ledger.search_transactions(min_amount=40)["total"] == 2
        assert ledger.search_transactions(min_amount=40, direction="out")["total"] == 1
        assert ledger.search_transactions(max_amount=60, direction="in")["total"] == 1


class TestBudgets:

    def test_rollover_carries_unspent_and_overspent(self, temp_db):  # noqa: F811
        ledger.upsert_category("Dining", "expense", False, 200, rollover=True)
        _add(date(2026, 1, 10), "DINER", -150, "Dining")   # +50 left
        _add(date(2026, 2, 10), "STEAKHOUSE", -280, "Dining")  # -80 → carry -30
        _add(date(2026, 3, 3), "CAFE", -20, "Dining")
        line = next(x for x in ledger.budget_status("2026-03", TODAY)["lines"] if x["category"] == "Dining")
        assert line["rollover"] and line["carried"] == -30 and line["available"] == 170
        assert line["remaining"] == 150

    def test_suggested_budgets_average_recent_months(self, temp_db):  # noqa: F811
        for m, amt in ((12, 0), (1, 310), (2, 280)):
            if amt:
                _add(date(2026 if m < 12 else 2025, m, 15), "KROGER", -amt, "Groceries")
        _add(date(2025, 12, 1), "GAS", -40, "Gas & Transport")
        s = {x["category"]: x for x in ledger.suggest_budgets(3, TODAY)}
        assert s["Groceries"]["average"] == pytest.approx(196.67, abs=0.01)
        assert s["Groceries"]["suggested"] == 200


class TestAssets:

    def test_assets_count_in_net_worth_with_history(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Car Loan", accountType: "credit", '
            'balance: 9000, interestRate: 6, creditLimit: 20000, paymentDueDate: 10) { success } }')
        r = api('mutation { saveAsset(name: "Civic", kind: "vehicle", value: 15000, linkedBank: "B", '
                'linkedAccount: "Car Loan") { success message asset { id equity loanBalance } } }')['saveAsset']
        assert r['success'] and r['asset']['equity'] == 6000
        aid = r['asset']['id']
        api('mutation { saveAsset(name: "401k", kind: "retirement", value: 20000) { success } }')
        nw = api('{ netWorthBreakdown { cash totalAssets totalDebt netWorth assetsByKind { kind value } } }')
        nw = nw['netWorthBreakdown']
        assert nw['cash'] == 3000 and nw['totalAssets'] == 38000 and nw['netWorth'] == 38000 - nw['totalDebt']
        assert api.manager.get_total_assets() == 38000
        # Editing the value records history (one point per day)
        api('mutation($id: Int) { saveAsset(id: $id, name: "Civic", kind: "vehicle", value: 14000) { success } }',
            id=aid)
        assert [p['value'] for p in api('query($id: Int!) { assetHistory(id: $id) { value } }', id=aid)['assetHistory']] \
            == [14000]
        # A snapshot was recorded with the assets in it
        assert api('{ netWorthHistory { netWorth } }')['netWorthHistory'][0]['netWorth'] == 37000 - 9000

    def test_validation(self, temp_db):  # noqa: F811
        with pytest.raises(ValueError):
            assets.save_asset("", "vehicle", 10)
        with pytest.raises(ValueError):
            assets.save_asset("Boat", "yacht", 10)
        with pytest.raises(ValueError):
            assets.save_asset("Boat", "vehicle", -1)
        assets.save_asset("Boat", "vehicle", 10)
        with pytest.raises(ValueError):
            assets.save_asset("Boat", "other", 5)
        a = assets.save_asset("Ring", "valuables", 2000, today=date(2026, 1, 1))
        assets.save_asset("Ring", "valuables", 2500, asset_id=a["id"], today=date(2026, 2, 1))
        assert [p["value"] for p in assets.asset_history(a["id"])] == [2000, 2500]
        assets.delete_asset(a["id"])
        assert assets.asset_history(a["id"]) == []


class TestPlanAndHealth:

    def test_monthly_plan_left_to_budget(self, api):  # noqa: F811
        api('mutation { createIncomeSource(sourceName: "Job", amount: 1500, frequency: "biweekly", payDates: [1]) '
            '{ success } }')
        api('mutation { createBill(billName: "Rent", amount: 1200, dueDate: 5) { success } }')
        api('mutation { setCategoryBudget(name: "Groceries", monthlyBudget: 400) { success } }')
        p = api('{ monthlyPlan { income bills budgets goalSaving leftToBudget status } }')['monthlyPlan']
        assert p['income'] == 3250 and p['bills'] == 1200 and p['budgets'] == 400
        assert p['leftToBudget'] == 3250 - 1200 - 400 - p['goalSaving'] and p['status'] == 'unassigned'

    def test_health_check_scores_and_tips(self, api):  # noqa: F811
        api('mutation { createIncomeSource(sourceName: "Job", amount: 4000, frequency: "monthly", payDates: [1]) '
            '{ success } }')
        api('mutation { createBill(billName: "Rent", amount: 1500, dueDate: 5) { success } }')
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 4500, '
            'interestRate: 24, creditLimit: 5000, paymentDueDate: 12) { success } }')
        h = api('{ healthCheck { score grade topTips factors { key score status tip value } } }')['healthCheck']
        f = {x['key']: x for x in h['factors']}
        assert f['utilization']['value'] == '90%' and f['utilization']['status'] == 'poor' and f['utilization']['tip']
        assert f['high_interest']['status'] != 'good'
        assert f['emergency_fund']['status'] == 'poor'
        assert 0 <= h['score'] <= 100 and h['grade'] in 'ABCDF' and h['topTips']

    def test_health_check_with_nothing(self, api):  # noqa: F811
        api.manager.banks.clear()
        h = api('{ healthCheck { score grade factors { key } } }')['healthCheck']
        assert h['score'] is None and h['factors'] == []


class TestSubscriptions:

    def test_detects_monthly_charges_and_price_increase(self, temp_db):  # noqa: F811
        from models.finance_manager import FinanceManager
        from models.fixed_bill import Bill
        today = date.today()
        for i, amt in enumerate((15.49, 15.49, 15.49, 17.99)):
            _add(today - timedelta(days=30 * (3 - i) + 2), "NETFLIX.COM", -amt)
        for i in range(3):  # irregular payee isn't a subscription
            _add(today - timedelta(days=(5, 47, 60)[i]), "KROGER", -80)
        manager = FinanceManager([], [], [Bill("Gym", 40.0, 10)])
        s = planning.subscriptions(manager, today)
        by = {i["name"]: i for i in s["items"]}
        assert by["Netflix Com"]["frequency"] == "monthly" and by["Netflix Com"]["price_increase"] == 2.5
        assert by["Gym"]["source"] == "scheduled" and by["Gym"]["yearly_cost"] == 480
        assert "Kroger" not in by
        assert s["price_increases"] == ["Netflix Com"]
        assert s["monthly_total"] == pytest.approx(sum(i["monthly_cost"] for i in s["items"]), abs=0.01)


class TestYearReview:

    def test_totals_tops_and_months(self, temp_db):  # noqa: F811
        _add(date(2025, 1, 2), "PAYROLL", 3000, "Income")
        _add(date(2025, 2, 2), "PAYROLL", 3000, "Income")
        _add(date(2025, 1, 5), "KROGER", -200, "Groceries")
        _add(date(2025, 2, 5), "KROGER", -250, "Groceries")
        _add(date(2025, 2, 9), "BEST BUY", -900, "Shopping", tags=["gifts"])
        _add(date(2025, 2, 10), "TO SAVINGS", -1000, "Transfer")
        _add(date(2026, 1, 5), "KROGER", -999, "Groceries")  # other year
        r = planning.year_review(2025)
        assert (r["income"], r["spending"], r["saved"], r["savings_rate"]) == (6000, 1350, 4650, 77.5)
        assert r["biggest_month"] == "2025-02" and len(r["months"]) == 12
        assert r["top_categories"][0]["name"] == "Shopping"
        assert r["top_payees"][0] == {"name": "Best Buy", "amount": 900}
        assert r["by_tag"] == [{"tag": "gifts", "amount": 900}]
        assert r["largest_purchases"][0]["description"] == "TO SAVINGS"  # transfers listed, not counted
        assert planning.year_review(2020)["has_data"] is False
