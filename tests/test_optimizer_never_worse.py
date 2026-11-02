"""
The optimizer must never leave you worse off than paying every bill on its
due date: every move is verified against the full simulation. Also covers
the moves the verified search adds and average-daily-balance interest.
"""

import random
from datetime import date, timedelta

import pytest

from models.bank import Bank
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from models.income_source import IncomeFrequency, IncomeSource
from models.payment_insights import PaymentInsightsAnalyzer, outcome_value
from models.payment_optimizer import PaymentOptimizer, score_simulation
from models.timeline_simulator import TimelineEvent, TimelineSimulator

START = date(2026, 3, 1)


def household(rng: random.Random) -> FinanceManager:
    """A random household: checking, maybe savings, cards (some with promos), a mortgage, a HELOC."""
    bank = Bank("B")
    bank.add_account("checking", "Chk", rng.choice([300, 800, 1500, 3000, 6000, 12000]))
    if rng.random() < 0.8:
        bank.add_account("savings", "Sav", rng.choice([500, 2000, 8000]), rng.choice([0.5, 2, 4.5]),
                         interest_accrual_date=rng.choice([None, 1, 28]))
    for i in range(rng.randint(0, 3)):
        limit = rng.choice([3000, 8000, 15000])
        card = bank.add_credit_account(f"Card{i}", limit, rng.choice([0, 18, 24, 29.9]),
                                       payment_due_date=rng.randint(1, 28), statement_date=rng.randint(1, 28))
        card.balance = card.regular_balance = float(rng.randint(0, int(limit * 0.7)))
        if rng.random() < 0.4:
            card.add_promotional_offer(f"P{i}", 12, start_date=START - timedelta(days=rng.randint(60, 340)))
            card.promo_balance[f"P{i}"] = owed = float(rng.randint(300, 2500))
            card.balance += owed
    if rng.random() < 0.4:
        bank.add_mortgage_account("Home", 300000, rng.choice([3, 6.5]), 360, rng.choice([150000, 250000]),
                                  payment_due_date=rng.randint(1, 28))
    if rng.random() < 0.4:
        bank.add_heloc_account("HE", 50000, rng.choice([7, 9.5]), 120, 240, START - timedelta(days=200),
                               rng.choice([0, 5000, 20000]), rng.randint(1, 28))
    freq = rng.choice(["semimonthly", "biweekly", "monthly"])
    amount = {"semimonthly": 2500, "biweekly": 2300, "monthly": 5000}[freq] * rng.choice([0.6, 1, 1.5])
    income = IncomeSource("Job", amount, IncomeFrequency[freq.upper()],
                          pay_date=[1, 15] if freq == "semimonthly" else [rng.randint(1, 28)],
                          distribution={"Chk": None}, start_date=START + timedelta(days=rng.randint(0, 13)))
    bills = [Bill(f"Bill{i}", rng.choice([60, 150, 400, 1200, 1800]), rng.randint(1, 28))
             for i in range(rng.randint(2, 6))]
    m = FinanceManager([bank], [income], bills)
    m.apply_settings({"everyday_weekly": rng.choice([0, 150, 400]), "cushion": rng.choice([0, 300]),
                      "card_late_fee": 30, "default_late_fee": 25, "overdraft_fee": 35})
    return m


class TestNeverWorse:

    @pytest.mark.parametrize("seed", range(30))
    def test_random_household(self, seed):
        rng = random.Random(seed)
        m = household(rng)
        days = rng.choice([30, 90])
        out = PaymentInsightsAnalyzer(m, start_date=START, days=days).analyze()
        base, opt = out["comparison"]["on_due_date"], out["comparison"]["optimized"]
        assert outcome_value(opt) >= outcome_value(base) - 0.01
        assert out["comparison"]["net_benefit"] >= -0.01
        assert len(opt["late_payments"]) <= len(base["late_payments"])
        assert opt["fees"] <= base["fees"] + 0.01
        if base["lowest_checking"] >= 0:
            assert opt["lowest_checking"] >= 0

    def test_plan_matches_insights(self):
        """The optimizer's own score is the insights' bottom line."""
        m = household(random.Random(7))
        a = PaymentInsightsAnalyzer(m, start_date=START, days=60)
        out = a.analyze()
        assert score_simulation(a.optimized) == pytest.approx(out["comparison"]["optimized"]["outcome"], abs=0.02)


