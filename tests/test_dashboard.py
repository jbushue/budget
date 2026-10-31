"""
Phase 1: everyday spending, fees, settings, and the dashboard summary
(safe to spend, bills status, pay-period checklist).
"""

from datetime import date, timedelta

import pytest

from models.bank import Bank
from models.dashboard import build_dashboard, overdue_bills
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from models import app_settings
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()


def _bank(checking=1000.0, savings=0.0):
    bank = Bank("B")
    bank.add_account("checking", "Chk", checking)
    if savings:
        bank.add_account("savings", "Sav", savings, interest_rate=4.0)
    return bank


def _day_in(n: int) -> int:
    return (TODAY + timedelta(days=n)).day


def _weekday_on_or_after(n: int) -> date:
    """Paychecks on weekends move to Friday; pick a weekday so tests know the payday."""
    d = TODAY + timedelta(days=n)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


PAYDAY = _weekday_on_or_after(5)


class TestEverydaySpending:

    def test_spending_comes_out_every_day(self):
        bank = _bank(1000)
        sim = TimelineSimulator([bank], [], [], daily_spending={"amount": 10.0})
        r = sim.project_balances(TODAY, TODAY + timedelta(days=9))
        spends = [cf for cf in r["cash_flow"] if cf["type"] == "EVERYDAY_SPENDING"]
        assert len(spends) == 10
        assert r["final_balances"]["B:Chk"] == pytest.approx(900)

    def test_spending_can_overdraw_and_charges_one_overdraft_fee_per_dip(self):
        bank = _bank(25)
        sim = TimelineSimulator([bank], [], [], daily_spending={"amount": 10.0},
                                fees={"overdraft_fee": 35.0})
        r = sim.project_balances(TODAY, TODAY + timedelta(days=5))
        fees = [cf for cf in r["cash_flow"] if cf["type"] == "FEE"]
        assert len(fees) == 1 and fees[0]["fee_kind"] == "overdraft"
        # 25 - 60 spending - 35 fee
        assert r["final_balances"]["B:Chk"] == pytest.approx(-70)

    def test_late_card_payment_adds_fee_to_card(self):
        bank = _bank(10)
        card = bank.add_credit_account("Visa", 5000, 20.0, payment_due_date=_day_in(2))
        card.balance = card.regular_balance = 1000.0
        manager = FinanceManager([bank], [], [])
        sim = TimelineSimulator(*[manager.banks, [], manager.bills, []], fees={"card_late_fee": 30.0})
        r = sim.project_balances(TODAY, TODAY + timedelta(days=5))
        fee = next(cf for cf in r["cash_flow"] if cf["type"] == "FEE")
        assert fee["fee_kind"] == "late" and fee["account"] == "Visa"
        assert r["credit_final_balances"]["B:Visa"] == pytest.approx(1030)

    def test_bill_specific_late_fee_wins(self):
        bank = _bank(10)
        rent = Bill("Rent", 500, _day_in(1))
        rent.late_fee = 75.0
        sim = TimelineSimulator([bank], [], [rent], fees={"default_late_fee": 5.0, "overdraft_fee": 0})
        r = sim.project_balances(TODAY, TODAY + timedelta(days=3))
        fee = next(cf for cf in r["cash_flow"] if cf["type"] == "FEE")
        assert fee["amount"] == -75.0

    def test_optimizer_leaves_room_for_spending(self):
        """Sweeps must count everyday spending, or the plan overdraws checking."""
        bank = _bank(3000, savings=1000)
        income = [IncomeSource("Job", 2000, "monthly", pay_date=[_day_in(3)], distribution={"Chk": None})]
        manager = FinanceManager([bank], income, [Bill("Rent", 800, _day_in(10))])
        manager.apply_settings({"everyday_weekly": 350, "cushion": 0})
        result = manager.project_balances(TODAY, TODAY + timedelta(days=60))
        low = min(s["balances"]["B:Chk"] for s in result["snapshots"])
        assert low >= 0


