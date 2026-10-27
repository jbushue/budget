"""
Tests for the BillGroup feature — bundled payments for student loans, etc.
"""

import pytest
from datetime import date, timedelta
from copy import deepcopy

from models.bank import Bank
from models.bill_group import BillGroup, BillGroupMember
from models.credit_card_account import CreditAccount
from models.fixed_bill import Bill
from models.income_source import IncomeSource, IncomeFrequency
from models.finance_manager import FinanceManager
from models.timeline_simulator import TimelineSimulator
from models.types import AllocationMethod, BillFrequency


# ── Fixtures ──

@pytest.fixture
def loan_servicer_bank():
    """A bank representing a student-loan servicer with 3 sub-loans."""
    bank = Bank("Student Loan Servicer", bank_type="credit_issuer")

    loan_a = bank.add_credit_account("Subsidized Loan A", credit_limit=50000, interest_rate=4.5, payment_due_date=15)
    loan_a.balance = 12000.0
    loan_a.regular_balance = 12000.0

    loan_b = bank.add_credit_account("Subsidized Loan B", credit_limit=50000, interest_rate=5.0, payment_due_date=15)
    loan_b.balance = 8000.0
    loan_b.regular_balance = 8000.0

    loan_c = bank.add_credit_account("Unsubsidized Loan C", credit_limit=50000, interest_rate=6.8, payment_due_date=15)
    loan_c.balance = 5000.0
    loan_c.regular_balance = 5000.0

    return bank


@pytest.fixture
def checking_bank():
    """A bank with a checking account for making payments."""
    bank = Bank("My Bank", bank_type="traditional")
    bank.add_account("checking", "Primary Checking", starting_balance=10000.0)
    return bank


@pytest.fixture
def student_loan_group(loan_servicer_bank):
    """A bill group tying together the three student sub-loans."""
    group = BillGroup(
        group_name="Federal Student Loans",
        total_payment=500.0,
        due_date=15,
        frequency=BillFrequency.MONTHLY,
        group_type="student_loan",
        preferred_source_bank="My Bank",
        preferred_source_account="Primary Checking",
    )
    group.add_member("Student Loan Servicer", "Subsidized Loan A")
    group.add_member("Student Loan Servicer", "Subsidized Loan B")
    group.add_member("Student Loan Servicer", "Unsubsidized Loan C")
    return group


# ── Model tests ──