def _simple(checking=3000.0, card_balance=0.0, card_rate=24.0, savings=None, bills=None, heloc=None):
    bank = Bank("B")
    bank.add_account("checking", "Chk", checking)
    if savings is not None:
        bank.add_account("savings", "Sav", savings, 4.0, interest_accrual_date=28)
    if card_balance:
        card = bank.add_credit_account("Visa", 10000, card_rate, payment_due_date=20, statement_date=25)
        card.balance = card.regular_balance = card_balance
    if heloc is not None:
        bank.add_heloc_account("HE", 30000, 9.0, 120, 240, START - timedelta(days=100), heloc, 10)
    income = [IncomeSource("Job", 3000, IncomeFrequency.SEMIMONTHLY, pay_date=[1, 15], distribution={"Chk": None})]
    return FinanceManager([bank], income, bills or [Bill("Rent", 1500, 3)])


class TestMoves:

    def test_spare_cash_pays_down_costly_card(self):
        m = _simple(checking=9000, card_balance=4000)
        a = PaymentInsightsAnalyzer(m, start_date=START, days=90)
        out = a.analyze()
        paydowns = [cf for cf in a.optimized["cash_flow"] if cf["type"] == "EXTRA_CREDIT_PAYMENT"]
        assert paydowns and all(cf["to_account"] == "Visa" for cf in paydowns)
        comp = out["comparison"]
        assert comp["optimized"]["interest_charged"] < comp["on_due_date"]["interest_charged"]
        assert comp["net_benefit"] > 0
        assert comp["optimized"]["lowest_checking"] >= 300 - 0.01  # the default cushion
        assert any(mv["type"] == "EXTRA_CREDIT_PAYMENT" for mv in out["optimizer_moves"])

    def test_cushion_is_respected(self):
        m = _simple(checking=9000, card_balance=4000)
        m.apply_settings({"cushion": 2500})
        out = PaymentInsightsAnalyzer(m, start_date=START, days=90).analyze()
        assert out["comparison"]["optimized"]["lowest_checking"] >= 2500 - 0.01

    def test_nothing_to_gain_means_due_dates(self):
        """With no interest anywhere the plan is simply paying on due dates."""
        m = _simple(checking=2000)
        out = PaymentInsightsAnalyzer(m, start_date=START, days=60).analyze()
        assert out["comparison"]["net_benefit"] == 0
        assert out["optimizer_moves"] == []

    def test_missed_bill_covered_by_heloc_draw(self):
        """Checking can't cover a bill; drawing on the HELOC beats a late payment and a fee."""
        m = _simple(checking=200, heloc=5000, bills=[Bill("Roof", 2500, 2)])
        m.apply_settings({"default_late_fee": 40})
        a = PaymentInsightsAnalyzer(m, start_date=START, days=30)
        out = a.analyze()
        base, opt = out["comparison"]["on_due_date"], out["comparison"]["optimized"]
        assert [p["name"] for p in base["late_payments"]] == ["Roof"]
        assert base["unpaid_bills"] == 2500
        assert opt["late_payments"] == [] and opt["unpaid_bills"] == 0
        assert any(cf["type"] == "HELOC_RECALL" for cf in a.optimized["cash_flow"])
        assert out["comparison"]["net_benefit"] > 0

    def test_unpaid_bill_counts_as_owed(self):
        """Skipping a bill must not look like saving money."""
        bank = Bank("B")
        bank.add_account("checking", "Chk", 100)
        r = TimelineSimulator([bank], [], [Bill("Rent", 1000, 5)]).project_balances(START, START + timedelta(days=10))
        assert score_simulation(r) == pytest.approx(100 - 1000)

    def _promo_card(self, due_day):
        bank = Bank("B")
        bank.add_account("checking", "Chk", 8000)
        card = bank.add_credit_account("Card", 10000, 24.0, payment_due_date=due_day, statement_date=28)
        card.add_promotional_offer("0%", 6, start_date=date(2026, 3, 31) - timedelta(days=180))  # ends Mar 31
        card.promo_balance["0%"] = 3000.0
        card.balance = 3000.0
        return FinanceManager([bank], [IncomeSource("Job", 5000, pay_date=[1], distribution={"Chk": None})],
                              [Bill("Rent", 1000, 1)])

    def test_imminent_promo_counts(self):
        """A promo expiring after the window but before the card's next payment counts its deferred interest."""
        a = PaymentInsightsAnalyzer(self._promo_card(due_day=5), start_date=date(2026, 3, 6), days=20)
        out = a.analyze()
        assert out["comparison"]["on_due_date"]["imminent_promo_interest"] > 0
        assert out["comparison"]["optimized"]["imminent_promo_interest"] == 0
        assert any(cf["type"] == "PROMO_PAYOFF" for cf in a.optimized["cash_flow"])

    def test_promo_with_a_payment_still_to_come_is_not_imminent(self):
        out = PaymentInsightsAnalyzer(self._promo_card(due_day=25), start_date=date(2026, 3, 1), days=20).analyze()
        base = out["comparison"]["on_due_date"]
        # The Mar 25 payment (after this 20-day view, before the Mar 31 expiry)
        # clears it, so nothing is at risk
        assert base["imminent_promo_interest"] == 0 and base["pending_deferred_interest"] == 0
        assert out["promos"][0]["on_track"] is True

    def test_deferred_interest_is_charged_the_day_a_promo_ends(self):
        from models.timeline_simulator import TimelineSimulator
        m = self._promo_card(due_day=5)
        m.income_sources, m.bills = [], []
        m.banks[0].accounts["Chk"].balance = 0.0
        r = TimelineSimulator(m.banks, [], []).project_balances(date(2026, 3, 20), date(2026, 4, 3))
        promo = [cf for cf in r["cash_flow"] if cf.get("promo")]
        assert [cf["date"] for cf in promo] == [date(2026, 3, 31)] and promo[0]["amount"] > 300


