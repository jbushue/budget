"""Debt boost, due-date moves, the purchase planner, and the HTML digest email."""

import json
import time
from datetime import date

import pytest

from models import optimizer_plus
from models.bank import Bank
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from models.income_source import IncomeSource, IncomeFrequency
from models.types import BillFrequency
from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from tests.test_tools import ok, run


def make_manager(checking=1500.0, card=3000.0, car_day=14):
    bank = Bank("Bank")
    bank.add_account("checking", "Checking", checking)
    bank.add_account("savings", "Savings", 200.0, 4.0)
    bank.add_credit_account("Visa", 8000.0, 24.0, payment_due_date=20, statement_date=25)
    bank.credit_accounts["Visa"].balance = card
    bank.credit_accounts["Visa"].regular_balance = card
    income = [IncomeSource("Job", 2600.0, IncomeFrequency.MONTHLY, pay_date=[15], distribution={"Checking": "remainder"})]
    bills = [Bill("Rent", 1300.0, 1, BillFrequency.MONTHLY), Bill("Car", 450.0, car_day, BillFrequency.MONTHLY)]
    m = FinanceManager([bank], income, bills)
    m._ensure_linked_bills()
    m.cushion = 100.0
    return m


class TestDebtBoost:
    def test_finds_a_safe_amount_that_saves_money(self):
        m = make_manager()
        t = time.time()
        r = optimizer_plus.debt_boost(m, days=120)
        assert time.time() - t < 30
        assert r["available"] and r["safe_monthly"] > 0
        assert r["plan"]["late"] <= r["base"]["late"]
        assert r["plan"]["lowest"] >= r["floor"] - 0.01
        assert r["plan"]["debt"] < r["base"]["debt"]
        assert r["saved"] > 0
        assert r["debts"][0]["account"] == "Visa" and r["debts"][0]["extra_paid"] > 0
        # Nothing was changed for real
        assert m.banks[0].credit_accounts["Visa"].balance == 3000.0

    def test_too_much_is_flagged_unsafe(self):
        m = make_manager()
        r = optimizer_plus.debt_boost(m, days=90, monthly=5000)
        assert r["monthly_is_safe"] is False

    def test_no_debt(self):
        m = make_manager(card=0.0)
        r = optimizer_plus.debt_boost(m, days=60)
        assert not r["available"] and r["reason"] == "No debt to pay down"

    def test_bad_strategy(self):
        with pytest.raises(ValueError):
            optimizer_plus.debt_boost(make_manager(), strategy="yolo")


class TestDueDateMoves:
    def test_bill_due_before_payday_is_moved_after_it(self):
        # $1,500 checking with rent on the 1st and pay mid-month: rent lands at
        # the low point, so moving it just after payday raises the lowest balance
        m = make_manager(checking=1500.0, car_day=14)
        r = optimizer_plus.due_date_moves(m, days=75)
        assert r["suggestions"], r
        top = r["suggestions"][0]
        near_payday = {min(28, d + k) for d in r["payday_days"] for k in (0, 1, 2)}
        assert top["suggested_day"] in near_payday
        assert top["lowest_after"] > top["lowest_before"] or top["fixes_late"] > 0
        assert m.bills[0].due_date == 1  # nothing changed for real

    def test_linked_bills_are_not_moved(self):
        r = optimizer_plus.due_date_moves(make_manager(), days=60)
        assert all(not s["bill"].startswith("[Auto]") for s in r["suggestions"])


class TestPurchasePlanner:
    def test_series_and_earliest_day(self):
        m = make_manager(checking=900.0)
        r = optimizer_plus.purchase_planner(m, 400.0, days=60)
        assert len(r["can_spend"]) == 61
        assert all(c["amount"] >= 0 for c in r["can_spend"])
        if r["earliest"]:
            assert r["lowest_after"] >= r["cushion"] - 0.01
            day = next(c for c in r["can_spend"] if c["date"] == r["earliest"])
            assert day["amount"] >= 400

    def test_unaffordable(self):
        r = optimizer_plus.purchase_planner(make_manager(checking=100.0), 1_000_000.0, days=30)
        assert r["earliest"] is None

    def test_negative(self):
        with pytest.raises(ValueError):
            optimizer_plus.purchase_planner(make_manager(), -5)


@pytest.fixture
def setup(client):  # noqa: F811
    ok(client, 'mutation { createBank(name: "Bank") { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Bank", accountName: "Checking", accountType: "checking", '
               'balance: 2500) { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Bank", accountName: "Visa", accountType: "credit", '
               'balance: 2000, interestRate: 22.0, creditLimit: 5000, paymentDueDate: 18) { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Bank", accountName: "SNAP", accountType: "ebt", '
               'balance: 150, refillAmount: 291, refillDay: 3, weeklySpending: 50) { success message } }')
    ok(client, 'mutation { createBill(billName: "Rent", amount: 1200, dueDate: 1) { success message } }')
    return client


class TestApi:
    def test_queries(self, setup):
        data = run(setup, '{ debtBoost(days: 60) dueDateMoves(days: 45) purchasePlanner(amount: 100, days: 30) }')
        boost = json.loads(data["debtBoost"])
        assert boost["available"] and boost["debts"][0]["account"] == "Visa"
        assert "suggestions" in json.loads(data["dueDateMoves"])
        assert len(json.loads(data["purchasePlanner"])["can_spend"]) == 31

    def test_bad_strategy_is_an_error(self, setup):
        r = setup.post("/graphql", json={"query": '{ debtBoost(strategy: "yolo") }'}).get_json()
        assert r.get("errors")


class TestDigest:
    def test_html_digest(self, setup):
        html = run(setup, "{ digestHtml }")["digestHtml"]
        assert html.startswith("<!DOCTYPE html>")
        assert "Safe to spend" in html and "Benefits &amp; other money" in html and "SNAP" in html
        assert "Rent" in html and "<script" not in html

    def test_text_digest_mentions_benefits(self, setup):
        text = run(setup, "{ digestPreview }")["digestPreview"]
        assert "Benefits:" in text and "SNAP" in text

    def test_email_has_both_parts(self, setup, monkeypatch):
        from models import alerts, app_settings
        sent = []

        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def starttls(self, **k): pass
            def login(self, *a): pass
            def send_message(self, msg): sent.append(msg)
            def quit(self): pass

        monkeypatch.setattr(alerts.smtplib, "SMTP", FakeSMTP)
        app_settings.update_settings({"smtp_host": "smtp.example.com", "email_to": "me@example.com"})
        from models.finance_manager import FinanceManager
        m = FinanceManager([], [], [])
        m.load_from_database()
        alerts.send_digest(m, force=True)
        msg = sent[0]
        types = [part.get_content_type() for part in msg.iter_parts()]
        assert types == ["text/plain", "text/html"]
