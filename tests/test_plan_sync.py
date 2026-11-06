"""One plan for the whole app, promos paid off on time, and a Safe to spend
that leaves money for bills after the next paycheck."""

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from models.bank import Bank
from models.credit_card_account import PromoOffer
from models.dashboard import build_dashboard
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from models.income_source import IncomeSource, IncomeFrequency
from models.timeline_simulator import TimelineSimulator
from models.types import BillFrequency
from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from tests.test_tools import ok, run

TODAY = date.today()


def card_with_promo(regular=2000.0, promo=1200.0, ends_in=150, due_day=20):
    bank = Bank("B")
    bank.add_account("checking", "Checking", 3000.0)
    card = bank.add_credit_account("Visa", 10000.0, 25.0, payment_due_date=due_day, statement_date=25)
    card.balance, card.regular_balance = regular + promo, regular
    p = PromoOffer("Couch", 12, start_date=TODAY - timedelta(days=30), end_date=TODAY + timedelta(days=ends_in))
    card.active_promos.append(p)
    card.promo_balance["Couch"] = promo
    return bank, card, p


def manager_for(bank, income=3000.0, bills=()):
    m = FinanceManager([bank], [IncomeSource("Job", income, IncomeFrequency.MONTHLY, pay_date=[1],
                                             distribution={"Checking": "remainder"})], list(bills))
    m._ensure_linked_bills()
    return m


class TestPromos:
    def test_installments_split_over_payments_left(self):
        _, card, p = card_with_promo(ends_in=150)
        n = card.payments_left_before(p.end_date, TODAY)
        assert 4 <= n <= 6
        assert card.promo_installments(TODAY)["Couch"] == round(1200 / n, 2)

    def test_regular_minimum_first_then_promo(self):
        _, card, _ = card_with_promo()
        regular_min = card.regular_minimum(TODAY)
        applied = card.pay_with_promo_plan(regular_min + 300, transaction_date=TODAY)
        assert applied == {"Couch": 300}
        assert card.promo_balance["Couch"] == pytest.approx(900)
        assert card.regular_balance == pytest.approx(2000 - regular_min)
        assert card.balance == pytest.approx(3200 - regular_min - 300)

    def test_promos_paid_soonest_expiring_first_then_regular(self):
        _, card, _ = card_with_promo(promo=300)
        later = PromoOffer("TV", 18, start_date=TODAY, end_date=TODAY + timedelta(days=400))
        card.active_promos.insert(0, later)  # listed first, but expires later
        card.promo_balance = {"TV": 500.0, "Couch": 300.0}
        card.balance = 2800.0
        regular_min = card.regular_minimum(TODAY)
        applied = card.make_payment(regular_min + 600, transaction_date=TODAY)
        assert applied == {"Couch": 300, "TV": 300}  # Couch paid off before TV gets anything
        assert card.promo_balance == {"TV": 200, "Couch": 0}
        card.make_payment(regular_min + 900, transaction_date=TODAY)
        assert card.promo_balance["TV"] == 0
        assert card.regular_balance == pytest.approx(2000 - 2 * regular_min - 700)

    def test_regular_last(self):
        _, card, _ = card_with_promo(promo=300)
        card.payment_order = "regular_last"
        assert card.make_payment(250, transaction_date=TODAY) == {"Couch": 250}
        assert card.regular_balance == 2000
        card.make_payment(150, transaction_date=TODAY)
        assert card.promo_balance["Couch"] == 0 and card.regular_balance == 1900

    def test_targeted_promo_payment_still_goes_to_that_promo(self):
        _, card, _ = card_with_promo()
        card.make_payment(400, transaction_date=TODAY, promo_name="Couch")
        assert card.promo_balance["Couch"] == 800 and card.regular_balance == 2000

    def test_promo_paid_off_before_it_expires_even_with_a_regular_balance(self):
        bank, card, p = card_with_promo(ends_in=150)
        m = manager_for(bank)
        state = deepcopy((m.banks, m.income_sources, m.bills, m.bill_groups))
        r = TimelineSimulator(*state, **m.sim_options()).project_balances(TODAY, p.end_date + timedelta(days=3))
        before = [s for s in r["snapshots"] if s["date"] < p.end_date][-1]
        assert before["promo_balances"]["B:Visa:Couch"] == pytest.approx(0.0, abs=0.01)
        # no deferred interest got charged, and the regular balance is still being paid normally
        assert not any(cf.get("type") == "INTEREST" and cf["amount"] > 200 for cf in r["cash_flow"])

    def test_insights_report_promo_on_track(self):
        bank, _, _ = card_with_promo(ends_in=60)
        m = manager_for(bank)
        promos = m.payment_insights(days=90)["promos"]
        assert promos and promos[0]["on_track"] is True and promos[0]["left_at_end"] == pytest.approx(0, abs=0.01)

    def test_promo_that_cant_be_paid_is_flagged(self):
        bank, _, _ = card_with_promo(regular=0, promo=3000, ends_in=40)
        bank.accounts["Checking"].balance = 50.0
        m = FinanceManager([bank], [], [])
        m._ensure_linked_bills()
        promos = m.payment_insights(days=60)["promos"]
        assert promos[0]["on_track"] is False and promos[0]["shortfall"] > 0


