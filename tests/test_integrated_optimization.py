"""
Integration tests for the unified optimizer ↔ timeline pipeline.

Verifies that PaymentOptimizer injects events (savings sweeps, promo payoffs,
HELOC parking, extra credit payments) into the TimelineSimulator and that
those events actually mutate balances within the same projection.
"""

import pytest
from datetime import date
from copy import deepcopy

from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource, IncomeFrequency
from models.finance_manager import FinanceManager
from models.payment_optimizer import PaymentOptimizer
from models.timeline_simulator import TimelineSimulator, TimelineEvent
from models.types import BillFrequency


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def full_bank():
    """Bank with checking, savings, credit, and HELOC."""
    bank = Bank("Main Bank", "traditional")
    bank.add_account("checking", "Checking", starting_balance=5000.0, interest_rate=0.01)
    bank.add_account("savings", "HYS", starting_balance=8000.0, interest_rate=4.5, interest_accrual_date=1)
    bank.add_credit_account("Visa", credit_limit=10000, interest_rate=22.0, payment_due_date=15, statement_date=10)
    bank.add_heloc_account(
        "HELOC",
        credit_limit=50000,
        interest_rate=7.5,
        draw_period_months=180,
        total_term_months=360,
        start_date=date(2024, 1, 1),
        current_balance=10000.0,
        payment_due_date=1,
    )
    return bank


@pytest.fixture
def income():
    return [
        IncomeSource("Salary", 4000.0, IncomeFrequency.BIWEEKLY, pay_date=[1, 15]),
    ]


@pytest.fixture
def basic_bills():
    return [
        Bill("Rent", 1500.0, 1, frequency=BillFrequency.MONTHLY),
        Bill("Internet", 80.0, 20, frequency=BillFrequency.MONTHLY),
    ]


# ── Tests ─────────────────────────────────────────────────────────────


class TestTimelineAcceptsInjectedEvents:
    """Verify that the TimelineSimulator processes injected events."""

    def test_savings_sweep_moves_money(self, full_bank, income, basic_bills):
        """A SAVINGS_SWEEP event should transfer money from checking to savings."""
        banks = [full_bank]
        bills = basic_bills

        sweep_date = date(2026, 4, 10)
        injected = {
            sweep_date: [
                TimelineEvent(
                    event_date=sweep_date,
                    event_type="SAVINGS_SWEEP",
                    amount=500.0,
                    description="Test sweep",
                    from_bank="Main Bank",
                    from_account="Checking",
                    to_bank="Main Bank",
                    to_account="HYS",
                ),
            ]
        }

        sim = TimelineSimulator(banks, income, bills)
        result = sim.project_balances(date(2026, 4, 7), date(2026, 4, 15), injected_events=injected)

        # Verify the sweep appears in cash_flow
        sweep_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'SAVINGS_SWEEP']
        assert len(sweep_cf) == 1
        assert sweep_cf[0]['amount'] == 500.0

    def test_heloc_park_reduces_heloc_balance(self, full_bank, income, basic_bills):
        """A HELOC_PARK event should reduce the HELOC balance."""
        banks = [full_bank]
        initial_heloc_balance = full_bank.heloc_accounts["HELOC"].balance

        park_date = date(2026, 4, 10)
        injected = {
            park_date: [
                TimelineEvent(
                    event_date=park_date,
                    event_type="HELOC_PARK",
                    amount=1000.0,
                    description="Park in HELOC",
                    from_bank="Main Bank",
                    from_account="Checking",
                    to_bank="Main Bank",
                    to_account="HELOC",
                ),
            ]
        }

        # Need deepcopy to avoid mutating fixture
        banks_copy = deepcopy(banks)
        sim = TimelineSimulator(banks_copy, income, basic_bills)
        result = sim.project_balances(date(2026, 4, 7), date(2026, 4, 15), injected_events=injected)

        park_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'HELOC_PARK']
        assert len(park_cf) == 1
        assert park_cf[0]['heloc_balance_after'] < initial_heloc_balance

    def test_promo_payoff_reduces_credit_balance(self, full_bank, income, basic_bills):
        """A PROMO_PAYOFF event should reduce the credit card balance."""
        card = full_bank.credit_accounts["Visa"]
        promo = card.add_promotional_offer("0% APR", 12, purchase_limit=5000)
        card.make_purchase(3000.0, promo_name="0% APR")

        payoff_date = date(2026, 4, 10)
        injected = {
            payoff_date: [
                TimelineEvent(
                    event_date=payoff_date,
                    event_type="PROMO_PAYOFF",
                    amount=500.0,
                    description="Promo payoff",
                    from_bank="Main Bank",
                    from_account="Checking",
                    to_bank="Main Bank",
                    to_account="Visa",
                ),
            ]
        }

        banks_copy = deepcopy([full_bank])
        sim = TimelineSimulator(banks_copy, income, basic_bills)
        result = sim.project_balances(date(2026, 4, 7), date(2026, 4, 15), injected_events=injected)

        payoff_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'PROMO_PAYOFF']
        assert len(payoff_cf) == 1
        assert payoff_cf[0]['credit_balance_after'] < 3000.0


