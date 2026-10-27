"""
Tests for the GraphQL API used by the web UI.

Runs queries/mutations against an in-memory FinanceManager backed by a
throwaway database (see the temp_db fixture).
"""

import json
import pytest

from models.finance_manager import FinanceManager
from models.graphql_schema import schema
from tests.test_persistence import temp_db  # noqa: F401  (fixture)


@pytest.fixture
def api(temp_db):  # noqa: F811
    manager = FinanceManager([], [], [])
    manager.load_from_database()

    def run(query, **variables):
        result = schema.execute(query, variable_values=variables, context_value={'manager': manager})
        assert not result.errors, result.errors
        return result.data

    run('mutation { createBank(name: "B") { success } }')
    run('mutation { createAccount(bankName: "B", accountName: "Chk", accountType: "checking", balance: 3000) { success } }')
    run.manager = manager
    return run


def _bank(api):
    return api.manager.banks[0]


class TestAccounts:

    def test_credit_card_created_with_balance_and_due_days(self, api):
        data = api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
                   'balance: 1500, interestRate: 20, creditLimit: 5000, paymentDueDate: 12, statementDate: 5) '
                   '{ success message } }')
        assert data['createAccount']['success'], data
        card = _bank(api).credit_accounts["Visa"]
        assert (card.balance, card.regular_balance, card.payment_due_date, card.statement_date) == (1500, 1500, 12, 5)
        # Its payment bill shows up immediately, due on the card's due day
        bills = api('{ allBills { billName dueDate } }')['allBills']
        assert {'billName': '[Auto] Visa Payment', 'dueDate': 12} in bills

    def test_credit_card_requires_limit(self, api):
        data = api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit") { success } }')
        assert not data['createAccount']['success']

    def test_create_returns_plain_values(self, api):
        data = api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) '
                   '{ bill { billType frequency nextDueDate } } }')
        bill = data['createBill']['bill']
        assert bill['billType'] == 'fixed' and bill['frequency'] == 'monthly' and bill['nextDueDate']


class TestBills:

    def test_floating_bill_with_preferred_source(self, api):
        data = api('mutation { createBill(billName: "Power", amount: 120, dueDate: 20, billType: "floating", '
                   'minAmount: 80, maxAmount: 200, preferredSourceBank: "B", preferredSourceAccount: "Chk") '
                   '{ success bill { billType minAmount maxAmount preferredSourceAccount } } }')
        bill = data['createBill']['bill']
        assert bill == {'billType': 'floating', 'minAmount': 80, 'maxAmount': 200, 'preferredSourceAccount': 'Chk'}

    def test_duplicate_bill_rejected(self, api):
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) { success } }')
        data = api('mutation { createBill(billName: "Rent", amount: 900, dueDate: 5) { success } }')
        assert not data['createBill']['success']

    def test_empty_string_clears_preferred_source(self, api):
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5, '
            'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
        api('mutation { updateBill(billName: "Rent", preferredSourceBank: "", preferredSourceAccount: "") { success } }')
        rent = next(b for b in api.manager.bills if b.bill_name == "Rent")
        assert rent.preferred_source_bank is None and rent.preferred_source_account is None

    def test_mark_paid_withdraws_and_records(self, api):
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) { success } }')
        data = api('mutation { markBillPaid(billName: "Rent", sourceBank: "B", sourceAccount: "Chk", '
                   'paymentDate: "2026-01-05") { success } }')
        assert data['markBillPaid']['success']
        assert _bank(api).accounts["Chk"].balance == 2000
        history = api('{ billPaymentHistory { billName amountPaid paymentDate } }')['billPaymentHistory']
        assert history == [{'billName': 'Rent', 'amountPaid': 1000.0, 'paymentDate': '2026-01-05'}]

    def test_mark_paid_from_credit_card_charges_card(self, api):
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", creditLimit: 5000) { success } }')
        api('mutation { createBill(billName: "Gym", amount: 50, dueDate: 5) { success } }')
        api('mutation { markBillPaid(billName: "Gym", sourceBank: "B", sourceAccount: "Visa") { success } }')
        assert _bank(api).credit_accounts["Visa"].balance == 50
        assert _bank(api).accounts["Chk"].balance == 3000

    def test_bad_date_is_a_friendly_error(self, api):
        api('mutation { createBill(billName: "Rent", amount: 1000, dueDate: 5) { success } }')
        data = api('mutation { markBillPaid(billName: "Rent", paymentDate: "10/26/2026") { success message } }')
        assert not data['markBillPaid']['success']
        assert 'YYYY-MM-DD' in data['markBillPaid']['message']


class TestCreditPayments:

    def test_failed_payment_does_not_lose_cash(self, api):
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
            'balance: 100, creditLimit: 5000) { success } }')
        data = api('mutation { markCreditPaymentPaid(bankName: "B", accountName: "Visa", amountPaid: 500, '
                   'sourceBank: "B", sourceAccount: "Chk") { success } }')
        assert not data['markCreditPaymentPaid']['success']
        assert _bank(api).accounts["Chk"].balance == 3000
        assert _bank(api).credit_accounts["Visa"].balance == 100

    def test_payment_moves_money_and_marks_paid(self, api):
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", '
            'balance: 1000, creditLimit: 5000) { success } }')
        api('mutation { markCreditPaymentPaid(bankName: "B", accountName: "Visa", amountPaid: 200, '
            'sourceBank: "B", sourceAccount: "Chk") { success } }')
        assert _bank(api).accounts["Chk"].balance == 2800
        assert _bank(api).credit_accounts["Visa"].balance == 800
        due = api('{ creditPaymentsDue { isPaidThisPeriod lastPaymentAmount } }')['creditPaymentsDue']
        assert due == [{'isPaidThisPeriod': True, 'lastPaymentAmount': 200.0}]