class TestOnePlan:
    def test_plan_goal_from_settings(self):
        bank, _, _ = card_with_promo()
        m = manager_for(bank)
        m.apply_settings({"optimizer_goal": "minimize_interest"})
        assert m.plan_goal() == ("minimize_interest", None)
        m.apply_settings({"optimizer_goal": "payoff_credit_account", "optimizer_target": "Visa"})
        assert m.plan_goal() == ("payoff_credit_account", "Visa")
        m.apply_settings({"optimizer_goal": "payoff_credit_account", "optimizer_target": "Gone"})
        assert m.plan_goal() == ("maximize_discretionary", None)

    def test_api_setting_drives_dashboard_and_insights(self, client):  # noqa: F811
        ok(client, 'mutation { createBank(name: "B") { success message } }')
        ok(client, 'mutation { createAccount(bankName: "B", accountName: "Checking", accountType: "checking", '
                   'balance: 4000) { success message } }')
        ok(client, 'mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
                   'balance: 2000, interestRate: 24.0, creditLimit: 5000, paymentDueDate: 15) { success message } }')
        ok(client, 'mutation { updateSettings(changes: "{\\"optimizer_goal\\": \\"payoff_credit_account\\", '
                   '\\"optimizer_target\\": \\"Visa\\"}") { success message } }')
        d = run(client, "{ dashboardSummary { planGoal planTarget lookaheadDays } }")["dashboardSummary"]
        assert d == {"planGoal": "payoff_credit_account", "planTarget": "Visa", "lookaheadDays": 90}

    def test_bad_goal_rejected(self, client):  # noqa: F811
        r = run(client, 'mutation { updateSettings(changes: "{\\"optimizer_goal\\": \\"yolo\\"}") { success message } }')
        assert not r["updateSettings"]["success"]


class TestSafeToSpend:
    def test_keeps_money_for_a_bill_after_the_next_paycheck(self):
        bank = Bank("B")
        bank.add_account("checking", "Checking", 3000.0)
        due = TODAY + timedelta(days=50)
        insurance = Bill("Insurance", 4000.0, min(due.day, 28), frequency=BillFrequency.YEARLY, due_month=due.month)
        pay_day = (TODAY + timedelta(days=3)).day
        m = FinanceManager([bank], [IncomeSource("Job", 1000.0, IncomeFrequency.MONTHLY, pay_date=[min(pay_day, 28)],
                                                 distribution={"Checking": "remainder"})], [insurance])
        m.cushion = 100.0
        d = build_dashboard(m, TODAY)
        assert d["held_for_later"] > 1500
        assert any(h["name"] == "Insurance" for h in d["held_for"])
        # Without looking ahead it would have said ~$2,900+
        assert d["safe_to_spend"] < 1500
        assert d["safe_to_spend"] == pytest.approx(max(0, d["lowest_balance"] - 100), abs=0.02)

    def test_late_bills_anywhere_ahead_are_held_back(self):
        bank = Bank("B")
        bank.add_account("checking", "Checking", 500.0)
        due = TODAY + timedelta(days=60)
        m = FinanceManager([bank], [], [Bill("Big", 5000.0, min(due.day, 28), frequency=BillFrequency.YEARLY,
                                             due_month=due.month)])
        d = build_dashboard(m, TODAY)
        assert d["short_total"] == 5000.0 and d["safe_to_spend"] == 0.0
        assert d["status"] == "danger"


def test_off_track_promo_raises_an_alert(temp_db):  # noqa: F811
    from models.alerts import build_alerts
    bank, _, _ = card_with_promo(regular=0, promo=3000, ends_in=40)
    bank.accounts["Checking"].balance = 50.0
    m = FinanceManager([bank], [], [])
    m._ensure_linked_bills()
    alerts = build_alerts(m)
    promo = [a for a in alerts if a["key"].startswith("promo:")]
    assert promo and promo[0]["severity"] == "danger" and "Couch" in promo[0]["title"]


class TestPaymentOrderSetting:

    def test_saved_through_the_api_and_used(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 1500, '
            'interestRate: 20, creditLimit: 5000, paymentDueDate: 12) { success } }')
        api('mutation { addPromoOffer(bankName: "B", accountName: "Visa", promoName: "0%", monthsInterestFree: 12, '
            'promoBalance: 500) { success } }')
        out = api('mutation { updateAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
                  'paymentOrder: "regular_last") { success message } }')["updateAccount"]
        assert out["success"], out
        bad = api('mutation { updateAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
                  'paymentOrder: "sideways") { success message } }')["updateAccount"]
        assert not bad["success"]
        m = FinanceManager([], [], [])
        assert m.load_from_database()
        card = m.banks[0].credit_accounts["Visa"]
        assert card.payment_order == "regular_last"
        assert api('{ allBanks { creditAccounts { paymentOrder } } }')["allBanks"][0]["creditAccounts"][0] == \
            {"paymentOrder": "regular_last"}
        card.make_payment(200)
        assert card.promo_balance["0%"] == 300 and card.regular_balance == 1000
