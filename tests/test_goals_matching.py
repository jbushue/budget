"""Tests for goals/sinking funds, bill-payment matching, recurring charges, and late payments."""

from datetime import date, timedelta

import pytest

from models import bill_matching, goals, ledger
from models.dashboard import build_dashboard, overdue_bills
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()


def _recent_due() -> date:
    """A due date a few days ago that every month has (day <= 28)."""
    d = TODAY - timedelta(days=3)
    return d if d.day <= 28 else d.replace(day=28)


def _bill(api, name, amount, day, frequency="monthly", **extra):  # noqa: F811
    args = ", ".join(f'{k}: {v!r}'.replace("'", '"') for k, v in extra.items())
    data = api(f'mutation {{ createBill(billName: "{name}", amount: {amount}, dueDate: {day}, '
               f'frequency: "{frequency}"{", " + args if args else ""}) {{ success message }} }}')
    assert data["createBill"]["success"], data
    return next(b for b in api.manager.bills if b.bill_name == name)


class TestLatePayment:

    def test_paying_overdue_bill_keeps_next_occurrence(self, api):  # noqa: F811
        due = _recent_due()
        bill = _bill(api, "Water", 60, due.day)
        bill.created_on = due - timedelta(days=60)  # it existed before this due date
        assert [o["name"] for o in overdue_bills(api.manager, TODAY)] == ["Water"]

        api('mutation { markBillPaid(billName: "Water", moveMoney: false) { success } }')
        assert overdue_bills(api.manager, TODAY) == []
        # The payment was for the missed due date; next month's is still owed
        assert not bill.is_paid_this_period

    def test_paying_upcoming_bill_flags_it_paid(self, api):  # noqa: F811
        due = TODAY + timedelta(days=5)
        bill = _bill(api, "Phone", 80, min(due.day, 28))
        api('mutation { markBillPaid(billName: "Phone", moveMoney: false) { success } }')
        assert bill.is_paid_this_period


class TestGoals:

    def test_reserves_only_count_checking(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Save", accountType: "savings", balance: 500) '
            '{ success } }')
        goals.save_goal("Vacation", 1200, TODAY + timedelta(days=180), saved_amount=300)  # blank = checking
        goals.save_goal("Car", 5000, None, "B", "Save", saved_amount=500)
        goals.save_goal("Gift", 100, None, "B", "Chk", saved_amount=250)  # capped at target
        assert goals.reserved_in_checking(api.manager) == 400

        before = build_dashboard(api.manager)
        assert before["goal_reserves"] == 400

        listed = {g["name"]: g for g in goals.list_goals(api.manager)}
        v = listed["Vacation"]
        assert v["in_checking"] and not listed["Car"]["in_checking"]
        assert v["remaining"] == 900 and v["monthly_needed"] == pytest.approx(900 / (180 / 30.44), abs=0.01)
        assert listed["Gift"]["complete"]

    def test_contribute_and_validation(self, temp_db):  # noqa: F811
        g = goals.save_goal("Fund", 100)
        assert goals.contribute(g["id"], 40)["saved_amount"] == 40
        with pytest.raises(ValueError):
            goals.contribute(g["id"], -50)
        with pytest.raises(ValueError):
            goals.save_goal("Fund", 10)  # duplicate name
        with pytest.raises(ValueError):
            goals.save_goal("Zero", 0)

    def test_sinking_fund_suggest_create_and_roll(self, api):  # noqa: F811
        due = TODAY + timedelta(days=60)
        _bill(api, "Car Insurance", 600, due.day, "semi_annual", dueMonth=due.month)
        _bill(api, "Rent", 1000, 1)
        sugg = goals.sinking_fund_suggestions(api.manager)
        assert [s["bill_name"] for s in sugg] == ["Car Insurance"]
        assert sugg[0]["monthly"] == pytest.approx(600 / (60 / 30.44), abs=1)

        goals.create_sinking_fund(api.manager, "Car Insurance", saved_amount=600)
        assert goals.sinking_fund_suggestions(api.manager) == []
        fund = goals.list_goals(api.manager)[0]
        assert fund["linked_bill"] == "Car Insurance" and fund["target_date"] == due.isoformat()

        # Paying the bill uses up the fund and points it at the next due date
        bill = next(b for b in api.manager.bills if b.bill_name == "Car Insurance")
        api.manager.record_bill_paid(bill, 600, due - timedelta(days=2))
        fund = goals.list_goals(api.manager, today=due + timedelta(days=1))[0]
        assert fund["saved_amount"] == 0
        assert date.fromisoformat(fund["target_date"]) > due + timedelta(days=150)


