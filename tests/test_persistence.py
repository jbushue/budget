"""
Tests for saving to / loading from the SQLite database.

Each test runs against a throwaway database file, never the real one.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine

import models.database as db
from models.bank import Bank
from models.bill_group import BillGroup
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill, AccountLinkedBill, GroupLinkedBill
from models.income_source import IncomeSource
from models.types import CreditAccountStatus, MortgageStatus


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the ORM at a temporary SQLite file for the duration of a test."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.SessionLocal.configure(bind=engine)
    db.init_db()
    yield engine
    db.SessionLocal.configure(bind=create_engine(db.DATABASE_URL))


def _loaded_manager() -> FinanceManager:
    manager = FinanceManager([], [], [])
    assert manager.load_from_database()
    return manager


def _build_manager() -> FinanceManager:
    bank = Bank("Chase")
    bank.add_account("checking", "Checking", 5000.0)
    bank.add_account("savings", "Savings", 1000.0, 4.0)
    card = bank.add_credit_account("Visa", 10000, 20.0, payment_due_date=15, statement_date=10)
    card.balance = card.regular_balance = 1200.0
    bank.add_credit_account("Loan", 20000, 5.0, payment_due_date=5).balance = 8000.0
    bank.add_mortgage_account("Home", 300000, 6.0, 360, 250000, 1)
    bank.add_heloc_account("HELOC", 50000, 8.0, 120, 240, date(2024, 1, 1), 10000, 20)
    income = [IncomeSource("Job", 4000.0, "monthly", [1], {"Checking": None})]
    bills = [Bill("Rent", 1500.0, 1), Bill("Gym", 50.0, 3)]
    group = BillGroup("Loans", total_payment=200.0, due_date=5)
    group.add_member("Chase", "Loan")
    manager = FinanceManager([bank], income, bills, [group])
    manager._db_sync_deletions = True  # in-memory state is authoritative here
    return manager


class TestDeletesPersist:

    def test_deleted_items_stay_deleted(self, temp_db):
        manager = _build_manager()
        manager.save_to_database()

        manager = _loaded_manager()
        bank = manager.banks[0]
        manager.bills = [b for b in manager.bills if b.bill_name != "Gym"]
        manager.income_sources.clear()
        del bank.accounts["Savings"]
        del bank.heloc_accounts["HELOC"]
        manager.save_to_database()

        reloaded = _loaded_manager()
        names = [b.bill_name for b in reloaded.bills]
        assert "Gym" not in names
        assert "[Auto] HELOC Payment" not in names
        assert reloaded.income_sources == []
        assert "Savings" not in reloaded.banks[0].accounts
        assert "HELOC" not in reloaded.banks[0].heloc_accounts

    def test_deleted_bank_and_group_stay_deleted(self, temp_db):
        manager = _build_manager()
        manager.save_to_database()

        manager = _loaded_manager()
        manager.remove_bill_group(manager.bill_groups[0])
        manager.save_to_database()
        assert _loaded_manager().bill_groups == []

        manager = _loaded_manager()
        manager.remove_bank(manager.banks[0])
        manager.save_to_database()
        reloaded = _loaded_manager()
        assert reloaded.banks == []
        assert not any(isinstance(b, AccountLinkedBill) for b in reloaded.bills)

    def test_no_pruning_without_successful_load(self, temp_db):
        _build_manager().save_to_database()
        # A manager that never loaded must not wipe the database
        FinanceManager([], [], []).save_to_database()
        assert len(_loaded_manager().banks) == 1


class TestEditsPersist:

    def test_account_edits_round_trip(self, temp_db):
        _build_manager().save_to_database()
        manager = _loaded_manager()
        bank = manager.banks[0]
        card = bank.credit_accounts["Visa"]
        card.credit_limit = 7500
        card.payment_due_date = 20
        card.status = CreditAccountStatus.FROZEN
        mortgage = bank.mortgage_accounts["Home"]
        mortgage.loan_term_months = 180
        mortgage.status = MortgageStatus.REFINANCED
        manager.save_to_database()

        bank = _loaded_manager().banks[0]
        card = bank.credit_accounts["Visa"]
        assert (card.credit_limit, card.payment_due_date, card.status) == (7500, 20, CreditAccountStatus.FROZEN)
        mortgage = bank.mortgage_accounts["Home"]
        assert mortgage.loan_term_months == 180
        assert mortgage.status == MortgageStatus.REFINANCED

    def test_distribution_type_round_trips(self, temp_db):
        manager = _build_manager()
        manager.income_sources[0].distribution = None
        from models.types import DistributionType
        manager.income_sources[0].distribution = DistributionType.__fromdict__(
            {"Savings": {"value": 0.5, "type": "fixed_amount"}, "Checking": None})
        manager.save_to_database()

        dist = _loaded_manager().income_sources[0].distribution
        assert dist.get_distribution_type("Savings").value == "fixed_amount"


class TestPaidStatusPersists:

    def test_linked_and_group_bills_keep_paid_flag(self, temp_db):
        manager = _build_manager()
        for bill in manager.bills:
            if bill.bill_name in ("[Auto] Home Payment", "[Auto] HELOC Payment", "[Auto] Loans Payment"):
                bill.is_paid_this_period = True
        manager.save_to_database()

        paid = {b.bill_name: b.is_paid_this_period for b in _loaded_manager().bills}
        assert paid["[Auto] Home Payment"]
        assert paid["[Auto] HELOC Payment"]
        assert paid["[Auto] Loans Payment"]
        assert not paid["Rent"]

    def test_auto_reset_works_after_restart(self, temp_db):
        manager = _build_manager()
        rent = next(b for b in manager.bills if b.bill_name == "Rent")
        rent.mark_paid("Chase", "Checking", payment_date=date(2020, 1, 1))
        group_bill = next(b for b in manager.bills if isinstance(b, GroupLinkedBill))
        group_bill.mark_paid("Chase", "Checking", payment_date=date(2020, 1, 1), banks=manager.banks)
        manager.save_to_database()

        manager = _loaded_manager()
        assert manager.auto_reset_periods() >= 2
        paid = {b.bill_name: b.is_paid_this_period for b in manager.bills}
        assert not paid["Rent"]
        assert not paid["[Auto] Loans Payment"]

    def test_same_card_name_in_two_banks(self, temp_db):
        a, b = Bank("A"), Bank("B")
        for bank in (a, b):
            bank.add_account("checking", "Chk", 1000.0)
            bank.add_credit_account("Visa", 5000, 20.0).balance = 500.0
        manager = FinanceManager([a, b], [], [])
        bill_a = next(x for x in manager.bills if x.linked_bank_name == "A")
        bill_a.is_paid_this_period = True
        bill_a.carryover_balance = 12.5
        manager.save_to_database()

        linked = {x.linked_bank_name: x for x in _loaded_manager().bills if isinstance(x, AccountLinkedBill)}
        assert linked["A"].is_paid_this_period and linked["A"].carryover_balance == 12.5
        assert not linked["B"].is_paid_this_period and linked["B"].carryover_balance == 0.0