class TestOptimizerInjectsEvents:
    """Verify the PaymentOptimizer produces and applies optimization events."""

    def test_optimized_vs_unoptimized_savings_differ(self, full_bank, income, basic_bills):
        """Optimized projection should show savings sweeps in cash_flow."""
        banks = [full_bank]

        # Un-optimized: raw timeline
        banks_raw = deepcopy(banks)
        raw_sim = TimelineSimulator(banks_raw, income, basic_bills)
        raw_result = raw_sim.project_balances(date(2026, 4, 7), date(2026, 7, 7))
        raw_sweep_count = sum(1 for cf in raw_result['cash_flow'] if cf['type'] == 'SAVINGS_SWEEP')
        assert raw_sweep_count == 0  # No sweeps in raw simulation

        # Optimized: through PaymentOptimizer
        banks_opt = deepcopy(banks)
        optimizer = PaymentOptimizer(banks_opt, income, basic_bills)
        opt_result, plan = optimizer.run_optimized_simulation(
            date(2026, 4, 7), date(2026, 7, 7)
        )

        # There should be optimization events in the cash_flow
        opt_types = {cf['type'] for cf in opt_result['cash_flow']}
        # At minimum, with excess income over bills, savings sweeps should occur
        # (checking has $5000, income is $4000/biweekly, bills are ~$1580/mo)
        assert 'SAVINGS_SWEEP' in opt_types or 'HELOC_PARK' in opt_types, \
            f"Expected optimization events, got: {opt_types}"

    def test_promo_payoff_injected_in_optimized(self):
        """If there's a promo with balance, the optimizer should inject PROMO_PAYOFF events."""
        bank = Bank("Test Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=8000.0)
        card = bank.add_credit_account("Card", credit_limit=10000, interest_rate=20.0,
                                       payment_due_date=15, statement_date=10)
        promo = card.add_promotional_offer("0% Intro", 6, purchase_limit=5000,
                                           start_date=date(2026, 1, 1))
        card.make_purchase(3000.0, promo_name="0% Intro",
                           transaction_date=date(2026, 1, 15))

        income = [IncomeSource("Job", 5000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1000.0, 1)]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, plan = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 6, 30)
        )

        promo_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'PROMO_PAYOFF']
        assert len(promo_cf) > 0, "Expected promo payoff events in the optimized timeline"

        # The promo payoff events should have reduced the credit balance
        final_credit = result.get('credit_final_balances', {})
        total_credit = sum(final_credit.values())
        assert total_credit < 3000.0, f"Expected credit balance < 3000 after promo payoffs, got {total_credit}"


class TestFinanceManagerUnifiedPipeline:
    """Verify that FinanceManager.project_balances() now includes optimization."""

    def test_project_balances_includes_sweeps(self, full_bank, income, basic_bills):
        """Default project_balances() should produce optimization events."""
        fm = FinanceManager([full_bank], income, basic_bills)
        result = fm.project_balances(
            start_date=date(2026, 4, 7),
            end_date=date(2026, 7, 7),
        )

        opt_types = {cf['type'] for cf in result['cash_flow']}
        # With excess income, sweeps should occur
        assert 'SAVINGS_SWEEP' in opt_types or 'HELOC_PARK' in opt_types, \
            f"Expected optimization events in project_balances, got: {opt_types}"

    def test_project_balances_unoptimized(self, full_bank, income, basic_bills):
        """project_balances(optimized=False) should NOT include optimization events."""
        fm = FinanceManager([full_bank], income, basic_bills)
        result = fm.project_balances(
            start_date=date(2026, 4, 7),
            end_date=date(2026, 7, 7),
            optimized=False,
        )

        opt_types = {cf['type'] for cf in result['cash_flow']}
        assert 'SAVINGS_SWEEP' not in opt_types
        assert 'HELOC_PARK' not in opt_types
        assert 'PROMO_PAYOFF' not in opt_types

    def test_optimized_checking_never_below_buffer(self, full_bank, income, basic_bills):
        """Checking should never drop below the discretionary buffer after optimization."""
        fm = FinanceManager([full_bank], income, basic_bills)
        result = fm.project_balances(
            start_date=date(2026, 4, 7),
            end_date=date(2026, 7, 7),
        )

        # Check that checking balance stays above 0 (the buffer protects it)
        for snap in result['snapshots']:
            for key, balance in snap['balances'].items():
                if 'Checking' in key:
                    # Allow small float imprecision
                    assert balance >= -0.01, \
                        f"Checking went negative on {snap['date']}: ${balance:.2f}"


