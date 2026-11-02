"""Regression tests for bugs found in review."""

from datetime import date, timedelta

import pytest

from models import ledger
from models.bank import Bank
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.timeline_simulator import TimelineSimulator
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()


def reload():
    m = FinanceManager([], [], [])
    assert m.load_from_database()
    return m


def test_removed_payment_stays_removed_and_later_payments_are_kept(api):  # noqa: F811
    api('mutation { createBill(billName: "Gym", amount: 40, dueDate: 3) { success } }')
    api('mutation { markBillPaid(billName: "Gym", paymentDate: "2026-09-03") { success } }')
    api('mutation { markBillPaid(billName: "Gym", paymentDate: "2026-10-03") { success } }')
    gym = next(b for b in api.manager.bills if b.bill_name == "Gym")
    gym.payment_history.pop()  # e.g. a bank match undone
    api.manager.save_to_database()
    api('mutation { markBillPaid(billName: "Gym", paymentDate: "2026-10-06") { success } }')
    dates = [str(p["date"]) for p in next(b for b in reload().bills if b.bill_name == "Gym").payment_history]
    assert dates == ["2026-09-03", "2026-10-06"]


def test_same_payment_twice_in_a_row_is_refused(api):  # noqa: F811
    api('mutation { createBill(billName: "Phone", amount: 80, dueDate: 9) { success } }')
    q = ('mutation { markBillPaid(billName: "Phone", paymentDate: "2026-10-09", sourceBank: "B", '
         'sourceAccount: "Chk") { success message } }')
    assert api(q)["markBillPaid"]["success"] is True
    again = api(q)["markBillPaid"]
    assert again["success"] is False and "just recorded" in again["message"]
    assert api.manager.banks[0].accounts["Chk"].balance == pytest.approx(3000 - 80)


def test_bill_paid_on_its_due_date_is_still_owed_next_month():
    bank = Bank("B")
    bank.add_account("checking", "Chk", 5000.0)
    rent = Bill("Rent", 1000.0, 5)
    rent.is_paid_this_period = True
    rent.payment_history = [{"date": date(2026, 11, 5), "amount_paid": 1000.0}]
    r = TimelineSimulator([bank], [], [rent]).project_balances(date(2026, 11, 6), date(2026, 12, 10))
    assert any(cf["type"] == "BILL_PAYMENT" and cf["date"] == date(2026, 12, 5) for cf in r["cash_flow"])


def test_auto_reset_clears_a_flag_once_its_due_date_has_passed(monkeypatch):
    bank = Bank("B")
    bank.add_account("checking", "Chk", 5000.0)
    rent = Bill("Rent", 1000.0, TODAY.day if TODAY.day <= 28 else 28)
    paid_on = TODAY - timedelta(days=40)
    rent.is_paid_this_period = True
    rent.payment_history = [{"date": paid_on, "amount_paid": 1000.0}]
    m = FinanceManager([bank], [], [rent])
    monkeypatch.setattr(m, "save_to_database", lambda: True)
    assert m.auto_reset_periods() == 1 and not rent.is_paid_this_period


def test_income_without_a_split_goes_to_checking_even_if_a_card_is_listed_first():
    cards = Bank("Cards")
    cards.add_credit_account("Visa", 5000, 20.0, payment_due_date=10)
    bank = Bank("B")
    bank.add_account("savings", "Sav", 100.0)
    bank.add_account("checking", "Chk", 100.0)
    pay = (TODAY + timedelta(days=2)).day
    inc = IncomeSource("Job", 1000.0, "monthly", [min(pay, 28)])
    r = TimelineSimulator([cards, bank], [inc], []).project_balances(TODAY, TODAY + timedelta(days=31))
    deposits = [cf for cf in r["cash_flow"] if cf["type"] == "INCOME"]
    assert deposits and all(cf["account"] == "Chk" for cf in deposits)


def test_card_without_a_statement_day_still_charges_interest():
    bank = Bank("B")
    bank.add_account("checking", "Chk", 0.0)
    card = bank.add_credit_account("Visa", 10000, 24.0, payment_due_date=None)
    card.balance = card.regular_balance = 5000.0
    r = TimelineSimulator([bank], [], []).project_balances(TODAY, TODAY + timedelta(days=62))
    assert sum(cf["amount"] for cf in r["cash_flow"] if cf["type"] == "INTEREST") > 150


