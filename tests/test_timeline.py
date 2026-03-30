"""
Tests for timeline simulator functionality.
"""

import pytest
from datetime import date, timedelta
from models.timeline_simulator import TimelineSimulator, TimelineEvent
from models.types import BillFrequency


class TestTimelineSimulator:
    """Test TimelineSimulator class functionality."""

    def test_timeline_creation(self, sample_bank, sample_income, sample_bills):
        """Test creating a timeline simulator."""
        simulator = TimelineSimulator([sample_bank], sample_income, sample_bills)

        assert len(simulator.banks) == 1
        assert len(simulator.income_sources) == 2
        assert len(simulator.bills) == 5
        assert len(simulator.events) == 0  # Not built yet

    def test_build_timeline_basic(self, sample_bank, sample_income, sample_bills):
        """Test building a basic timeline."""
        simulator = TimelineSimulator([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        # Should have events for income and bills
        assert len(events) > 0

        # Check event types
        event_types = [e.event_type for e in events]
        assert "INCOME" in event_types
        assert "BILL_DUE" in event_types

    def test_income_events_in_timeline(self, sample_bank, sample_income):
        """Test that income events are included in timeline."""
        simulator = TimelineSimulator([sample_bank], sample_income, [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        # Filter income events
        income_events = [e for e in events if e.event_type == "INCOME"]

        # Should have income on the 1st
        assert len(income_events) >= 1
        assert any(e.event_date == date(2024, 1, 1) for e in income_events)

    def test_bill_events_in_timeline(self, sample_bank, sample_bills):
        """Test that bill events are included in timeline."""
        simulator = TimelineSimulator([sample_bank], [], sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        # Filter bill events
        bill_events = [e for e in events if e.event_type == "BILL_DUE"]

        # Should have bills due in January
        assert len(bill_events) > 0

        # Check specific bills
        bill_names = [e.description for e in bill_events]
        assert any("Rent" in name for name in bill_names)

    def test_yearly_bill_in_timeline(self, sample_bank):
        """Test that yearly bills appear correctly in timeline."""
        # Create a yearly bill
        from models.fixed_bill import Bill
        yearly_bill = Bill(
            "Property Tax",
            2400,
            15,
            due_month=4,
            frequency=BillFrequency.YEARLY
        )

        simulator = TimelineSimulator([sample_bank], [], [yearly_bill])

        # Test period that includes April 15th
        start_date = date(2024, 4, 1)
        end_date = date(2024, 4, 30)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        bill_events = [e for e in events if e.event_type == "BILL_DUE"]
        assert len(bill_events) == 1
        assert bill_events[0].event_date == date(2024, 4, 15)
        assert "Property Tax" in bill_events[0].description

    def test_semi_annual_bill_in_timeline(self, sample_bank):
        """Test that semi-annual bills appear correctly in timeline."""
        from models.fixed_bill import Bill
        semi_bill = Bill(
            "Car Insurance",
            1200,
            1,
            due_month=1,
            frequency=BillFrequency.SEMI_ANNUAL
        )

        simulator = TimelineSimulator([sample_bank], [], [semi_bill])

        # Test period that includes July 1st (second occurrence)
        start_date = date(2024, 6, 1)
        end_date = date(2024, 7, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        bill_events = [e for e in events if e.event_type == "BILL_DUE"]
        assert len(bill_events) == 1
        assert bill_events[0].event_date == date(2024, 7, 1)
        assert "Car Insurance" in bill_events[0].description

    def test_mortgage_events_in_timeline(self, sample_mortgage_bank):
        """Test that mortgage payments appear in timeline."""
        simulator = TimelineSimulator([sample_mortgage_bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        mortgage_events = [e for e in events if e.event_type == "MORTGAGE_PAYMENT"]
        assert len(mortgage_events) == 1
        assert mortgage_events[0].event_date == date(2024, 1, 1)  # Due on 1st

    def test_interest_events_in_timeline(self, sample_bank):
        """Test that interest accrual events appear in timeline."""
        simulator = TimelineSimulator([sample_bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=True)

        interest_events = [e for e in events if e.event_type == "INTEREST"]
        # Should have interest on the 1st of the month for savings account
        assert len(interest_events) >= 1

    def test_credit_interest_events(self, sample_credit_bank):
        """Test credit card interest accrual in timeline."""
        # Add a balance to the credit card
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        card.charge(1000.00)

        simulator = TimelineSimulator([sample_credit_bank], [], [])

        start_date = date(2024, 1, 10)  # After statement date (10th)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=True)

        interest_events = [e for e in events if e.event_type == "INTEREST"]
        # Should have interest accrual on statement date (15th)
        interest_on_15th = any(e.event_date == date(2024, 1, 15) for e in interest_events)
        assert interest_on_15th

    def test_timeline_event_sorting(self, sample_bank, sample_income, sample_bills):
        """Test that timeline events are properly sorted by date."""
        simulator = TimelineSimulator([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=False)

        # Check that events are sorted by date
        dates = [e.event_date for e in events]
        assert dates == sorted(dates)

    def test_project_balances_basic(self, sample_bank, sample_income, sample_bills):
        """Test basic balance projection."""
        simulator = TimelineSimulator([sample_bank], sample_income, sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = simulator.project_balances(start_date, end_date)

        # Should have snapshots, final balances, and cash flow
        assert "snapshots" in result
        assert "final_balances" in result
        assert "cash_flow" in result

        # Should have daily snapshots
        assert len(result["snapshots"]) > 0

        # Should have final balances
        assert len(result["final_balances"]) > 0

    def test_project_balances_with_payments(self, sample_bank, sample_bills):
        """Test balance projection with bill payments."""
        simulator = TimelineSimulator([sample_bank], [], sample_bills)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        # Create payment strategy for bills
        strategy = {}
        for bill in sample_bills:
            if bill.bill_name == "Rent":
                strategy[bill.bill_name] = {
                    "bank": "Test Bank",
                    "account": "Primary Checking",
                    "date": date(2024, 1, 1)
                }

        result = simulator.project_balances(start_date, end_date, strategy)

        # Should have processed payments
        cash_flow = result["cash_flow"]
        payment_events = [cf for cf in cash_flow if cf.get("type") == "BILL_PAYMENT"]
        assert len(payment_events) > 0

    def test_timeline_event_creation(self):
        """Test creating timeline events."""
        event = TimelineEvent(
            event_date=date(2024, 1, 1),
            event_type="INCOME",
            amount=5000.00,
            description="Salary",
            account_name="Checking",
            bank_name="Test Bank"
        )

        assert event.event_date == date(2024, 1, 1)
        assert event.event_type == "INCOME"
        assert event.amount == 5000.00
        assert event.description == "Salary"
        assert event.account_name == "Checking"
        assert event.bank_name == "Test Bank"

    def test_timeline_event_sorting(self):
        """Test timeline event sorting."""
        events = [
            TimelineEvent(date(2024, 1, 3), "BILL", 100, "Bill C"),
            TimelineEvent(date(2024, 1, 1), "INCOME", 5000, "Income A"),
            TimelineEvent(date(2024, 1, 2), "BILL", 200, "Bill B"),
        ]

        sorted_events = sorted(events)

        assert sorted_events[0].event_date == date(2024, 1, 1)
        assert sorted_events[1].event_date == date(2024, 1, 2)
        assert sorted_events[2].event_date == date(2024, 1, 3)


class TestTimelineIntegration:
    """Test timeline simulator integration with other components."""

    def test_full_financial_timeline(self, sample_finance_manager, sample_date_range):
        """Test complete financial timeline simulation."""
        manager = sample_finance_manager
        start_date, end_date = sample_date_range

        simulator = TimelineSimulator(
            manager.banks,
            manager.income_sources,
            manager.bills
        )

        events = simulator.build_timeline(start_date, end_date, include_interest=True)

        # Should have various types of events
        event_types = set(e.event_type for e in events)
        expected_types = {"INCOME", "BILL_DUE", "MORTGAGE_PAYMENT", "INTEREST"}
        assert expected_types.issubset(event_types)

    def test_timeline_with_multiple_banks(self):
        """Test timeline with multiple bank types."""
        from models.bank import Bank

        # Create multiple banks
        checking_bank = Bank("Checking Bank")
        checking_bank.add_account("checking", "Checking", 5000)

        credit_bank = Bank("Credit Bank")
        credit_bank.add_credit_account("Credit Card", 5000)

        mortgage_bank = Bank("Mortgage Bank")
        mortgage_bank.add_mortgage_account("Mortgage", 200000)

        simulator = TimelineSimulator([checking_bank, credit_bank, mortgage_bank], [], [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=True)

        # Should have events from all banks
        bank_names = set(e.bank_name for e in events if e.bank_name)
        assert "Checking Bank" in bank_names
        assert "Credit Bank" in bank_names
        assert "Mortgage Bank" in bank_names

    def test_timeline_balance_accuracy(self, sample_bank, sample_income):
        """Test that timeline balance calculations are accurate."""
        simulator = TimelineSimulator([sample_bank], sample_income, [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        result = simulator.project_balances(start_date, end_date)

        # Check that balances make sense
        final_balances = result["final_balances"]

        # Should have positive balances (income added)
        for balance in final_balances.values():
            assert balance >= 0

        # Check cash flow accuracy
        cash_flow = result["cash_flow"]
        income_total = sum(cf["amount"] for cf in cash_flow if cf.get("type") == "INCOME")
        assert income_total > 0

