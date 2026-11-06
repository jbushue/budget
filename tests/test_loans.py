"""
Loans besides mortgages: auto, student, personal and other. They share the
mortgage's amortization; what differs by kind is a vehicle value that
depreciates (auto), a deferment with interest added at repayment (student),
the lender's payment overriding the amortized one (any), loan groups, and
turning a card-style account into a loan.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import inspect, text

from models import assets, database as db
from models.account_edit import term_for_payment
from models.bank import Bank
from models.bill_group import BillGroup
from models.finance_manager import FinanceManager
from models.fixed_bill import AccountLinkedBill, GroupLinkedBill
from models.mortgage_account import MortgageAccount
from models.timeline_simulator import TimelineSimulator
from models.types import BillFrequency, BillType
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)

TODAY = date.today()


def reload():
    m = FinanceManager([], [], [])
    assert m.load_from_database()
    return m


def loan_payments(result, name):
    return [c for c in result["cash_flow"] if c["type"] == "MORTGAGE_PAYMENT" and c.get("mortgage_name") == name]


def simulate(bank, bills, days=95):
    return TimelineSimulator([bank], [], bills).project_balances(TODAY, TODAY + timedelta(days=days))


class TestAutoLoan:

    def test_amortized_payment_without_escrow(self):
        car = MortgageAccount("Car", 30000, 7.0, 60, loan_kind="auto")
        assert car.kind_label == "Auto loan" and not car.is_mortgage
        assert car.total_monthly_payment == pytest.approx(594.04, abs=0.01)
        assert car.escrow.total_monthly == 0 and car.remaining_months == 60

    def test_vehicle_value_depreciates(self):
        car = MortgageAccount("Car", 30000, 7.0, 60, loan_kind="auto", market_value=28000,
                              value_as_of=TODAY)
        assert car.depreciation_rate == 15.0
        assert car.value_on(TODAY) == 28000
        assert car.value_on(TODAY + timedelta(days=365)) == pytest.approx(28000 * 0.85, rel=1e-3)
        home = MortgageAccount("Home", 300000, 6.0, 360, market_value=400000, value_as_of=TODAY)
        assert home.value_on(TODAY + timedelta(days=3650)) == 400000  # homes don't depreciate

    def test_simulated_payments(self):
        b = Bank("B")
        b.add_account("checking", "Chk", 10000)
        car = b.add_mortgage_account("Car", 20000, 6.0, 48, payment_due_date=10, loan_kind="auto")
        bill = AccountLinkedBill(car, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)
        r = simulate(b, [bill])
        pays = loan_payments(r, "Car")
        assert len(pays) == 3 and all(p["amount"] == pytest.approx(-car.total_monthly_payment) for p in pays)
        assert pays[0]["loan_kind"] == "auto"
        assert r["mortgage_final_balances"]  # the balance falls as it's paid


class TestPaymentOverride:

    def test_lenders_payment_wins(self):
        loan = MortgageAccount("Plan", 6000, 0.0, 24, loan_kind="personal", payment_override=300)
        assert loan.total_monthly_payment == 300
        assert loan.remaining_months == 20  # 6000 / 300, not the 24-month term
        b = Bank("B")
        b.add_account("checking", "Chk", 5000)
        b.mortgage_accounts["Plan"] = loan
        r = simulate(b, [AccountLinkedBill(loan, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)], 62)
        assert all(p["amount"] == pytest.approx(-300) for p in loan_payments(r, "Plan"))


class TestStudentLoan:

    def _loan(self, **kw):
        return MortgageAccount("Fed", 10000, 6.0, 120, loan_kind="student", payment_due_date=15,
                               payments_start=TODAY + timedelta(days=60), **kw)

    def test_nothing_due_in_deferment_then_interest_capitalized(self):
        b = Bank("B")
        b.add_account("checking", "Chk", 20000)
        loan = self._loan()
        b.mortgage_accounts["Fed"] = loan
        assert loan.in_deferment()
        accrued = loan.deferred_interest()
        assert accrued == pytest.approx(10000 * 0.06 * 60 / 365, abs=0.01)
        r = simulate(b, [AccountLinkedBill(loan, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)], 120)
        pays = loan_payments(r, "Fed")
        assert pays and all(p["date"] >= loan.payments_start for p in pays)
        # The first payment came after ~60 days of interest were added to the principal
        assert loan.capitalized
        first = pays[0]
        assert first["principal"] == pytest.approx(
            loan.total_monthly_payment - (10000 + accrued) * 0.005, abs=1)

    def test_capitalized_once(self):
        loan = self._loan()
        loan.make_payment(payment_date=loan.payments_start)
        assert loan.capitalized
        after_first = loan.current_principal
        assert after_first > 10000 - loan.total_monthly_payment  # interest was added before paying
        loan.make_payment(payment_date=loan.payments_start + timedelta(days=31))
        assert loan.current_principal < after_first

    def test_subsidized_accrues_nothing(self):
        loan = self._loan(subsidized=True)
        assert loan.deferred_interest() == 0
        loan.make_payment(amount=100, payment_date=loan.payments_start)
        assert loan.current_principal == pytest.approx(10000 - (100 - 50))  # 100 minus a month's interest

    def test_linked_bill_is_zero_before_start(self):
        loan = self._loan()
        bill = AccountLinkedBill(loan, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)
        assert bill.amount_on(TODAY) == 0
        assert bill.amount_on(loan.payments_start) == loan.total_monthly_payment


class TestLoanGroups:

    def test_group_pays_card_and_loan_members(self):
        b = Bank("Servicer")
        b.add_account("checking", "Chk", 5000)
        card = b.add_credit_account("Card-style", 5000, 4.0)
        card.balance = card.regular_balance = 2000.0
        loan = b.add_mortgage_account("Real loan", 6000, 5.0, 120, loan_kind="student")
        group = BillGroup("Student loans", 300, due_date=TODAY.day if TODAY.day <= 28 else 1,
                          frequency=BillFrequency.MONTHLY)
        group.add_member("Servicer", "Card-style")
        group.add_member("Servicer", "Real loan")
        assert group.get_total_balance([b]) == pytest.approx(8000)
        paid = group.distribute_payment(300, [b], TODAY)
        assert {p["account_name"] for p in paid} == {"Card-style", "Real loan"}
        assert b.credit_accounts["Card-style"].balance < 2000 and loan.current_principal < 6000

    def test_loan_in_group_has_no_bill_of_its_own(self, api):  # noqa: F811
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Fed", originalPrincipal: 8000, '
            'interestRate: 5, loanTermMonths: 120, loanKind: "student") { success } }')
        api('mutation { createBillGroup(groupName: "Loans", totalPayment: 200, dueDate: 12) { success } }')
        out = api('mutation { addBillGroupMember(groupName: "Loans", bankName: "B", accountName: "Fed") '
                  '{ success message } }')["addBillGroupMember"]
        assert out["success"], out
        for m in (api.manager, reload()):
            m.refresh()
            linked = [x for x in m.bills if isinstance(x, AccountLinkedBill)]
            assert not linked
            assert any(isinstance(x, GroupLinkedBill) for x in m.bills)
            assert m.bill_groups[0].get_total_balance(m.banks) == 8000


class TestConvert:

    def test_term_keeps_the_payment(self):
        n = term_for_payment(10000, 6.0, 200)
        assert MortgageAccount("x", 10000, 6.0, n).total_monthly_payment == pytest.approx(200, abs=3)
        assert term_for_payment(1200, 0, 100) == 12

    def test_card_style_loan_becomes_a_loan(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Nelnet", accountType: "credit", '
            'balance: 9000, interestRate: 5.5, creditLimit: 20000, paymentDueDate: 20) { success } }')
        api('mutation { createAccount(bankName: "B", accountName: "Other", accountType: "credit", '
            'balance: 1000, interestRate: 5.5, creditLimit: 20000, paymentDueDate: 20) { success } }')
        api('mutation { createBillGroup(groupName: "Loans", totalPayment: 250, dueDate: 20) { success } }')
        for n in ("Nelnet", "Other"):
            api('mutation { addBillGroupMember(groupName: "Loans", bankName: "B", accountName: "%s") '
                '{ success } }' % n)
        api('mutation { recordBalanceUpdate(bankName: "B", accountName: "Nelnet", newBalance: 9000, '
            'accountType: "credit") { success } }')
        minimum = api.manager.banks[0].credit_accounts["Nelnet"].calculate_minimum_payment()

        out = api('mutation { convertCreditToLoan(bankName: "B", accountName: "Nelnet", loanKind: "student", '
                  'paymentsStart: "%s") { success message name } }'
                  % (TODAY + timedelta(days=40)).isoformat())["convertCreditToLoan"]
        assert out["success"], out
        assert "student loan" in out["message"]

        for m in (api.manager, reload()):
            bank = m.banks[0]
            assert "Nelnet" not in bank.credit_accounts
            loan = bank.mortgage_accounts["Nelnet"]
            assert (loan.kind, loan.current_principal, loan.interest_rate, loan.payment_due_date) == \
                ("student", 9000, 5.5, 20)
            assert loan.total_monthly_payment == pytest.approx(minimum, abs=3)
            assert loan.in_deferment()
            assert [x.account_name for x in m.bill_groups[0].members] == ["Nelnet", "Other"]
            assert m.bill_groups[0].get_total_balance(m.banks) == pytest.approx(10000)
        s = db.get_session()
        try:
            kinds = s.execute(text("SELECT account_type FROM balance_history WHERE account_name = 'Nelnet'")).scalars()
            assert set(kinds) <= {"mortgage"}
        finally:
            s.close()

    def test_convert_refuses_nothing_owed(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Paid", accountType: "credit", '
            'balance: 0, interestRate: 5, creditLimit: 1000) { success } }')
        out = api('mutation { convertCreditToLoan(bankName: "B", accountName: "Paid") { success message } }')
        assert not out["convertCreditToLoan"]["success"]


class TestPersistence:

    def test_round_trip(self, api):  # noqa: F811
        start = TODAY + timedelta(days=200)
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Fed", originalPrincipal: 20000, '
            'interestRate: 4.5, loanTermMonths: 120, loanKind: "student", subsidized: true, '
            'paymentsStart: "%s", paymentOverride: 210) { success message } }' % start.isoformat())
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Car", originalPrincipal: 25000, '
            'interestRate: 6.9, loanTermMonths: 60, loanKind: "auto", marketValue: 24000, '
            'depreciationRate: 12) { success message } }')
        bank = reload().banks[0]
        fed, car = bank.mortgage_accounts["Fed"], bank.mortgage_accounts["Car"]
        assert (fed.kind, fed.subsidized, fed.payments_start, fed.payment_override) == ("student", True, start, 210)
        assert (car.kind, car.market_value, car.depreciation_rate, car.value_as_of) == ("auto", 24000, 12, TODAY)

    def test_old_database_is_all_mortgages(self, temp_db):  # noqa: F811
        engine = temp_db
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE mortgage_accounts DROP COLUMN loan_kind"))
        assert "loan_kind" not in {c["name"] for c in inspect(engine).get_columns("mortgage_accounts")}
        db.init_db()
        assert "loan_kind" in {c["name"] for c in inspect(engine).get_columns("mortgage_accounts")}


class TestApi:

    def test_create_each_kind(self, api):  # noqa: F811
        for kind in ("auto", "student", "personal", "other", "mortgage"):
            out = api('mutation { createMortgageAccount(bankName: "B", accountName: "%s", originalPrincipal: 10000, '
                      'interestRate: 5, loanKind: "%s") { success message } }' % (kind, kind))
            assert out["createMortgageAccount"]["success"], out
        rows = api('{ allBanks { mortgageAccounts { accountName loanKind kindLabel loanTermMonths } } }')
        loans = {r["accountName"]: r for r in rows["allBanks"][0]["mortgageAccounts"]}
        assert loans["auto"]["kindLabel"] == "Auto loan" and loans["auto"]["loanTermMonths"] == 60
        assert loans["mortgage"]["kindLabel"] == "Mortgage" and loans["mortgage"]["loanTermMonths"] == 360

    def test_kind_rules(self, api):  # noqa: F811
        bad = api('mutation { createMortgageAccount(bankName: "B", accountName: "Car", originalPrincipal: 10000, '
                  'loanKind: "auto", escrowPropertyTax: 100) { success message } }')["createMortgageAccount"]
        assert not bad["success"] and "Escrow" in bad["message"]
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Car", originalPrincipal: 10000, '
            'interestRate: 5, loanKind: "auto") { success } }')
        bad = api('mutation { updateAccount(bankName: "B", accountName: "Car", accountType: "mortgage", '
                  'escrowInsurance: 50) { success message } }')["updateAccount"]
        assert not bad["success"] and "Escrow" in bad["message"]
        ok = api('mutation { updateAccount(bankName: "B", accountName: "Car", accountType: "mortgage", '
                 'loanKind: "personal", paymentOverride: 250) { success message } }')["updateAccount"]
        assert ok["success"], ok
        car = reload().banks[0].mortgage_accounts["Car"]
        assert (car.kind, car.total_monthly_payment) == ("personal", 250)


class TestNetWorth:

    def test_vehicle_value_and_debts_by_kind(self, api):  # noqa: F811
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Car", originalPrincipal: 20000, '
            'interestRate: 6, loanTermMonths: 60, loanKind: "auto", marketValue: 18000) { success } }')
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Fed", originalPrincipal: 5000, '
            'interestRate: 5, loanTermMonths: 120, loanKind: "student") { success } }')
        nw = assets.net_worth_breakdown(api.manager)
        assert {"kind": "Vehicle", "value": 18000} in nw["assets_by_kind"]
        debts = {d["kind"]: d["value"] for d in nw["debts"]}
        assert debts == {"Auto loans": 20000, "Student loans": 5000}
        on = assets.other_assets_on(api.manager)
        assert on(TODAY + timedelta(days=365)) == pytest.approx(18000 * 0.85, rel=1e-3)
        # An asset linked to the loan covers the vehicle: not counted twice
        assets.save_asset("Civic", "vehicle", 17500, linked_bank="B", linked_account="Car", manager=api.manager)
        nw = assets.net_worth_breakdown(api.manager)
        assert {"kind": "Vehicle", "value": 17500} in nw["assets_by_kind"] and not nw["homes"]


class TestImportExport:

    def test_loans_round_trip_through_excel(self, api, tmp_path):  # noqa: F811
        pytest.importorskip("openpyxl")
        from models.data_import_export import DataImportExport
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Car", originalPrincipal: 25000, '
            'interestRate: 6.9, loanTermMonths: 60, loanKind: "auto", marketValue: 24000, '
            'paymentOverride: 500) { success } }')
        path = tmp_path / "out.xlsx"
        DataImportExport(api.manager).export_current_data(str(path))
        fresh = FinanceManager([], [], [])
        DataImportExport(fresh).import_from_excel(str(path))
        car = next(b for b in fresh.banks if b.name == "B").mortgage_accounts["Car"]
        assert (car.kind, car.payment_override, car.market_value, car.depreciation_rate) == ("auto", 500, 24000, 15)