def test_day_31_interest_cycle_has_no_phantom_interest():
    bank = Bank("B")
    bank.add_account("checking", "Chk", 10000.0)
    card = bank.add_credit_account("Visa", 10000, 24.0, statement_date=31)
    card.balance = card.regular_balance = 3000.0
    sim = TimelineSimulator([bank], [], [])
    from models.timeline_simulator import TimelineEvent
    pay = {date(2027, 1, 2): [TimelineEvent(event_date=date(2027, 1, 2), event_type="EXTRA_DEBT_PAYMENT",
                                            amount=3000.0, description="Pay it off", from_bank="B",
                                            from_account="Chk", to_account="Visa")]}
    r = sim.project_balances(date(2027, 1, 1), date(2027, 3, 5), injected_events=pay)
    feb = [cf for cf in r["cash_flow"] if cf["type"] == "INTEREST" and cf["date"].month == 2]
    # Paid off Jan 2: February only charges interest on January's few cents of interest
    # (the old cycle math charged ~$10 on a balance that was gone)
    assert sum(cf["amount"] for cf in feb) < 0.5


def test_lowering_a_card_balance_shrinks_its_promos():
    bank = Bank("B")
    card = bank.add_credit_account("Visa", 5000, 20.0)
    card.balance, card.regular_balance, card.promo_balance = 600.0, 0.0, {"0%": 600.0}
    bank.update_credit_balance("Visa", 200.0)
    assert card.promo_balance["0%"] == pytest.approx(200.0) and card.regular_balance == 0.0


def test_rejected_bill_edit_changes_nothing(api):  # noqa: F811
    api('mutation { createBill(billName: "Water", amount: 50, dueDate: 9) { success } }')
    out = api('mutation { updateBill(billName: "Water", amount: 99, dueDate: 40) { success message } }')
    assert out["updateBill"]["success"] is False
    assert next(b for b in api.manager.bills if b.bill_name == "Water").amount == 50


def test_bill_start_date_and_due_month_can_be_cleared(api):  # noqa: F811
    api('mutation { createBill(billName: "Tax", amount: 900, dueDate: 9, frequency: "yearly", dueMonth: 4, '
        'startDate: "2026-04-09") { success } }')
    api('mutation { updateBill(billName: "Tax", startDate: "", dueMonth: 0) { success } }')
    tax = next(b for b in api.manager.bills if b.bill_name == "Tax")
    assert tax.start_date is None and not tax.due_month


def test_bad_pay_day_is_refused(api):  # noqa: F811
    out = api('mutation { createIncomeSource(sourceName: "Job", amount: 100, frequency: "monthly", payDates: [0], '
              'distribution: "{}") { success message } }')
    assert out["createIncomeSource"]["success"] is False


def test_weekly_income_gets_a_fixed_start_date(api):  # noqa: F811
    api('mutation { createIncomeSource(sourceName: "Gig", amount: 300, frequency: "weekly", payDates: [5], '
        'distribution: "{}") { success } }')
    assert next(i for i in reload().income_sources if i.source_name == "Gig").start_date is not None


def test_duplicate_loan_group_name_is_refused(api):  # noqa: F811
    q = 'mutation { createBillGroup(groupName: "Loans", totalPayment: 300, dueDate: 5) { success message } }'
    assert api(q)["createBillGroup"]["success"] is True
    assert api(q)["createBillGroup"]["success"] is False


def test_identical_rows_in_one_csv_are_both_imported(temp_db):  # noqa: F811
    csv = "Date,Description,Amount\n2026-10-01,Bus fare,-2.90\n2026-10-01,Bus fare,-2.90\n"
    assert ledger.import_csv(csv, "B", "Chk")["imported"] == 2
    assert ledger.import_csv(csv, "B", "Chk")["duplicates"] == 2  # importing the file again adds nothing


@pytest.mark.parametrize("text,value", [("$-5.00", -5.0), ("(5.00)", -5.0), ("5.00 DR", -5.0),
                                        ("1,234.56", 1234.56), ("1.234.56", None)])
def test_csv_amounts(text, value):
    assert ledger._parse_amount(text) == value


def test_cors_is_off_unless_origins_are_listed(temp_db, monkeypatch):  # noqa: F811
    monkeypatch.delenv("BUDGET_CORS_ORIGINS", raising=False)
    from api_server import create_app
    r = create_app().test_client().options("/graphql", headers={"Origin": "https://evil.example",
                                                                "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_nan_setting_is_refused(api):  # noqa: F811
    out = api('mutation { updateSettings(changes: "{\\"overdraft_fee\\": \\"nan\\"}") { success } }')
    assert out["updateSettings"]["success"] is False
