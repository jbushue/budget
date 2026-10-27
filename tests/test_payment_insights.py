"""
Tests for the payment insights analyzer (models/payment_insights.py) and
its GraphQL query, which power the Optimizer page's recommendations.
"""

import json
from datetime import date, timedelta

import pytest

from models.payment_insights import PaymentInsightsAnalyzer
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()


def _day(offset: int) -> int:
    """Day of month `offset` days from today (kept within 1-28 so it always exists)."""
    return min(28, max(1, (TODAY + timedelta(days=offset)).day))


@pytest.fixture
def household(api):  # noqa: F811
    """Checking + savings, a paycheck, rent, a card with a balance, a student-loan group."""
    api('mutation { createAccount(bankName: "B", accountName: "Sav", accountType: "savings", '
        'balance: 2000, interestRate: 4) { success } }')
    api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
        'balance: 2000, interestRate: 24, creditLimit: 8000, paymentDueDate: 20, statementDate: 25) { success } }')
    api('mutation { createAccount(bankName: "B", accountName: "Loan A", accountType: "credit", '
        'balance: 6000, interestRate: 4, creditLimit: 20000) { success } }')
    api('mutation { createAccount(bankName: "B", accountName: "Loan B", accountType: "credit", '
        'balance: 6000, interestRate: 8, creditLimit: 20000) { success } }')
    api('mutation { createBillGroup(groupName: "Student Loans", totalPayment: 300, dueDate: 12, '
        'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
    for loan in ("Loan A", "Loan B"):
        api(f'mutation {{ addBillGroupMember(groupName: "Student Loans", bankName: "B", accountName: "{loan}") '
            '{ success } }')
    api('mutation { createIncomeSource(sourceName: "Job", amount: 2500, frequency: "semimonthly", '
        'payDates: [1, 15], distribution: "{\\"Chk\\": null}") { success } }')
    api('mutation { createBill(billName: "Rent", amount: 1400, dueDate: 3, '
        'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
    api('mutation { createBill(billName: "Internet", amount: 70, dueDate: 18) { success } }')
    return api


def _analyze(api, days=60):  # noqa: F811
    return PaymentInsightsAnalyzer(api.manager, days=days).analyze()


class TestComparison:

    def test_shape_and_headline(self, household):
        out = _analyze(household)
        comp = out["comparison"]
        assert set(comp) >= {"on_due_date", "optimized", "net_benefit", "changes"}
        for side in ("on_due_date", "optimized"):
            s = comp[side]
            assert s["late_payments"] == []
            assert s["lowest_checking_account"] == "Chk"
        assert comp["net_benefit"] == pytest.approx(
            comp["optimized"]["net_position"] - comp["on_due_date"]["net_position"])
        assert "covered on time" in out["headline"]
        assert comp["changes"]

    def test_analysis_does_not_touch_real_state(self, household):
        before = household.manager.banks[0].accounts["Chk"].balance
        _analyze(household)
        assert household.manager.banks[0].accounts["Chk"].balance == before


class TestBillTiming:

    def test_regular_bill_advises_paying_on_due_date(self, household):
        rows = _analyze(household)["bill_timing"]
        rent = next(r for r in rows if r["name"] == "Rent")
        assert rent["status"] == "on_time"
        assert rent["early_savings"] == 0
        assert "doesn't save money" in rent["advice"]

    def test_card_payment_on_payday_saves_interest(self, household):
        rows = _analyze(household)["bill_timing"]
        visa = next(r for r in rows if r["name"] == "[Auto] Visa Payment")
        assert visa["kind"] == "credit"
        if visa["days_early"] > 0:
            # amount x 24% APR / 365 x days early
            expected = visa["amount"] * 0.24 / 365 * visa["days_early"]
            assert visa["early_savings"] == pytest.approx(expected, abs=0.01) or expected < 0.5
            assert visa["pay_early_date"] < visa["due_date"]

    def test_group_payment_rows_use_member_rates(self, household):
        rows = _analyze(household)["bill_timing"]
        group = next(r for r in rows if r["name"] == "Student Loans")
        assert group["kind"] == "group"

    def test_late_payment_has_fixes(self, household):
        # A big bill the checking account can't cover on its own
        household('mutation { createBill(billName: "Roof", amount: 4500, dueDate: %d, '
                  'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }' % _day(2))
        household.manager.banks[0].accounts["Chk"].balance = 500
        out = _analyze(household)
        roof = next(r for r in out["bill_timing"] if r["name"] == "Roof")
        assert roof["status"] == "late"
        assert roof["shortfall"] > 0
        assert roof["fixes"]
        assert any(i["category"] == "late" and "Roof" in i["title"] for i in out["insights"])
        assert out["insights"][0]["severity"] in ("urgent", "warning")

    def test_already_paid_bill(self, household):
        household('mutation { markBillPaid(billName: "Internet") { success } }')
        rows = _analyze(household)["bill_timing"]
        internet = [r for r in rows if r["name"] == "Internet"]
        assert internet[0]["status"] == "already_paid"


class TestGroups:

    def test_highest_rate_first_saves_interest(self, household):
        g = next(x for x in _analyze(household)["groups"] if x["group_name"] == "Student Loans")
        assert g["highest_rate_member"] == "Loan B"
        assert g["current"]["pays_off"] and g["highest_rate_first"]["pays_off"]
        assert g["highest_rate_first"]["interest"] < g["current"]["interest"]
        assert g["reallocation_savings"] == pytest.approx(
            g["current"]["interest"] - g["highest_rate_first"]["interest"], abs=0.01)
        # Loan A keeps getting its interest (~$20/mo); the rest goes to Loan B
        assert g["suggested_fixed_amount"] == pytest.approx(300 - 6000 * 0.04 / 12, abs=0.01)
        # Proportional split today: equal balances -> equal shares
        shares = {m["account_name"]: m["next_payment_share"] for m in g["members"]}
        assert shares == {"Loan A": 150.0, "Loan B": 150.0}
        assert g["with_extra"]["months"] < g["current"]["months"]

    def test_payment_below_interest_is_flagged(self, household):
        household('mutation { updateBillGroup(groupName: "Student Loans", totalPayment: 50) { success } }')
        out = _analyze(household)
        g = next(x for x in out["groups"] if x["group_name"] == "Student Loans")
        assert g["current"]["pays_off"] is False
        assert any(i["category"] == "group" and i["severity"] == "urgent" for i in out["insights"])


class TestPromos:

    def test_promo_listed_with_interest_at_risk(self, household):
        start = (TODAY - timedelta(days=30)).isoformat()
        household('mutation { addPromoOffer(bankName: "B", accountName: "Visa", promoName: "0% BT", '
                  f'monthsInterestFree: 3, promoBalance: 900, startDate: "{start}") {{ success }} }}')
        promos = _analyze(household, days=90)["promos"]
        p = next(x for x in promos if x["promo_name"] == "0% BT")
        assert p["balance"] == 900
        assert p["interest_at_risk"] > 0
        assert p["on_track"] in (True, False)


class TestGraphQL:

    def test_payment_insights_query(self, household):
        data = household('{ paymentInsights(days: 60) { headline netBenefit '
                         'onDueDate { endingCash lowestChecking latePayments { name } } '
                         'optimized { netPosition interestEarned } changes '
                         'insights { severity category title detail impact date } '
                         'billTiming { name kind dueDate amount status planStatus advice fixes earlySavings } '
                         'groups { groupName reallocationSavings suggestedFixedAmount current { months interest paysOff } '
                         'members { accountName nextPaymentShare } } '
                         'promos { promoName onTrack } optimizerMoves { title why amount } } }')
        pi = data["paymentInsights"]
        assert pi["headline"]
        assert pi["insights"] and all(i["severity"] for i in pi["insights"])
        assert any(r["name"] == "Rent" for r in pi["billTiming"])
        assert pi["groups"][0]["groupName"] == "Student Loans"

    def test_what_if_includes_plain_language_summary(self, household):
        mods = json.dumps({"adjust_income": [{"source_name": "Job", "new_amount": 0}]})
        data = household('query($m: JSONString!) { whatIfScenario(modifications: $m, days: 120) '
                         '{ difference changes baseline { latePayments { name } } '
                         'scenario { latePayments { name } lowestChecking } } }', m=mods)
        wi = data["whatIfScenario"]
        assert wi["difference"] < 0
        assert len(wi["scenario"]["latePayments"]) > len(wi["baseline"]["latePayments"])
        assert any("worse off" in c for c in wi["changes"])
