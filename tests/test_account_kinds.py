"""More kinds of bank account: EBT, HSA, CDs, investments, ... and how the
planner treats each (bills, refills, weekly spending, growth)."""

import json
from datetime import date, timedelta

import pytest

from models.bank import Bank
from models.bank_account import BankAccount
from models.fixed_bill import Bill
from models.timeline_simulator import TimelineSimulator
from models.types import ACCOUNT_KINDS, AccountType, BillFrequency, pays_bills
from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from tests.test_tools import ok, run


def _sim(bank, bills=(), spending=None):
    return TimelineSimulator([bank], [], list(bills), daily_spending=spending)


class TestKinds:
    def test_every_kind_is_an_account_type(self):
        for value in ACCOUNT_KINDS:
            assert AccountType(value).value == value
            BankAccount(value, f"A {value}", 10.0)

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            BankAccount("piggybank", "Oink", 1.0)

    def test_restricted_kinds_never_pay_bills(self):
        for value in ("ebt", "hsa", "fsa", "cd", "investment", "retirement", "cash", "other"):
            assert not pays_bills(BankAccount(value, "x"))
        for value in ("checking", "savings", "money_market", "prepaid", "wallet"):
            assert pays_bills(BankAccount(value, "x"))

    def test_bill_is_not_paid_from_ebt(self):
        bank = Bank("B")
        bank.add_account("ebt", "Food", 900.0)
        bank.add_account("checking", "Checking", 50.0)
        today = date.today()
        bill = Bill("Rent", 400.0, (today + timedelta(days=2)).day, BillFrequency.MONTHLY)
        result = _sim(bank, [bill]).project_balances(today, today + timedelta(days=5))
        assert bank.accounts["Food"].balance == 900.0
        assert any(cf["type"] == "BILL_DEFERRED" for cf in result["cash_flow"])


class TestRefillAndSpending:
    def test_monthly_refill_lands(self):
        bank = Bank("B")
        today = date.today()
        day = (today + timedelta(days=3)).day
        bank.add_account("ebt", "Food", 0.0, refill_amount=300.0, refill_day=day)
        bank.add_account("checking", "Checking", 100.0)
        result = _sim(bank).project_balances(today, today + timedelta(days=5))
        refills = [cf for cf in result["cash_flow"] if cf["type"] == "ACCOUNT_REFILL"]
        assert len(refills) == 1 and refills[0]["amount"] == 300.0
        assert bank.accounts["Food"].balance == 300.0
        assert bank.accounts["Checking"].balance == 100.0

    def test_ebt_covers_everyday_spending_until_it_runs_out(self):
        bank = Bank("B")
        bank.add_account("ebt", "Food", 30.0, weekly_spending=70.0, offsets_everyday=True)
        bank.add_account("checking", "Checking", 1000.0)
        today = date.today()
        spending = {"amount": 20.0}
        result = _sim(bank, spending=spending).project_balances(today, today + timedelta(days=4))
        # Days 1-3: $10 from EBT + $10 from checking; days 4-5: $20 from checking
        assert bank.accounts["Food"].balance == pytest.approx(0.0)
        assert bank.accounts["Checking"].balance == pytest.approx(1000 - 30 - 40)
        assert sum(1 for cf in result["cash_flow"] if cf["type"] == "ACCOUNT_SPENDING") == 3

    def test_spending_without_offset_leaves_checking_alone(self):
        bank = Bank("B")
        bank.add_account("hsa", "HSA", 100.0, weekly_spending=7.0)
        bank.add_account("checking", "Checking", 1000.0)
        today = date.today()
        _sim(bank, spending={"amount": 5.0}).project_balances(today, today + timedelta(days=1))
        assert bank.accounts["HSA"].balance == pytest.approx(98.0)
        assert bank.accounts["Checking"].balance == pytest.approx(990.0)

    def test_investments_grow_checking_does_not(self):
        inv = BankAccount("retirement", "401k", 12000.0, interest_rate=6.0)
        chk = BankAccount("checking", "Checking", 12000.0, interest_rate=6.0)
        assert inv.accrue_interest() == pytest.approx(60.0)
        assert chk.accrue_interest() == 0.0

    def test_bad_refill_day(self):
        with pytest.raises(ValueError):
            BankAccount("ebt", "Food", 0.0, refill_amount=10, refill_day=40)