class TestAverageDailyBalance:

    def test_last_minute_sweep_earns_a_day_not_a_month(self):
        bank = Bank("B")
        bank.add_account("checking", "Chk", 6000)
        bank.add_account("savings", "Sav", 0.0, 12.0, interest_accrual_date=10)
        sweep = TimelineEvent(event_date=date(2026, 3, 9), event_type="SAVINGS_SWEEP", amount=6000,
                              description="Sweep", from_bank="B", from_account="Chk", to_bank="B", to_account="Sav")
        r = TimelineSimulator([bank], [], []).project_balances(
            date(2026, 3, 1), date(2026, 3, 10), injected_events={sweep.event_date: [sweep]})
        earned = sum(cf["amount"] for cf in r["cash_flow"] if cf["type"] == "INTEREST")
        # One day of a 28-day cycle (Feb 10 → Mar 10) at 1% a month on $6,000
        assert earned == pytest.approx(6000 * 0.01 / 28, rel=0.01)

    def test_constant_balance_is_unchanged(self):
        bank = Bank("B")
        bank.add_account("savings", "Sav", 1200.0, 12.0)  # no interest day: end of month
        r = TimelineSimulator([bank], [], []).project_balances(date(2026, 3, 1), date(2026, 3, 31))
        earned = [cf["amount"] for cf in r["cash_flow"] if cf["type"] == "INTEREST"]
        assert earned == [pytest.approx(12.0)]

    def test_card_paid_mid_cycle_is_charged_for_the_days_it_was_owed(self):
        bank = Bank("B")
        bank.add_account("checking", "Chk", 5000)
        card = bank.add_credit_account("Visa", 10000, 24.0, payment_due_date=20, statement_date=31)
        card.balance = card.regular_balance = 3000.0
        pay = TimelineEvent(event_date=date(2026, 3, 16), event_type="EXTRA_CREDIT_PAYMENT", amount=3000,
                            description="Pay", from_bank="B", from_account="Chk", to_bank="B", to_account="Visa")
        r = TimelineSimulator([bank], [], []).project_balances(
            date(2026, 3, 1), date(2026, 3, 31), injected_events={pay.event_date: [pay]})
        charged = sum(cf["amount"] for cf in r["cash_flow"] if cf["type"] == "INTEREST")
        assert 0 < charged < 3000 * 0.02  # about half a month, not zero and not a full month


class TestPayoffGoal:

    def test_target_card_kept(self):
        bank = Bank("B")
        bank.add_account("checking", "Chk", 6000)
        card = bank.add_credit_account("Visa", 10000, 20.0, payment_due_date=12, statement_date=5)
        card.balance = card.regular_balance = 2500.0
        income = [IncomeSource("Job", 4000, pay_date=[1], distribution={"Chk": None})]
        m = FinanceManager([bank], income, [Bill("Rent", 1200, 3)])
        opt = PaymentOptimizer(m.banks, m.income_sources, m.bills)
        result, plan = opt.run_optimized_simulation(START, START + timedelta(days=90),
                                                    optimization_goal="payoff_credit_account",
                                                    target_credit_account="Visa")
        assert plan.extra_credit_payments
        assert result["credit_final_balances"]["B:Visa"] < 2500