class TestBillMatching:

    def test_auto_match_named_payment(self, api):  # noqa: F811
        due = _recent_due()
        bill = _bill(api, "Netflix", 15.49, due.day)
        ledger.add_transaction(due - timedelta(days=1), "NETFLIX.COM 866-579", -15.49, "B", "Chk")
        ledger.add_transaction(due, "KROGER #4", -15.49, "B", "Chk")  # same amount, wrong payee
        assert bill_matching.auto_match(api.manager) == 1
        assert bill.payment_history[-1]["amount_paid"] == 15.49
        assert api.manager.banks[0].accounts["Chk"].balance == 3000  # no money moved
        # Due date has passed, so the upcoming occurrence still counts as owed
        assert not bill.is_paid_this_period
        matched = [t for t in ledger.all_transactions() if t["matched_bill"]]
        assert [t["description"] for t in matched] == ["NETFLIX.COM 866-579"]
        assert bill_matching.find_matches(api.manager) == []  # already paid for that due date

    def test_medium_suggestions_confirm_ignore_unmatch(self, api):  # noqa: F811
        due = _recent_due()
        bill = _bill(api, "Gym", 42.00, due.day)
        t = ledger.add_transaction(due, "ANYTIME HEALTH CLUB 4411", -42.00, "B", "Chk")
        s = bill_matching.suggestions(api.manager)
        assert [(m["bill_name"], m["confidence"]) for m in s] == [("Gym", "medium")]
        assert bill_matching.auto_match(api.manager) == 0  # medium is never automatic

        bill_matching.ignore_match(t["id"])
        assert bill_matching.suggestions(api.manager) == []
        ledger.update_transaction(t["id"], matched_bill=None)

        bill_matching.confirm_match(api.manager, t["id"], "Gym")
        assert len(bill.payment_history) == 1
        # The same payee is now learned: a later charge is high confidence
        assert bill_matching._learned_payees()["Gym"] == {ledger.normalize_payee("ANYTIME HEALTH CLUB 4411")}

        bill_matching.unmatch(api.manager, t["id"])
        assert bill.payment_history == [] and not bill.is_paid_this_period
        assert ledger.all_transactions()[0]["matched_bill"] is None

    def test_card_payment_matches_by_name(self, api):  # noqa: F811
        api('mutation { createBank(name: "Chase") { success } }')
        api('mutation { createAccount(bankName: "Chase", accountName: "Sapphire", accountType: "credit", '
            f'balance: 800, creditLimit: 5000, paymentDueDate: {_recent_due().day}) {{ success }} }}')
        ledger.add_transaction(_recent_due(), "CHASE CREDIT CRD AUTOPAY", -250, "B", "Chk")
        m = bill_matching.find_matches(api.manager)
        assert [(x["bill_name"], x["confidence"]) for x in m] == [("[Auto] Sapphire Payment", "high")]

    def test_matching_respects_setting(self, api):  # noqa: F811
        api('mutation { updateSettings(changes: "{\\"auto_match_bills\\": false}") { success } }')
        due = _recent_due()
        _bill(api, "Netflix", 15.49, due.day)
        ledger.add_transaction(due, "NETFLIX.COM", -15.49)
        assert bill_matching.auto_match(api.manager) == 0
        assert [m["confidence"] for m in bill_matching.suggestions(api.manager)] == ["high"]


class TestRecurring:

    def _monthly(self, desc, amount, n=4):
        for i in range(n):
            ledger.add_transaction(TODAY - timedelta(days=30 * i + 2), desc, -amount)

    def test_detects_monthly_and_dismiss(self, api):  # noqa: F811
        self._monthly("SPOTIFY USA 877-778", 11.99)
        self._monthly("RANDOM STORE", 5, n=2)  # too few
        for i, gap in enumerate([3, 17, 40]):
            ledger.add_transaction(TODAY - timedelta(days=gap), "IRREGULAR CAFE", -9)
        r = bill_matching.detect_recurring(api.manager)
        assert [(x["name"], x["frequency"], x["amount"]) for x in r] == [("Spotify Usa", "monthly", 11.99)]
        assert r[0]["next_expected"] > TODAY.isoformat()
        bill_matching.dismiss_recurring(r[0]["key"])
        assert bill_matching.detect_recurring(api.manager) == []

    def test_existing_bill_is_not_suggested(self, api):  # noqa: F811
        self._monthly("SPOTIFY USA", 11.99)
        _bill(api, "Spotify", 11.99, 5)
        assert bill_matching.detect_recurring(api.manager) == []


class TestGoalsApi:

    def test_goal_crud_and_queries(self, api):  # noqa: F811
        r = api('mutation { saveSavingsGoal(name: "Trip", targetAmount: 1000, targetDate: "2099-01-01") '
                '{ success message } }')["saveSavingsGoal"]
        assert r["success"], r
        g = api('{ savingsGoals { id name inChecking remaining } }')["savingsGoals"][0]
        assert g["inChecking"] and g["remaining"] == 1000
        api('mutation($id: Int!) { contributeToGoal(id: $id, amount: 250) { success } }', id=g["id"])
        d = api('{ dashboardSummary { goalReserves } savingsGoals { savedAmount } }')
        assert d["dashboardSummary"]["goalReserves"] == 250 and d["savingsGoals"][0]["savedAmount"] == 250
        api('{ sinkingFundSuggestions { billName } billMatchSuggestions { billName } recurringCharges { name } }')
        assert api('mutation($id: Int!) { deleteSavingsGoal(id: $id) { success } }', id=g["id"])

    def test_csv_import_auto_matches_bills(self, api):  # noqa: F811
        due = _recent_due()
        _bill(api, "Netflix", 15.49, due.day)
        csv_text = f"Date,Description,Amount\n{due:%m/%d/%Y},NETFLIX.COM,-15.49\n"
        r = api('mutation($c: String!) { importCsvTransactions(content: $c, bankName: "B", accountName: "Chk") '
                '{ result { success imported matchedBills } } }', c=csv_text)["importCsvTransactions"]["result"]
        assert r == {"success": True, "imported": 1, "matchedBills": 1}
        page = api('{ ledgerTransactions { items { matchedBill } } }')["ledgerTransactions"]["items"]
        assert page == [{"matchedBill": "Netflix"}]