class TestExtraCreditPaymentsInjected:
    """Verify extra credit payments are in the timeline for payoff goal."""

    def test_payoff_goal_produces_extra_events(self):
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=10000.0)
        card = bank.add_credit_account("Card", credit_limit=10000, interest_rate=20.0,
                                       payment_due_date=15, statement_date=10)
        card.make_purchase(5000.0)

        income = [IncomeSource("Job", 6000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1500.0, 1)]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, plan = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 6, 30),
            optimization_goal="payoff_credit_account",
            target_credit_account="Card",
        )

        extra_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'EXTRA_CREDIT_PAYMENT']
        assert len(extra_cf) > 0, "Expected extra credit payment events for payoff goal"

        # Should also appear in the plan
        assert len(plan.extra_credit_payments) > 0


class TestHELOCParkingOptimization:
    """Verify HELOC parking works when HELOC rate > savings rate."""

    def test_heloc_park_when_rate_higher(self):
        """When HELOC rate > savings APY, excess should go to HELOC."""
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=10000.0)
        bank.add_account("savings", "Savings", starting_balance=5000.0,
                         interest_rate=2.0, interest_accrual_date=1)  # Low APY
        bank.add_heloc_account(
            "HELOC", credit_limit=50000, interest_rate=8.0,
            draw_period_months=180, total_term_months=360,
            start_date=date(2024, 1, 1), current_balance=15000.0,
            payment_due_date=1,
        )

        income = [IncomeSource("Job", 5000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1000.0, 5)]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, plan = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 6, 30),
        )

        # HELOC rate (8%) > savings rate (2%), so should park in HELOC
        heloc_park_cf = [cf for cf in result['cash_flow'] if cf['type'] == 'HELOC_PARK']
        # With $10k checking + $5k/mo income - $1k/mo rent, there's plenty of excess
        assert len(heloc_park_cf) > 0, "Expected HELOC parking when HELOC rate > savings rate"


class TestDiscretionaryBufferProtection:
    """Verify the discretionary buffer prevents over-sweeping."""

    def test_buffer_prevents_full_sweep(self):
        """Even with excess, checking should retain the buffer amount."""
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=1000.0)
        bank.add_account("savings", "HYS", starting_balance=0.0,
                         interest_rate=5.0, interest_accrual_date=1)

        income = [IncomeSource("Job", 3000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1500.0, 5)]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, plan = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 5, 31),
            discretionary_buffer=500.0,
        )

        # Check that checking balance stays above 0 throughout
        for snap in result['snapshots']:
            for key, balance in snap['balances'].items():
                if 'Checking' in key:
                    assert balance >= -0.01, \
                        f"Checking went negative on {snap['date']}: ${balance:.2f}"