@pytest.fixture
def setup(client):  # noqa: F811
    ok(client, 'mutation { createBank(name: "State") { success message } }')
    ok(client, 'mutation { createAccount(bankName: "State", accountName: "Checking", accountType: "checking", '
               'balance: 2000) { success message } }')
    refill = (date.today() + timedelta(days=20)).day
    ok(client, 'mutation { createAccount(bankName: "State", accountName: "SNAP", accountType: "ebt", '
               f'balance: 120, refillAmount: 291, refillDay: {refill}, weeklySpending: 60, offsetsEveryday: true) '
               '{ success message account { kindLabel kindGroup paysBills } } }')
    return client


class TestApi:
    def test_create_and_read(self, setup):
        data = run(setup, '{ allBanks { bankAccounts { accountName accountType kindLabel kindGroup paysBills '
                          'refillAmount refillDay weeklySpending offsetsEveryday } } }')
        snap = next(a for a in data["allBanks"][0]["bankAccounts"] if a["accountName"] == "SNAP")
        assert snap == {"accountName": "SNAP", "accountType": "ebt", "kindLabel": "EBT / SNAP",
                        "kindGroup": "benefits", "paysBills": False, "refillAmount": 291.0,
                        "refillDay": (date.today() + timedelta(days=20)).day,
                        "weeklySpending": 60.0, "offsetsEveryday": True}

    def test_survives_reload(self, setup):
        from models.finance_manager import FinanceManager
        m = FinanceManager([], [], [])
        m.load_from_database()
        acc = m.banks[0].accounts["SNAP"]
        assert acc.account_type == AccountType.EBT and acc.refill_amount == 291.0 and acc.offsets_everyday

    def test_edit_kind_and_settings(self, setup):
        ok(setup, 'mutation { updateAccount(bankName: "State", accountName: "Checking", accountType: "checking", '
                  'newAccountType: "wallet") { success message } }')
        ok(setup, 'mutation { updateAccount(bankName: "State", accountName: "SNAP", accountType: "ebt", '
                  'refillDay: 0, weeklySpending: 0, offsetsEveryday: false) { success message } }')
        data = run(setup, '{ allBanks { bankAccounts { accountName accountType refillDay weeklySpending '
                          'offsetsEveryday } } }')
        rows = {a["accountName"]: a for a in data["allBanks"][0]["bankAccounts"]}
        assert rows["Checking"]["accountType"] == "wallet"
        assert rows["SNAP"]["refillDay"] is None and rows["SNAP"]["weeklySpending"] == 0
        assert rows["SNAP"]["offsetsEveryday"] is False

    def test_edit_rejects_unknown_kind(self, setup):
        r = run(setup, 'mutation { updateAccount(bankName: "State", accountName: "SNAP", accountType: "ebt", '
                       'newAccountType: "piggy") { success message } }')
        assert not r["updateAccount"]["success"]

    def test_account_kinds_query(self, setup):
        kinds = json.loads(run(setup, "{ accountKinds }")["accountKinds"])
        assert {k["value"] for k in kinds} >= {"checking", "ebt", "hsa", "retirement"}
        assert "mortgage" not in {k["value"] for k in kinds}

    def test_dashboard_other_money(self, setup):
        data = run(setup, "{ dashboardSummary { otherMoney checkingNow } }")["dashboardSummary"]
        other = json.loads(data["otherMoney"])
        assert data["checkingNow"] == 2000
        snap = other[0]
        assert snap["account"] == "SNAP" and snap["purpose"] == "Groceries" and snap["next_refill"]
        # $120 at $60/week lasts two weeks; the refill is ~20 days away
        assert snap["runs_out"] and snap["runs_out"] < snap["next_refill"]