class TestBillGroups:

    def test_group_payment_moves_money(self, api):
        api('mutation { createAccount(bankName: "B", accountName: "Loan", accountType: "credit", '
            'balance: 4000, creditLimit: 10000) { success } }')
        api('mutation { createBillGroup(groupName: "SL", totalPayment: 200, dueDate: 5, '
            'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
        api('mutation { addBillGroupMember(groupName: "SL", bankName: "B", accountName: "Loan") { success } }')
        data = api('mutation { markBillGroupPaid(groupName: "SL") { success billGroup { isPaidThisPeriod } } }')
        assert data['markBillGroupPaid']['billGroup']['isPaidThisPeriod']
        assert _bank(api).accounts["Chk"].balance == 2800
        assert _bank(api).credit_accounts["Loan"].balance == 3800

    def test_member_must_exist(self, api):
        api('mutation { createBillGroup(groupName: "SL", totalPayment: 200, dueDate: 5) { success } }')
        data = api('mutation { addBillGroupMember(groupName: "SL", bankName: "B", accountName: "Nope") { success } }')
        assert not data['addBillGroupMember']['success']


class TestQueries:

    def test_balance_on_date(self, api):
        data = api('{ balanceOnDate(date: "2030-01-01") }')
        assert json.loads(data['balanceOnDate'])

    def test_projection_net_change_matches_cash(self, api):
        api('mutation { createIncomeSource(sourceName: "Job", amount: 2000, payDates: [1]) { success } }')
        p = api('{ projection(days: 60) { totalFinalBalance netChange } }')['projection']
        assert p['netChange'] == pytest.approx(p['totalFinalBalance'] - 3000)

    def test_what_if_snapshots_are_arrays(self, api):
        mods = json.dumps({"add_bills": [{"bill_name": "X", "amount": 100, "due_date": 15}]})
        data = api('query($m: JSONString!) { whatIfScenario(modifications: $m, days: 60) { baselineSnapshots } }', m=mods)
        assert isinstance(json.loads(data['whatIfScenario']['baselineSnapshots']), list)

    def test_snapshot_records_net_worth(self, api):
        api('{ snapshot { netWorth } }')
        history = api('{ netWorthHistory { netWorth } }')['netWorthHistory']
        assert history == [{'netWorth': 3000.0}]


class TestMortgages:

    CREATE = ('mutation { createMortgageAccount(bankName: "B", accountName: "Home", originalPrincipal: 300000, '
              'currentPrincipal: 250000, interestRate: 6, loanTermMonths: 360, paymentDueDate: 3, '
              'startDate: "2020-05-01", escrowPropertyTax: 300, escrowInsurance: 100, marketValue: 400000, '
              'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success message } }')

    def test_create_mortgage(self, api):
        data = api(self.CREATE)
        assert data['createMortgageAccount']['success'], data
        m = _bank(api).mortgage_accounts["Home"]
        assert (m.original_principal, m.current_principal, m.payment_due_date) == (300000, 250000, 3)
        assert m.escrow.total_monthly == 400
        assert m.market_value == 400000 and m.equity == 150000
        assert str(m.start_date) == "2020-05-01"
        # Standard 30-year payment on $300k at 6% is $1,798.65, plus $400 escrow
        assert m.total_monthly_payment == pytest.approx(2198.65)
        # Its payment bill appears immediately, due on the 3rd, paid from Chk
        bills = api('{ allBills { billName dueDate amount preferredSourceAccount } }')['allBills']
        assert {'billName': '[Auto] Home Payment', 'dueDate': 3, 'amount': pytest.approx(2198.65),
                'preferredSourceAccount': 'Chk'} in bills

    def test_mortgage_survives_reload(self, api):
        api(self.CREATE)
        api('mutation { loadDatabase { success } }')
        m = _bank(api).mortgage_accounts["Home"]
        assert (m.current_principal, m.market_value, str(m.start_date)) == (250000, 400000, "2020-05-01")

    def test_create_mortgage_validation(self, api):
        bad = [
            'originalPrincipal: 0',
            'originalPrincipal: 100000, currentPrincipal: 200000',
            'originalPrincipal: 100000, escrowHoa: -5',
            'originalPrincipal: 100000, preferredSourceBank: "B"',
            'originalPrincipal: 100000, startDate: "05/01/2020"',
        ]
        for args in bad:
            data = api(f'mutation {{ createMortgageAccount(bankName: "B", accountName: "M", {args}) {{ success }} }}')
            assert not data['createMortgageAccount']['success'], args
        api(self.CREATE)
        data = api(self.CREATE)
        assert not data['createMortgageAccount']['success']  # duplicate name