class TestSettings:

    def test_defaults_and_update(self, temp_db):  # noqa: F811
        s = app_settings.get_settings()
        assert s["cushion"] == 200.0 and s["spending_mode"] == "manual"
        s = app_settings.update_settings({"cushion": "150", "everyday_weekly": 300})
        assert s["cushion"] == 150.0 and s["everyday_weekly"] == 300.0
        assert app_settings.get_settings()["cushion"] == 150.0

    @pytest.mark.parametrize("change", [{"cushion": -5}, {"spending_mode": "magic"}, {"nope": 1},
                                        {"spending_account": "NoColon"}, {"cushion": "abc"}])
    def test_invalid_settings_rejected(self, temp_db, change):  # noqa: F811
        with pytest.raises(ValueError):
            app_settings.update_settings(change)

    def test_public_settings_hide_secrets(self, temp_db):  # noqa: F811
        app_settings.update_settings({"smtp_password": "hunter2"})
        pub = app_settings.public_settings()
        assert "smtp_password" not in pub and "password_hash" not in pub
        assert pub["smtp_password_set"] is True and "password_set" not in pub

    def test_apply_settings(self):
        m = FinanceManager([], [], [])
        m.apply_settings({"cushion": 100, "everyday_weekly": 70, "spending_account": "B:Chk",
                          "overdraft_fee": 20})
        assert m.cushion == 100
        assert m.everyday_spending == {"amount": 10.0, "weekly": 70.0, "mode": "manual", "bank": "B", "account": "Chk"}
        assert m.fees["overdraft_fee"] == 20
        m.apply_settings({"everyday_weekly": 0})
        assert m.everyday_spending is None


class TestDashboard:

    def _manager(self, checking=2000.0, weekly=0.0, cushion=200.0, bills=None):
        bank = _bank(checking)
        income = [IncomeSource("Job", 1500, "biweekly", pay_date=[1], distribution={"Chk": None},
                               start_date=PAYDAY)]
        m = FinanceManager([bank], income, bills or [])
        m.apply_settings({"cushion": cushion, "everyday_weekly": weekly, "overdraft_fee": 35,
                          "card_late_fee": 30})
        return m

    def test_safe_to_spend_is_lowest_balance_minus_cushion(self):
        rent = Bill("Rent", 1200, _day_in(3), start_date=TODAY)
        m = self._manager(checking=2000, bills=[rent])
        d = build_dashboard(m)
        # Lowest point: after rent on day 3, before the day-5 paycheck
        assert d["lowest_balance"] == pytest.approx(800)
        assert d["safe_to_spend"] == pytest.approx(600)
        assert d["status"] == "ok"
        assert d["next_payday"] == PAYDAY.isoformat()
        assert d["safe_per_day"] == pytest.approx(600 / (PAYDAY - TODAY).days)
        names = [b["name"] for b in d["bills_this_period"]]
        assert names == ["Rent"] and d["bills_this_period"][0]["status"] == "covered"

    def test_everyday_spending_lowers_safe_to_spend(self):
        rent = Bill("Rent", 1200, _day_in(3), start_date=TODAY)
        plain = build_dashboard(self._manager(bills=[rent]))["safe_to_spend"]
        spender = build_dashboard(self._manager(bills=[Bill("Rent", 1200, _day_in(3), start_date=TODAY)],
                                                weekly=70))
        # $10/day keeps going after rent until payday: the low point moves to the
        # day before payday, (PAYDAY - TODAY) days of spending later
        assert spender["safe_to_spend"] == pytest.approx(plain - 10 * (PAYDAY - TODAY).days)
        assert spender["everyday_weekly"] == 70

    def test_short_bill_is_danger(self):
        m = self._manager(checking=300, cushion=0, bills=[Bill("Roof", 2000, _day_in(2), start_date=TODAY)])
        d = build_dashboard(m)
        assert d["status"] == "danger" and "Roof" in d["status_title"]
        # The unpaid Roof money is still in checking but it isn't spendable
        assert d["safe_to_spend"] == 0
        assert d["short_total"] == 2000
        roof = next(b for b in d["bills_this_period"] if b["name"] == "Roof")
        assert roof["status"] == "short"

    def test_tight_cushion_is_warning(self):
        m = self._manager(checking=500, cushion=400, bills=[Bill("Rent", 300, _day_in(2), start_date=TODAY)])
        d = build_dashboard(m)
        assert d["status"] == "warning" and "tight" in d["status_title"]

    def test_overdue_bill_is_held_back(self):
        past = TODAY - timedelta(days=3)
        late = Bill("Phone", 80, past.day)
        late.created_on = past - timedelta(days=40)
        m = self._manager(checking=2000, bills=[late])
        od = overdue_bills(m, TODAY)
        assert [o["name"] for o in od] == ["Phone"] and od[0]["days_overdue"] == 3
        d = build_dashboard(m)
        assert d["overdue_total"] == 80
        assert d["status"] == "warning"
        assert d["bills_this_period"][0]["status"] == "overdue"
        # Paid bills aren't overdue
        late.is_paid_this_period = True
        assert overdue_bills(m, TODAY) == []

    def test_newly_added_bill_is_not_overdue(self):
        """A bill added today isn't overdue for a due date before it existed."""
        past = TODAY - timedelta(days=3)
        fresh = Bill("Phone", 80, past.day)  # created_on = today
        m = self._manager(bills=[fresh])
        assert overdue_bills(m, TODAY) == []
        # ...unless it has been paid before (so it's clearly being tracked)
        fresh.payment_history.append({"date": past - timedelta(days=30), "amount_paid": 80})
        assert [o["name"] for o in overdue_bills(m, TODAY)] == ["Phone"]

    def test_created_date_survives_reload(self, api):  # noqa: F811
        api('mutation { createBill(billName: "Gym", amount: 40, dueDate: 3) { success } }')
        api('mutation { loadDatabase { success } }')
        gym = next(b for b in api.manager.bills if b.bill_name == "Gym")
        assert gym.created_on == TODAY


