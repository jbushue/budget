"""Every page reads the same year-long plan, so they agree about every day."""

from datetime import date, timedelta

import pytest

from models import optimizer_plus, plan, tools
from models.bank import Bank
from models.dashboard import build_dashboard
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from models.income_source import IncomeSource, IncomeFrequency
from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from tests.test_tools import ok, run

TODAY = date.today()


def manager(checking=2500.0, card=1800.0):
    bank = Bank("B")
    bank.add_account("checking", "Checking", checking)
    bank.add_account("savings", "Savings", 500.0, 4.0)
    c = bank.add_credit_account("Visa", 6000.0, 24.0, payment_due_date=18, statement_date=24)
    c.balance = c.regular_balance = card
    m = FinanceManager([bank], [IncomeSource("Job", 2400.0, IncomeFrequency.BIWEEKLY,
                                             start_date=TODAY - timedelta(days=4),
                                             distribution={"Checking": "remainder"})],
                       [Bill("Rent", 1300.0, 3), Bill("Power", 140.0, 21)])
    m.cushion = 150.0
    m._ensure_linked_bills()
    return m


def test_short_and_long_views_agree_on_shared_days():
    m = manager()
    short = m.project_balances(end_date=TODAY + timedelta(days=30))
    long = m.project_balances(end_date=TODAY + timedelta(days=200))
    by_day = {s["date"]: s["balances"] for s in long["snapshots"]}
    assert len(short["snapshots"]) == 31
    for s in short["snapshots"]:
        assert s["balances"] == by_day[s["date"]]


def test_plan_is_computed_once_and_redone_when_data_changes(monkeypatch):
    m = manager()
    calls = []
    from models import payment_optimizer
    orig = payment_optimizer.PaymentOptimizer.run_optimized_simulation

    def counting(self, *a, **k):
        calls.append(1)
        return orig(self, *a, **k)
    monkeypatch.setattr(payment_optimizer.PaymentOptimizer, "run_optimized_simulation", counting)
    build_dashboard(m)
    m.project_balances(end_date=TODAY + timedelta(days=60))
    m.payment_insights(days=45)
    optimizer_plus.purchase_planner(m, 100)
    assert len(calls) == 1
    m.banks[0].accounts["Checking"].balance += 10
    m.project_balances(end_date=TODAY + timedelta(days=60))
    assert len(calls) == 2


def test_purchase_planner_today_is_safe_to_spend():
    m = manager()
    d = build_dashboard(m)
    p = optimizer_plus.purchase_planner(m, 0, days=30)
    assert p["today"] == pytest.approx(d["safe_to_spend"], abs=0.01)
    assert d["plan_series"][0]["date"] == TODAY.isoformat()


def test_compare_goals_matches_the_optimizer_page():
    m = manager()
    rows = {r["goal"]: r for r in tools.compare_strategies(m, 90)}
    opt = m.payment_insights(days=90)["comparison"]["optimized"]
    mine = rows[m.plan_goal()[0]]
    assert mine["final_cash"] == opt["ending_cash"] and mine["interest_paid"] == opt["interest_charged"]


def test_what_if_with_no_change_is_the_plan():
    m = manager()
    r = m.run_what_if_scenario({}, days=60)
    assert r["difference"] == 0
    assert r["baseline_summary"] == r["scenario_summary"]
    opt = m.payment_insights(days=60)["comparison"]["optimized"]
    assert r["baseline_summary"]["ending_cash"] == opt["ending_cash"]


def test_optimizer_keeps_your_cushion_not_a_hidden_300():
    m = manager(checking=900.0, card=3000.0)
    m.cushion = 50.0
    runs = plan.plan_runs(m)
    assert runs.optimized  # ran with the user's cushion
    assert plan.floor(m) == 50.0


def test_lowest_checking_is_all_checking_together():
    from models.payment_insights import summarize_simulation
    m = manager()
    m.banks[0].add_account("checking", "Joint", 400.0)
    s = summarize_simulation(m.project_balances(end_date=TODAY + timedelta(days=40)), m.banks)
    assert s["lowest_checking_account"] is None  # two checking accounts: it's their total
    series = plan.checking_series(m.project_balances(end_date=TODAY + timedelta(days=40)),
                                  plan.checking_keys(m.banks))
    assert s["lowest_checking"] == pytest.approx(min(v for _, v in series), abs=0.01)


def test_timeline_totals_add_up_and_net_worth_has_assets(client):  # noqa: F811
    ok(client, 'mutation { createBank(name: "B") { success message } }')
    ok(client, 'mutation { createAccount(bankName: "B", accountName: "Checking", accountType: "checking", '
               'balance: 3000) { success message } }')
    ok(client, 'mutation { createBill(billName: "Rent", amount: 1200, dueDate: 5) { success message } }')
    ok(client, 'mutation { saveAsset(name: "Car", kind: "vehicle", value: 9000) { success message } }')
    p = run(client, "{ projection(days: 60) { totalIncome totalExpenses netChange netFinalBalance "
                    "totalFinalBalance otherAssets lowestChecking planGoal } }")["projection"]
    assert p["totalIncome"] - p["totalExpenses"] == pytest.approx(p["netChange"], abs=0.01)
    assert p["netFinalBalance"] == pytest.approx(p["totalFinalBalance"] + p["otherAssets"], abs=0.01)
    assert p["planGoal"] == "maximize_discretionary"


def test_background_plan_matches_and_is_reused(monkeypatch):
    """warm() works the plan out in the background; the next page uses it."""
    m = manager()
    expected = plan.plan_runs(manager()).optimized["final_balances"]
    thread = plan.warm(m)
    assert thread is not None
    assert plan.warm(m) is None  # already being worked out
    thread.join(timeout=60)
    from models import payment_optimizer
    monkeypatch.setattr(payment_optimizer.PaymentOptimizer, "run_optimized_simulation",
                        lambda *a, **k: pytest.fail("the plan was worked out again"))
    assert plan.plan_runs(m).optimized["final_balances"] == expected
    assert plan.warm(m) is None  # cached


def test_page_waits_for_a_background_plan_instead_of_redoing_it(monkeypatch):
    import threading
    m = manager()
    from models import payment_optimizer
    orig = payment_optimizer.PaymentOptimizer.run_optimized_simulation
    release, calls = threading.Event(), []

    def slow(self, *a, **k):
        calls.append(1)
        release.wait(timeout=30)
        return orig(self, *a, **k)
    monkeypatch.setattr(payment_optimizer.PaymentOptimizer, "run_optimized_simulation", slow)
    thread = plan.warm(m)
    threading.Timer(0.2, release.set).start()
    runs = plan.plan_runs(m)  # waits for the background run
    thread.join(timeout=60)
    assert len(calls) == 1 and runs is plan.plan_runs(m)