class TestBillGroupModel:

    def test_create_bill_group(self, student_loan_group):
        assert student_loan_group.group_name == "Federal Student Loans"
        assert student_loan_group.total_payment == 500.0
        assert len(student_loan_group.members) == 3

    def test_add_duplicate_member_raises(self, student_loan_group):
        with pytest.raises(ValueError, match="already a member"):
            student_loan_group.add_member("Student Loan Servicer", "Subsidized Loan A")

    def test_remove_member(self, student_loan_group):
        assert student_loan_group.remove_member("Student Loan Servicer", "Subsidized Loan B")
        assert len(student_loan_group.members) == 2

    def test_remove_nonexistent_member(self, student_loan_group):
        assert not student_loan_group.remove_member("Fake Bank", "Fake Account")

    def test_get_total_balance(self, student_loan_group, loan_servicer_bank):
        total = student_loan_group.get_total_balance([loan_servicer_bank])
        assert total == pytest.approx(25000.0)

    def test_get_member_details(self, student_loan_group, loan_servicer_bank):
        details = student_loan_group.get_member_details([loan_servicer_bank])
        assert len(details) == 3
        names = [d["account_name"] for d in details]
        assert "Subsidized Loan A" in names

    def test_get_next_due_date(self, student_loan_group):
        ref = date(2026, 4, 1)
        next_due = student_loan_group.get_next_due_date(ref)
        assert next_due == date(2026, 4, 15)

    def test_get_next_due_date_past(self, student_loan_group):
        ref = date(2026, 4, 16)
        next_due = student_loan_group.get_next_due_date(ref)
        assert next_due == date(2026, 5, 15)

    def test_mark_paid_and_reset(self, student_loan_group):
        student_loan_group.mark_paid(date(2026, 4, 15))
        assert student_loan_group.is_paid_this_period
        assert len(student_loan_group.payment_history) == 1
        student_loan_group.reset_period()
        assert not student_loan_group.is_paid_this_period

    def test_grouped_account_keys(self, student_loan_group):
        keys = student_loan_group.get_grouped_account_keys()
        assert ("Student Loan Servicer", "Subsidized Loan A") in keys
        assert len(keys) == 3

    def test_copy(self, student_loan_group):
        copied = student_loan_group.copy()
        assert copied.group_name == student_loan_group.group_name
        assert copied is not student_loan_group
        assert copied.members is not student_loan_group.members

    def test_invalid_due_date(self):
        with pytest.raises(ValueError, match="Due date must be between"):
            BillGroup("Bad", 100, due_date=0)

    def test_negative_payment(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            BillGroup("Bad", -100, due_date=1)


# ── Payment Distribution tests ──

class TestPaymentDistribution:

    def test_proportional_distribution(self, student_loan_group, loan_servicer_bank):
        """Payment should be distributed proportional to balance."""
        results = student_loan_group.distribute_payment(500.0, [loan_servicer_bank])
        # Total balance = 25000 → A(12000)=48%, B(8000)=32%, C(5000)=20%
        total_distributed = sum(r["amount"] for r in results)
        assert total_distributed == pytest.approx(500.0, abs=0.02)

        # Check proportions
        amounts = {r["account_name"]: r["amount"] for r in results}
        assert amounts["Subsidized Loan A"] == pytest.approx(240.0, abs=0.01)
        assert amounts["Subsidized Loan B"] == pytest.approx(160.0, abs=0.01)
        assert amounts["Unsubsidized Loan C"] == pytest.approx(100.0, abs=0.01)

    def test_equal_distribution(self, loan_servicer_bank):
        group = BillGroup("Equal Test", 300.0, due_date=15)
        group.add_member("Student Loan Servicer", "Subsidized Loan A", AllocationMethod.EQUAL)
        group.add_member("Student Loan Servicer", "Subsidized Loan B", AllocationMethod.EQUAL)
        group.add_member("Student Loan Servicer", "Unsubsidized Loan C", AllocationMethod.EQUAL)

        results = group.distribute_payment(300.0, [loan_servicer_bank])
        amounts = [r["amount"] for r in results]
        assert all(a == pytest.approx(100.0, abs=0.01) for a in amounts)

    def test_fixed_distribution(self, loan_servicer_bank):
        group = BillGroup("Fixed Test", 400.0, due_date=15)
        group.add_member("Student Loan Servicer", "Subsidized Loan A", AllocationMethod.FIXED, fixed_amount=200.0)
        group.add_member("Student Loan Servicer", "Subsidized Loan B", AllocationMethod.FIXED, fixed_amount=150.0)
        group.add_member("Student Loan Servicer", "Unsubsidized Loan C", AllocationMethod.FIXED, fixed_amount=50.0)

        results = group.distribute_payment(400.0, [loan_servicer_bank])
        amounts = {r["account_name"]: r["amount"] for r in results}
        assert amounts["Subsidized Loan A"] == pytest.approx(200.0)
        assert amounts["Subsidized Loan B"] == pytest.approx(150.0)
        assert amounts["Unsubsidized Loan C"] == pytest.approx(50.0)

    def test_distribution_reduces_balances(self, student_loan_group, loan_servicer_bank):
        original_total = student_loan_group.get_total_balance([loan_servicer_bank])
        student_loan_group.distribute_payment(500.0, [loan_servicer_bank])
        new_total = student_loan_group.get_total_balance([loan_servicer_bank])
        assert new_total == pytest.approx(original_total - 500.0, abs=0.02)

    def test_no_members_with_balance(self, loan_servicer_bank):
        """If all members have zero balance, nothing happens."""
        for acc in loan_servicer_bank.get_all_credit_accounts():
            acc.balance = 0.0
            acc.regular_balance = 0.0
        group = BillGroup("Zero Test", 500.0, due_date=15)
        group.add_member("Student Loan Servicer", "Subsidized Loan A")
        results = group.distribute_payment(500.0, [loan_servicer_bank])
        assert results == []


# ── Timeline Simulator Integration tests ──

class TestBillGroupTimeline:

    def test_group_event_generated(self, checking_bank, loan_servicer_bank, student_loan_group):
        """Timeline should generate a BILL_GROUP_PAYMENT event on the due date."""
        sim = TimelineSimulator(
            [checking_bank, loan_servicer_bank], [], [],
            bill_groups=[student_loan_group]
        )
        # Choose a range that includes day 15
        start = date(2026, 4, 1)
        end = date(2026, 4, 30)
        events = sim.build_timeline(start, end)

        group_events = [e for e in events if e.event_type == "BILL_GROUP_PAYMENT"]
        assert len(group_events) == 1
        assert group_events[0].event_date == date(2026, 4, 15)
        assert group_events[0].amount == 500.0

    def test_grouped_accounts_suppress_individual_credit_events(
        self, checking_bank, loan_servicer_bank, student_loan_group
    ):
        """Individual credit payment BILL_DUE events should NOT be generated for grouped accounts."""
        sim = TimelineSimulator(
            [checking_bank, loan_servicer_bank], [], [],
            bill_groups=[student_loan_group]
        )
        start = date(2026, 4, 1)
        end = date(2026, 4, 30)
        events = sim.build_timeline(start, end)

        # Find all BILL_DUE events for auto-generated linked bills
        from models.fixed_bill import AccountLinkedBill
        credit_bill_events = [
            e for e in events
            if e.event_type == "BILL_DUE" and "[Auto]" in e.description
        ]
        # None of the grouped accounts should produce individual credit events
        grouped_names = {"Subsidized Loan A", "Subsidized Loan B", "Unsubsidized Loan C"}
        for ce in credit_bill_events:
            bill_name = ce.description.replace("Bill: [Auto] ", "").replace(" Payment", "")
            assert bill_name not in grouped_names

    def test_group_payment_processed_in_simulation(
        self, checking_bank, loan_servicer_bank, student_loan_group
    ):
        """project_balances should withdraw from checking and distribute to sub-loans."""
        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, pay_date=[1])
        sim = TimelineSimulator(
            [checking_bank, loan_servicer_bank],
            [income],
            [],
            bill_groups=[student_loan_group]
        )

        start = date(2026, 4, 1)
        end = date(2026, 4, 30)
        result = sim.project_balances(start, end)

        # Check cash flow for the group payment
        group_cf = [cf for cf in result["cash_flow"] if cf["type"] == "BILL_GROUP_PAYMENT"]
        assert len(group_cf) == 1
        assert group_cf[0]["amount"] == -500.0
        assert "sub_payments" in group_cf[0]
        assert len(group_cf[0]["sub_payments"]) == 3