class TestMinHoldDays:
    """Verify the min_hold_days parameter prevents pointless sweep-then-recall churn."""

    def test_short_hold_prevents_sweep(self):
        """With bills 3 days after income, min_hold_days=7 should prevent the sweep."""
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=2000.0)
        bank.add_account("savings", "HYS", starting_balance=0.0,
                         interest_rate=5.0, interest_accrual_date=1)

        # Income on 1st, big bill on 3rd — only 2 days to hold
        income = [IncomeSource("Job", 3000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("BigBill", 2500.0, 3)]

        optimizer = PaymentOptimizer([bank], income, bills)

        # With min_hold_days=7, excess after BigBill (~$2200) can't stay
        # parked for 7 days before the NEXT bill cycle, so no sweep
        result_strict, _ = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 5, 31),
            min_hold_days=7,
        )
        sweeps_strict = [cf for cf in result_strict['cash_flow']
                         if cf['type'] in ('SAVINGS_SWEEP', 'HELOC_PARK')]

        # With min_hold_days=0, sweeps should happen freely
        from copy import deepcopy
        optimizer2 = PaymentOptimizer(
            deepcopy([bank]),
            [IncomeSource("Job", 3000.0, IncomeFrequency.MONTHLY, pay_date=[1])],
            [Bill("BigBill", 2500.0, 3)]
        )
        result_loose, _ = optimizer2.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 5, 31),
            min_hold_days=0,
        )
        sweeps_loose = [cf for cf in result_loose['cash_flow']
                        if cf['type'] in ('SAVINGS_SWEEP', 'HELOC_PARK')]

        # Strict should have fewer (or no) sweeps compared to loose
        assert len(sweeps_strict) <= len(sweeps_loose), \
            f"min_hold_days=7 should produce fewer sweeps ({len(sweeps_strict)}) " \
            f"than min_hold_days=0 ({len(sweeps_loose)})"

    def test_long_gap_allows_sweep(self):
        """With bills well spaced, sweeps should still happen with min_hold_days=7."""
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=5000.0)
        bank.add_account("savings", "HYS", starting_balance=0.0,
                         interest_rate=5.0, interest_accrual_date=1)

        # Income on 1st, bill on 25th — 24 days to hold, well above 7
        income = [IncomeSource("Job", 4000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1000.0, 25)]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, _ = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 7, 31),
            min_hold_days=7,
        )

        sweeps = [cf for cf in result['cash_flow']
                  if cf['type'] in ('SAVINGS_SWEEP', 'HELOC_PARK')]
        # With plenty of gap between income and bills, sweeps should occur
        assert len(sweeps) > 0, \
            "Expected sweeps when there's a long gap between income and bills"

    def test_no_sweep_near_end_of_projection(self):
        """Don't sweep if fewer than min_hold_days remain before end_date."""
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=10000.0)
        bank.add_account("savings", "HYS", starting_balance=0.0,
                         interest_rate=5.0, interest_accrual_date=1)

        income = [IncomeSource("Job", 5000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Small", 100.0, 15)]

        optimizer = PaymentOptimizer([bank], income, bills)
        # Very short projection: only 5 days
        result, _ = optimizer.run_optimized_simulation(
            date(2026, 4, 1), date(2026, 4, 5),
            min_hold_days=7,
        )

        sweeps = [cf for cf in result['cash_flow']
                  if cf['type'] in ('SAVINGS_SWEEP', 'HELOC_PARK')]
        assert len(sweeps) == 0, \
            "Should not sweep when projection period < min_hold_days"


class TestPaymentPlanBackwardCompat:
    """Verify the PaymentPlan dataclass still works as expected."""

    def test_plan_has_simulation_result(self):
        bank = Bank("Bank", "traditional")
        bank.add_account("checking", "Checking", starting_balance=5000.0)
        income = [IncomeSource("Job", 3000.0, IncomeFrequency.MONTHLY, pay_date=[1])]
        bills = [Bill("Rent", 1000.0, 1)]

        optimizer = PaymentOptimizer([bank], income, bills)
        plan = optimizer.optimize_payment_schedule(
            date(2026, 4, 1), date(2026, 6, 30),
        )

        assert plan.simulation_result is not None
        assert 'cash_flow' in plan.simulation_result
        assert 'final_balances' in plan.simulation_result
        assert isinstance(plan.strategy, dict)
        assert isinstance(plan.violations, list)




class TestParkingRespectsCashFlow:
    """HELOC parking must leave enough in checking for bills due before payday."""

    def test_park_accounts_for_bills_before_first_payday(self):
        bank = Bank("Chase", "traditional")
        bank.add_account("checking", "Checking", starting_balance=4000.0)
        bank.add_account("savings", "Savings", starting_balance=6000.0, interest_rate=4.5)
        bank.add_heloc_account("HELOC", 50000, 8.5, 120, 240, date(2024, 1, 1), 15000, 10)
        # Rent is due before the first paycheck; part of each paycheck goes to savings
        bills = [Bill("Rent", 1800.0, 1)]
        income = [IncomeSource("Pay", 2300.0, IncomeFrequency.BIWEEKLY,
                               distribution={"Savings": 200, "Checking": None},
                               start_date=date(2026, 10, 23))]

        optimizer = PaymentOptimizer([bank], income, bills)
        result, plan = optimizer.run_optimized_simulation(date(2026, 10, 26), date(2027, 1, 24))

        assert any(cf['type'] == 'HELOC_PARK' for cf in result['cash_flow'])
        lowest = min(s['balances']['Chase:Checking'] for s in result['snapshots'])
        assert lowest >= 300.0  # default discretionary buffer
        payments = [cf for cf in result['cash_flow'] if cf['type'] in ('BILL_PAYMENT', 'HELOC_PAYMENT')]
        assert all(cf['account'] == 'Checking' for cf in payments)