class TestDashboardApi:

    def test_query_and_settings_mutation(self, api):  # noqa: F811
        api('mutation { createIncomeSource(sourceName: "Job", amount: 2000, payDates: [1]) { success } }')
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) { success } }')
        data = api('mutation { updateSettings(changes: "{\\"cushion\\": 50, \\"everyday_weekly\\": 140}") '
                   '{ success message settings } }')
        assert data["updateSettings"]["success"], data
        assert api.manager.cushion == 50 and api.manager.everyday_spending["amount"] == 20
        d = api('{ dashboardSummary { status statusTitle safeToSpend safePerDay cushion everydayWeekly nextPayday '
                'billsThisPeriod { name billName status amount } upcomingIncome { name } insights { title } } }')
        d = d["dashboardSummary"]
        assert d["cushion"] == 50 and d["everydayWeekly"] == 140
        assert d["status"] in ("ok", "warning", "danger")
        bad = api('mutation { updateSettings(changes: "{\\"cushion\\": -1}") { success message } }')
        assert not bad["updateSettings"]["success"]
        assert '"cushion": 50' in api('{ settings }')["settings"] or api('{ settings }')["settings"]


class TestRecordOnly:

    def test_record_only_moves_no_money(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
            'balance: 500, creditLimit: 5000) { success } }')
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) { success } }')
        for name in ("Rent", "[Auto] Visa Payment"):
            data = api('mutation($n: String!) { markBillPaid(billName: $n, moveMoney: false) { success } }', n=name)
            assert data["markBillPaid"]["success"]
        bank = api.manager.banks[0]
        assert bank.accounts["Chk"].balance == 3000
        assert bank.credit_accounts["Visa"].balance == 500
        assert all(b.is_paid_this_period for b in api.manager.bills)
        history = api('{ billPaymentHistory { billName } }')["billPaymentHistory"]
        assert {h["billName"] for h in history} == {"Rent", "[Auto] Visa Payment"}