# ── FinanceManager Integration tests ──

class TestBillGroupFinanceManager:

    def test_manager_with_groups(self, checking_bank, loan_servicer_bank, student_loan_group):
        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, pay_date=[1])
        manager = FinanceManager(
            banks=[checking_bank, loan_servicer_bank],
            income_sources=[income],
            bills=[],
            bill_groups=[student_loan_group],
        )
        assert len(manager.bill_groups) == 1
        assert len(manager.get_all_bill_groups()) == 1

    def test_add_remove_bill_group(self, checking_bank, loan_servicer_bank):
        manager = FinanceManager([checking_bank, loan_servicer_bank], [], [])
        group = BillGroup("Test Group", 100.0, due_date=1)
        manager.add_bill_group(group)
        assert len(manager.bill_groups) == 1
        manager.remove_bill_group(group)
        assert len(manager.bill_groups) == 0

    def test_grouped_account_keys(self, checking_bank, loan_servicer_bank, student_loan_group):
        manager = FinanceManager(
            [checking_bank, loan_servicer_bank], [], [],
            bill_groups=[student_loan_group]
        )
        keys = manager.get_grouped_account_keys()
        assert ("Student Loan Servicer", "Subsidized Loan A") in keys
        assert len(keys) == 3

    def test_safe_to_spend_includes_groups(self, checking_bank, loan_servicer_bank, student_loan_group):
        """Bill group payment should be included in committed bills for safe-to-spend."""
        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, pay_date=[28])
        manager = FinanceManager(
            [checking_bank, loan_servicer_bank],
            [income],
            [],
            bill_groups=[student_loan_group],
        )
        result = manager.calculate_safe_to_spend()
        # The $500 group payment should be committed
        assert result["committed_bills"] >= 500.0

