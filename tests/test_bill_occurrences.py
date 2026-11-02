"""Paid status per due date: paying ahead, partial payments, skips, overdue, the month view."""

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from models import occurrences as occ
from models.bank import Bank
from models.date_utils import add_months
from models.finance_manager import FinanceManager
from models.fixed_bill import Bill, FloatingBill
from models.timeline_simulator import TimelineSimulator
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()
DAY = min((TODAY + timedelta(days=5)).day, 28)


def reload():
    m = FinanceManager([], [], [])
    assert m.load_from_database()
    return m


def bill_of(m, name):
    return next(b for b in m.bills if b.bill_name == name)


def dues(bill, n=3):
    return occ.due_dates(bill, TODAY, TODAY + timedelta(days=31 * n + 5))[:n]


def payments(result, name):
    return [cf["date"] for cf in result["cash_flow"] if cf["type"] == "BILL_PAYMENT" and cf["description"] == name]


def project(bills, days=100, checking=10000.0):
    bank = Bank("B")
    bank.add_account("checking", "Chk", checking)
    return TimelineSimulator([bank], [], bills).project_balances(TODAY, TODAY + timedelta(days=days))


def test_paying_next_month_ahead_skips_only_that_month():
    rent = Bill("Rent", 1000.0, DAY)
    first, second, third = dues(rent)
    rent.mark_paid("B", "Chk", 1000.0, TODAY, due=second)
    paid = payments(project([rent]), "Rent")
    assert first in paid and second not in paid and third in paid


def test_two_months_paid_ahead_are_both_left_out():
    rent = Bill("Rent", 1000.0, DAY)
    first, second, third = dues(rent)
    for d in (first, second):
        rent.mark_paid("B", "Chk", 1000.0, TODAY, due=d)
    assert payments(project([rent], days=70), "Rent") == [third]
    assert rent.is_paid_this_period


def test_partial_payment_leaves_the_rest_owed():
    rent = Bill("Rent", 1000.0, DAY)
    first = dues(rent)[0]
    rent.mark_paid("B", "Chk", 400.0, TODAY, due=first)
    assert occ.status(rent, first) == "partial" and occ.remaining(rent, first) == 600
    r = project([rent], days=20)
    assert [cf["amount"] for cf in r["cash_flow"] if cf["type"] == "BILL_PAYMENT"] == [-600.0]


def test_overdue_bill_is_paid_on_day_one_of_the_projection():
    past = TODAY - timedelta(days=3)
    phone = Bill("Phone", 80.0, min(past.day, 28))
    phone.created_on = TODAY - timedelta(days=20)
    late = occ.overdue(phone)
    assert late and late[0][1] == 80.0
    r = project([phone], days=5)
    first_day = [cf for cf in r["cash_flow"] if cf["date"] == TODAY and cf["type"] == "BILL_PAYMENT"]
    assert first_day and first_day[0]["overdue"] and first_day[0]["due"] == late[0][0]
    assert r["final_balances"]["B:Chk"] == pytest.approx(10000 - 80 * len(late))


def test_skipped_due_date_is_not_owed():
    phone = Bill("Phone", 80.0, DAY)
    first = dues(phone)[0]
    phone.skipped = {first}
    assert first not in payments(project([phone], days=20), "Phone")
    assert occ.status(phone, first) == "skipped"


def test_floating_actual_amount_is_for_one_due_date_only():
    power = FloatingBill("Power", 100.0, DAY)
    first, second, _ = dues(power)
    power.set_actual_amount(140.0, first)
    amounts = {cf["date"]: -cf["amount"] for cf in project([power], days=70)["cash_flow"]
               if cf["type"] == "BILL_PAYMENT"}
    assert amounts[first] == 140.0 and amounts[second] == 100.0


def test_weekly_bill_due_dates_are_paid_separately(api):  # noqa: F811
    api('mutation { createBill(billName: "Lessons", amount: 30, dueDate: 1, frequency: "weekly") { success } }')
    lessons = bill_of(api.manager, "Lessons")
    first, second = dues(lessons, 2)
    out = api(f'mutation {{ markBillPaid(billName: "Lessons", dueDate: "{second}", moveMoney: false) '
              '{ success message } }')["markBillPaid"]
    assert out["success"], out
    assert occ.status(lessons, second) == "paid" and occ.status(lessons, first) == "unpaid"
    # Due dates stay put across a reload (the weekly cycle is saved)
    again = bill_of(reload(), "Lessons")
    assert dues(again, 2) == [first, second] and occ.status(again, second) == "paid"


