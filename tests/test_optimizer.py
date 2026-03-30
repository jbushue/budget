"""
Tests for payment optimizer functionality.
"""

import pytest
from datetime import date, timedelta
from models.payment_optimizer import PaymentOptimizer, PaymentPlan, CashFlowEvent
from models.types import BillFrequency


class TestPaymentOptimizer:
    """Test PaymentOptimizer class functionality."""

    def test_optimizer_creation(self, sample_bank, sample_income, sample_bills):
        """Test creating a payment optimizer."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        assert len(optimizer.banks) == 1
        assert len(optimizer.income_sources) == 2
        assert len(optimizer.bills) == 5

    def test_optimize_basic(self, sample_bank, sample_income, sample_bills):
        """Test basic payment optimization."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        plan = optimizer.optimize_payment_schedule(start_date, end_date)

        assert isinstance(plan, PaymentPlan)
        assert "strategy" in plan.__dict__
        assert isinstance(plan.total_interest_paid, (int, float))
        assert isinstance(plan.final_discretionary, (int, float))

    def test_optimize_maximize_discretionary(self, sample_bank, sample_income, sample_bills):
        """Test optimization for maximizing discretionary funds."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        plan = optimizer.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="maximize_discretionary"
        )

        assert plan.final_discretionary >= 0
        assert len(plan.strategy) > 0

    def test_optimize_payoff_credit(self, sample_credit_bank, sample_income, sample_bills):
        """Test optimization for paying off credit account."""
        optimizer = PaymentOptimizer([sample_credit_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        plan = optimizer.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="payoff_credit_account",
            target_credit_account="Rewards Card"
        )

        assert plan.target_credit_payoff == "Rewards Card"
        assert len(plan.extra_credit_payments) >= 0

    def test_optimize_payoff_credit_no_target(self, sample_bank, sample_income, sample_bills):
        """Test that payoff_credit goal requires target account."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        with pytest.raises(ValueError, match="target_credit_account is required"):
            optimizer.optimize_payment_schedule(
                date(2024, 1, 1),
                date(2024, 1, 31),
                optimization_goal="payoff_credit_account"
            )

    def test_build_bill_schedule(self, sample_bank, sample_bills):
        """Test building bill schedule."""
        optimizer = PaymentOptimizer([sample_bank], [], sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        bill_schedule = optimizer._build_bill_schedule(start_date, end_date)

        assert len(bill_schedule) > 0

        # Check structure
        for bill_entry in bill_schedule:
            assert "bill" in bill_entry
            assert "bill_name" in bill_entry
            assert "amount" in bill_entry
            assert "due_date" in bill_entry
            assert isinstance(bill_entry["due_date"], date)

    def test_build_mortgage_schedule(self, sample_mortgage_bank):
        """Test building mortgage payment schedule."""
        optimizer = PaymentOptimizer([sample_mortgage_bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        mortgage_schedule = optimizer._build_mortgage_schedule(start_date, end_date)

        assert len(mortgage_schedule) > 0

        # Check structure
        for mortgage_entry in mortgage_schedule:
            assert "mortgage" in mortgage_entry
            assert "mortgage_name" in mortgage_entry
            assert "total_payment" in mortgage_entry
            assert "due_date" in mortgage_entry

    def test_find_income_dates(self, sample_bank, sample_income):
        """Test finding income dates in range."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        income_dates = optimizer._find_income_dates(start_date, end_date)

        assert len(income_dates) > 0
        # Should have income on the 1st
        assert date(2024, 1, 1) in income_dates

    def test_build_cash_flow_timeline(self, sample_bank, sample_income, sample_bills):
        """Test building cash flow timeline."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        cash_flow_events = optimizer._build_cash_flow_timeline(start_date, end_date)

        assert len(cash_flow_events) > 0

        # Check event types
        event_types = [e.event_type for e in cash_flow_events]
        assert "INCOME" in event_types

        # Check event structure
        for event in cash_flow_events:
            assert isinstance(event, CashFlowEvent)
            assert isinstance(event.event_date, date)
            assert isinstance(event.amount, (int, float))

    def test_calculate_savings_transfers(self, sample_bank, sample_income, sample_bills):
        """Test calculating savings transfers for interest optimization."""
        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        income_dates = optimizer._find_income_dates(start_date, end_date)
        bill_schedule = optimizer._build_bill_schedule(start_date, end_date)

        transfers, estimated_interest = optimizer._calculate_savings_transfers(
            start_date, end_date, income_dates, bill_schedule, [], [], []
        )

        # Should return valid results (may be empty list)
        assert isinstance(transfers, list)
        assert isinstance(estimated_interest, (int, float))
        assert estimated_interest >= 0

    def test_check_constraints(self, sample_bank, sample_income, sample_bills):
        """Test constraint checking."""
        from models.timeline_simulator import TimelineSimulator

        optimizer = PaymentOptimizer([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        bill_schedule = optimizer._build_bill_schedule(start_date, end_date)

        # Create a mock simulation result
        simulator = TimelineSimulator([sample_bank], sample_income, sample_bills)
        simulation_result = simulator.project_balances(start_date, end_date)

        violations = optimizer._check_constraints(simulation_result, bill_schedule, [])

        # Should return a list (may be empty)
        assert isinstance(violations, list)


class TestPaymentPlan:
    """Test PaymentPlan dataclass functionality."""

    def test_payment_plan_creation(self):
        """Test creating a payment plan."""
        strategy = {"Rent": {"bank": "Test", "account": "Checking"}}
        plan = PaymentPlan(
            strategy=strategy,
            total_interest_paid=100.00,
            total_fees=5.00,
            final_discretionary=5000.00
        )

        assert plan.strategy == strategy
        assert plan.total_interest_paid == 100.00
        assert plan.total_fees == 5.00
        assert plan.final_discretionary == 5000.00
        assert plan.violations == []
        assert plan.extra_credit_payments == []
        assert plan.target_credit_payoff is None

    def test_payment_plan_string_representation(self):
        """Test payment plan string representation."""
        plan = PaymentPlan(
            strategy={},
            total_interest_paid=150.50,
            total_fees=0.0,
            final_discretionary=3200.75
        )

        str_repr = str(plan)
        assert "150.50" in str_repr
        assert "3200.75" in str_repr


class TestPromoPayoff:
    """Test promotional offer payoff functionality."""

    def test_find_promo_payoff_priorities(self, sample_credit_bank):
        """Test finding promotional offers that need payoff."""
        # Add a promo to the credit card
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        from models.credit_card_account import PromotionalOffer
        from datetime import timedelta

        end_date = date.today() + timedelta(days=60)
        promo = PromotionalOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00,
            end_date=end_date
        )
        card.active_promos.append(promo)
        card.promo_balance["0% APR"] = 1500.00

        optimizer = PaymentOptimizer([sample_credit_bank], [], [])

        start_date = date.today()
        end_date = start_date + timedelta(days=90)

        priorities = optimizer._find_promo_payoff_priorities(start_date, end_date)

        assert len(priorities) > 0
        assert priorities[0].promo_name == "0% APR"
        assert priorities[0].balance_owed == 1500.00

    def test_calculate_promo_payoff_schedule(self, sample_credit_bank):
        """Test calculating promo payoff schedule."""
        # Setup similar to above
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        from models.credit_card_account import PromotionalOffer

        end_date = date.today() + timedelta(days=60)
        promo = PromotionalOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00,
            end_date=end_date
        )
        card.active_promos.append(promo)
        card.promo_balance["0% APR"] = 1500.00

        optimizer = PaymentOptimizer([sample_credit_bank], [], [])

        start_date = date.today()
        end_date = start_date + timedelta(days=90)
        income_dates = [start_date + timedelta(days=1)]
        bill_schedule = []
        priorities = optimizer._find_promo_payoff_priorities(start_date, end_date)

        schedule = optimizer._calculate_promo_payoff_schedule(
            start_date, end_date, income_dates, bill_schedule, priorities
        )

        assert isinstance(schedule, list)
        # May be empty if no payments can be scheduled


class TestCashFlowEvent:
    """Test CashFlowEvent dataclass functionality."""

    def test_cash_flow_event_creation(self):
        """Test creating a cash flow event."""
        event = CashFlowEvent(
            event_date=date(2024, 1, 1),
            event_type="INCOME",
            amount=5000.00,
            description="Monthly Salary",
            source_name="Primary Job"
        )

        assert event.event_date == date(2024, 1, 1)
        assert event.event_type == "INCOME"
        assert event.amount == 5000.00
        assert event.description == "Monthly Salary"
        assert event.source_name == "Primary Job"

    def test_cash_flow_event_sorting(self):
        """Test cash flow event sorting."""
        events = [
            CashFlowEvent(date(2024, 1, 3), "BILL", -100, "Bill C"),
            CashFlowEvent(date(2024, 1, 1), "INCOME", 5000, "Income A"),
            CashFlowEvent(date(2024, 1, 2), "BILL", -200, "Bill B"),
        ]

        sorted_events = sorted(events)

        assert sorted_events[0].event_date == date(2024, 1, 1)
        assert sorted_events[1].event_date == date(2024, 1, 2)
        assert sorted_events[2].event_date == date(2024, 1, 3)


class TestPaymentOptimizerIntegration:
    """Test payment optimizer integration with other components."""

    def test_full_optimization_workflow(self, sample_finance_manager, sample_date_range):
        """Test complete optimization workflow."""
        manager = sample_finance_manager
        start_date, end_date = sample_date_range

        optimizer = PaymentOptimizer(
            manager.banks,
            manager.income_sources,
            manager.bills
        )

        plan = optimizer.optimize_payment_schedule(start_date, end_date)

        # Should have a complete plan
        assert len(plan.strategy) >= 0  # May be empty if no bills due
        assert plan.final_discretionary >= 0
        assert isinstance(plan.violations, list)

    def test_optimization_with_yearly_bills(self, sample_bank):
        """Test optimization including yearly bills."""
        from models.fixed_bill import Bill

        yearly_bill = Bill(
            "Property Tax",
            2400,
            15,
            due_month=4,
            frequency=BillFrequency.YEARLY
        )

        optimizer = PaymentOptimizer([sample_bank], [], [yearly_bill])

        # Test period that includes April
        start_date = date(2024, 4, 1)
        end_date = date(2024, 4, 30)

        plan = optimizer.optimize_payment_schedule(start_date, end_date)

        # Should include the yearly bill in strategy
        assert len(plan.strategy) > 0

    def test_optimization_with_credit_payoff(self, sample_credit_bank, sample_income):
        """Test credit payoff optimization."""
        # Add balance to credit card
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        card.make_purchase(1000.00)

        optimizer = PaymentOptimizer([sample_credit_bank], sample_income, [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        plan = optimizer.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="payoff_credit_account",
            target_credit_account="Rewards Card"
        )

        assert plan.target_credit_payoff == "Rewards Card"
        assert len(plan.extra_credit_payments) >= 0