def test_group_payments_survive_a_reload(api):  # noqa: F811
    api('mutation { createAccount(bankName: "B", accountName: "Loan", accountType: "credit", balance: 5000, '
        'interestRate: 5, creditLimit: 9000) { success } }')
    api(f'mutation {{ createBillGroup(groupName: "Loans", totalPayment: 200, dueDate: {DAY}, '
        'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
    api('mutation { addBillGroupMember(groupName: "Loans", bankName: "B", accountName: "Loan") { success } }')
    group_bill = bill_of(api.manager, "[Auto] Loans Payment")
    second = dues(group_bill, 2)[1]
    out = api(f'mutation {{ markBillGroupPaid(groupName: "Loans", dueDate: "{second}") {{ success message }} }}')
    assert out["markBillGroupPaid"]["success"], out
    loaded = bill_of(reload(), "[Auto] Loans Payment")
    assert occ.status(loaded, second) == "paid" and occ.paid_amount(loaded, second) == 200


def test_old_payments_get_due_dates_when_loaded(api):  # noqa: F811
    """Payments saved before due dates were kept are assigned one (a late one pays the missed month)."""
    api(f'mutation {{ createBill(billName: "Gym", amount: 40, dueDate: {DAY}) {{ success }} }}')
    gym = bill_of(api.manager, "Gym")
    gym.created_on = TODAY - timedelta(days=120)
    y, m = add_months(TODAY.year, TODAY.month, -2)
    missed = date(y, m, DAY)
    y, m = add_months(TODAY.year, TODAY.month, -1)
    on_time = date(y, m, DAY) - timedelta(days=2)
    from models import database as db
    with db.engine.begin() as conn:
        bill_id = conn.execute(text("SELECT id FROM bills WHERE bill_name='Gym'")).scalar()
        conn.execute(text("UPDATE bills SET created_at=:c WHERE id=:i"),
                     {"c": f"{TODAY - timedelta(days=120)} 12:00:00", "i": bill_id})
        for paid_on in (missed + timedelta(days=6), on_time):
            conn.execute(text("INSERT INTO bill_payments (bill_id, amount_paid, source_bank, source_account, "
                              "payment_date) VALUES (:b, 40, '', '', :d)"), {"b": bill_id, "d": paid_on.isoformat()})
    loaded = bill_of(reload(), "Gym")
    assert sorted(occ.due_of(e) for e in loaded.payment_history) == [missed, date(on_time.year, on_time.month, DAY)]


def test_undo_puts_the_money_back(api):  # noqa: F811
    api(f'mutation {{ createBill(billName: "Water", amount: 50, dueDate: {DAY}, preferredSourceBank: "B", '
        'preferredSourceAccount: "Chk") { success } }')
    api('mutation { markBillPaid(billName: "Water") { success } }')
    chk = api.manager.banks[0].accounts["Chk"]
    assert chk.balance == pytest.approx(2950)
    due = dues(bill_of(api.manager, "Water"), 1)[0]
    out = api(f'mutation {{ undoBillPayment(billName: "Water", dueDate: "{due}") {{ success message }} }}')
    assert out["undoBillPayment"]["success"], out
    assert chk.balance == pytest.approx(3000)
    assert occ.status(bill_of(reload(), "Water"), due) == "unpaid"


def test_undo_a_card_payment_owes_it_again(api):  # noqa: F811
    api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 1000, '
        f'interestRate: 20, creditLimit: 5000, paymentDueDate: {DAY}) {{ success }} }}')
    api('mutation { markBillPaid(billName: "[Auto] Visa Payment", amountPaid: 100, sourceBank: "B", '
        'sourceAccount: "Chk") { success } }')
    card = api.manager.banks[0].credit_accounts["Visa"]
    assert card.balance == pytest.approx(900)
    api('mutation { undoBillPayment(billName: "[Auto] Visa Payment") { success } }')
    assert card.balance == pytest.approx(1000)
    assert api.manager.banks[0].accounts["Chk"].balance == pytest.approx(3000)


def test_month_view(api):  # noqa: F811
    api(f'mutation {{ createBill(billName: "Rent", amount: 1000, dueDate: {DAY}) {{ success }} }}')
    api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 1000, '
        f'interestRate: 20, creditLimit: 5000, paymentDueDate: {DAY}) {{ success }} }}')
    rent = bill_of(api.manager, "Rent")
    nxt = dues(rent, 2)[1]
    month = f"{nxt.year:04d}-{nxt.month:02d}"
    api(f'mutation {{ markBillPaid(billName: "Rent", dueDate: "{nxt}", amountPaid: 250, moveMoney: false) '
        '{ success } }')
    q = f'{{ billMonth(month: "{month}") {{ month occurrences {{ billName kind dueDate amount paid remaining status }} ' \
        'totals { due paid remaining } } }'
    data = api(q)["billMonth"]
    rows = {r["billName"]: r for r in data["occurrences"]}
    assert data["month"] == month
    assert rows["Rent"]["status"] == "partial" and rows["Rent"]["remaining"] == 750
    assert rows["[Auto] Visa Payment"]["kind"] == "credit"
    assert data["totals"]["paid"] == 250


def test_skip_mutation(api):  # noqa: F811
    api(f'mutation {{ createBill(billName: "Gym", amount: 40, dueDate: {DAY}) {{ success }} }}')
    due = dues(bill_of(api.manager, "Gym"), 1)[0]
    api(f'mutation {{ skipBillOccurrence(billName: "Gym", dueDate: "{due}") {{ success }} }}')
    assert occ.status(bill_of(reload(), "Gym"), due) == "skipped"
    api(f'mutation {{ skipBillOccurrence(billName: "Gym", dueDate: "{due}", skip: false) {{ success }} }}')
    assert occ.status(bill_of(api.manager, "Gym"), due) == "unpaid"


def test_paying_too_far_ahead_is_refused(api):  # noqa: F811
    api(f'mutation {{ createBill(billName: "Gym", amount: 40, dueDate: {DAY}) {{ success }} }}')
    far = TODAY + timedelta(days=400)
    out = api(f'mutation {{ markBillPaid(billName: "Gym", dueDate: "{far}") {{ success message }} }}')
    assert out["markBillPaid"]["success"] is False
