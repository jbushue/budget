import pytest
"""
Editing accounts and banks after they're created: every setting, renames
and moves, and that everything referring to an account by name follows it
(and survives a reload from the database).
"""

from sqlalchemy import text

from models import database as db
from models import app_settings, simplefin
from models.finance_manager import FinanceManager
from models.fixed_bill import AccountLinkedBill
from tests.test_graphql_api import api  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)


def reload():
    m = FinanceManager([], [], [])
    assert m.load_from_database()
    return m


def edit(api, **args):  # noqa: F811
    parts = []
    for k, v in args.items():
        parts.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    return api("mutation { updateAccount(%s) { success message name } }" % ", ".join(parts))["updateAccount"]


def rows(sql, **params):
    s = db.get_session()
    try:
        return s.execute(text(sql), params).fetchall()
    finally:
        s.close()


class TestBankAccounts:

    def test_rename_checking_carries_every_reference(self, api):  # noqa: F811
        api('mutation { createBill(billName: "Rent", amount: 1200, dueDate: 3, '
            'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
        api('mutation { createIncomeSource(sourceName: "Job", amount: 2500, frequency: "monthly", payDates: [1], '
            'distribution: "{\\"Chk\\": null}") { success } }')
        api('mutation { markBillPaid(billName: "Rent") { success } }')
        api('mutation { recordBalanceUpdate(bankName: "B", accountName: "Chk", newBalance: 1800) { success } }')
        api('mutation { addLedgerTransaction(date: "2026-01-05", description: "Coffee", amount: -4, '
            'bankName: "B", accountName: "Chk") { success } }')
        api('mutation { updateSettings(changes: "{\\"spending_account\\": \\"B:Chk\\"}") { success } }')
        simplefin.save_simplefin_mapping("sf-1", "Everyday", "Bank Co", "B", "Chk", "checking")

        out = edit(api, bankName="B", accountName="Chk", accountType="checking", newName="Everyday",
                   interestRate=0.5, interestAccrualDate=15)
        assert out == {"success": True, "message": "Saved Everyday", "name": "Everyday"}

        for m in (api.manager, reload()):
            acc = m.banks[0].accounts["Everyday"]
            assert "Chk" not in m.banks[0].accounts
            assert (acc.balance, acc.interest_rate, acc.interest_accrual_date) == (1800.0, 0.5, 15)
            rent = next(b for b in m.bills if b.bill_name == "Rent")
            assert (rent.preferred_source_bank, rent.preferred_source_account) == ("B", "Everyday")
            assert rent.is_paid_this_period and rent.payment_history
            assert list(m.income_sources[0].distribution.keys()) == ["Everyday"]
        assert rows("SELECT source_account FROM bill_payments")[0][0] == "Everyday"
        assert rows("SELECT account_name FROM balance_history")[0][0] == "Everyday"
        assert rows("SELECT account_name FROM ledger_transactions")[0][0] == "Everyday"
        assert rows("SELECT local_account_name FROM simplefin_account_mappings")[0][0] == "Everyday"
        assert app_settings.get_settings()["spending_account"] == "B:Everyday"

    def test_type_change_and_validation(self, api):  # noqa: F811
        assert edit(api, bankName="B", accountName="Chk", accountType="checking", newAccountType="savings",
                    interestRate=4)["success"]
        assert reload().banks[0].accounts["Chk"].account_type.value == "savings"
        bad = edit(api, bankName="B", accountName="Chk", accountType="savings", interestAccrualDate=40)
        assert not bad["success"] and "between 1 and 31" in bad["message"]
        bad = edit(api, bankName="B", accountName="Chk", accountType="savings", newAccountType="credit")
        assert not bad["success"]
        assert edit(api, bankName="B", accountName="Chk", accountType="savings", interestAccrualDate=0)["success"]
        assert reload().banks[0].accounts["Chk"].interest_accrual_date is None

    def test_name_collisions_change_nothing(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Sav", accountType: "savings", balance: 5) '
            '{ success } }')
        bad = edit(api, bankName="B", accountName="Chk", accountType="checking", newName="Sav", balance=1)
        assert not bad["success"] and "already has" in bad["message"]
        assert api.manager.banks[0].accounts["Chk"].balance == 3000  # untouched
        assert not edit(api, bankName="B", accountName="Chk", accountType="checking", newName="  ")["success"]
        assert not edit(api, bankName="B", accountName="Nope", accountType="checking", balance=1)["success"]


class TestCards:

    def _card(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 1500, '
            'interestRate: 20, creditLimit: 5000, paymentDueDate: 12, statementDate: 5) { success } }')
        api('mutation { addPromoOffer(bankName: "B", accountName: "Visa", promoName: "0% BT", monthsInterestFree: 12, '
            'promoBalance: 500) { success } }')
        api('mutation { updateBill(billName: "[Auto] Visa Payment", preferredSourceBank: "B", '
            'preferredSourceAccount: "Chk") { success } }')
        api('mutation { markBillPaid(billName: "[Auto] Visa Payment", amountPaid: 50) { success } }')

    def test_edit_all_card_settings(self, api):  # noqa: F811
        self._card(api)
        out = edit(api, bankName="B", accountName="Visa", accountType="credit", newName="Sapphire",
                   creditLimit=9000, interestRate=24.99, paymentDueDate=20, statementDate=14, balance=2000,
                   status="frozen")
        assert out["success"], out
        for m in (api.manager, reload()):
            card = m.banks[0].credit_accounts["Sapphire"]
            assert (card.credit_limit, card.interest_rate, card.payment_due_date, card.statement_date) == \
                   (9000, 24.99, 20, 14)
            assert card.status.value == "frozen"
            # The $50 payment gave the promo its share first ($500 over 12 payments)
            assert card.balance == 2000 and card.promo_balance == {"0% BT": 458.33}
            assert card.regular_balance == pytest.approx(1541.67)
            bills = [b for b in m.bills if isinstance(b, AccountLinkedBill)]
            assert [b.bill_name for b in bills] == ["[Auto] Sapphire Payment"]
            # The payment bill kept its own settings, history and paid flag, and follows the new due day
            assert bills[0].preferred_source_account == "Chk" and bills[0].payment_history
            assert bills[0].is_paid_this_period and bills[0].due_date == 20
        assert rows("SELECT COUNT(*) FROM bills")[0][0] == 1

    def test_balance_cant_drop_below_promos(self, api):  # noqa: F811
        self._card(api)
        bad = edit(api, bankName="B", accountName="Visa", accountType="credit", balance=100)
        assert not bad["success"] and "promo" in bad["message"]

    def test_edit_promo(self, api):  # noqa: F811
        self._card(api)
        r = api('mutation { updatePromoOffer(bankName: "B", accountName: "Visa", promoName: "0% BT", '
                'newName: "Balance transfer", monthsInterestFree: 18, purchaseLimit: 3000, startDate: "2026-01-01", '
                'promoBalance: 700) { success message } }')["updatePromoOffer"]
        assert r["success"], r
        card = reload().banks[0].credit_accounts["Visa"]
        promo = card.active_promos[0]
        assert (promo.promo_name, promo.months_interest_free, promo.purchase_limit) == ("Balance transfer", 18, 3000)
        assert promo.start_date.isoformat() == "2026-01-01" and promo.end_date.isoformat() == "2027-06-25"
        assert card.promo_balance == {"Balance transfer": 700}
        bad = api('mutation { updatePromoOffer(bankName: "B", accountName: "Visa", promoName: "Balance transfer", '
                  'startDate: "2026-05-01", endDate: "2026-04-01") { success message } }')["updatePromoOffer"]
        assert not bad["success"] and reload().banks[0].credit_accounts["Visa"].active_promos[0].end_date.year == 2027

    def test_card_in_group_and_matched_transactions(self, api):  # noqa: F811
        self._card(api)
        api('mutation { createBillGroup(groupName: "Cards", totalPayment: 100, dueDate: 12) { success } }')
        api('mutation { addBillGroupMember(groupName: "Cards", bankName: "B", accountName: "Visa") { success } }')
        s = db.get_session()
        s.execute(text("INSERT INTO ledger_transactions (txn_date, description, amount, source, matched_bill) "
                       "VALUES ('2026-01-01', 'Visa pay', -50, 'manual', '[Auto] Visa Payment')"))
        s.commit()
        s.close()
        assert edit(api, bankName="B", accountName="Visa", accountType="credit", newName="Amex")["success"]
        m = reload()
        assert [(x.bank_name, x.account_name) for x in m.bill_groups[0].members] == [("B", "Amex")]
        assert rows("SELECT matched_bill FROM ledger_transactions")[0][0] == "[Auto] Amex Payment"


class TestLoans:

    def test_mortgage_every_field_and_move_bank(self, api):  # noqa: F811
        api('mutation { createBank(name: "Lender") { success } }')
        api('mutation { createMortgageAccount(bankName: "B", accountName: "Home", originalPrincipal: 300000, '
            'currentPrincipal: 250000, interestRate: 6.5, loanTermMonths: 360, paymentDueDate: 1) { success } }')
        out = edit(api, bankName="B", accountName="Home", accountType="mortgage", newName="House",
                   newBankName="Lender", originalPrincipal=320000, currentPrincipal=240000, interestRate=5.75,
                   loanTermMonths=300, paymentDueDate=5, startDate="2020-06-01", escrowPropertyTax=300,
                   escrowInsurance=120, escrowPmi=0, escrowHoa=25, escrowOther=5, marketValue=450000,
                   preferredSourceBank="B", preferredSourceAccount="Chk")
        assert out["success"], out
        m = reload()
        assert "Home" not in m.banks[0].mortgage_accounts
        lender = next(b for b in m.banks if b.name == "Lender")
        home = lender.mortgage_accounts["House"]
        assert (home.original_principal, home.current_principal, home.interest_rate, home.loan_term_months,
                home.payment_due_date) == (320000, 240000, 5.75, 300, 5)
        assert home.start_date.isoformat() == "2020-06-01" and home.market_value == 450000
        assert home.escrow.total_monthly == 450
        bill = next(b for b in m.bills if isinstance(b, AccountLinkedBill))
        assert (bill.bill_name, bill.linked_bank_name, bill.due_date) == ("[Auto] House Payment", "Lender", 5)
        assert (bill.preferred_source_bank, bill.preferred_source_account) == ("B", "Chk")
        data = api('{ allBanks { name mortgageAccounts { accountName startDate escrowHoa marketValue } } }')
        lender_gql = next(b for b in data["allBanks"] if b["name"] == "Lender")
        assert lender_gql["mortgageAccounts"] == [
            {"accountName": "House", "startDate": "2020-06-01", "escrowHoa": 25.0, "marketValue": 450000.0}]
        bad = edit(api, bankName="Lender", accountName="House", accountType="mortgage", currentPrincipal=999999)
        assert not bad["success"]
        assert not edit(api, bankName="Lender", accountName="House", accountType="mortgage",
                        preferredSourceBank="B", preferredSourceAccount="Nope")["success"]

    def test_heloc(self, api):  # noqa: F811
        api('mutation { createHelocAccount(bankName: "B", accountName: "HE", creditLimit: 50000, interestRate: 8, '
            'currentBalance: 10000, paymentDueDate: 10) { success } }')
        assert edit(api, bankName="B", accountName="HE", accountType="heloc", creditLimit=60000, balance=12000,
                    interestRate=7.25, drawPeriodMonths=60, totalTermMonths=240, startDate="2024-03-01",
                    paymentDueDate=15, preferredSourceBank="B", preferredSourceAccount="Chk")["success"]
        he = reload().banks[0].heloc_accounts["HE"]
        assert (he.credit_limit, he.balance, he.interest_rate, he.draw_period_months, he.total_term_months,
                he.payment_due_date, he.preferred_source_account) == (60000, 12000, 7.25, 60, 240, 15, "Chk")
        bad = edit(api, bankName="B", accountName="HE", accountType="heloc", drawPeriodMonths=300)
        assert not bad["success"] and "longer" in bad["message"]
        assert reload().banks[0].heloc_accounts["HE"].draw_period_months == 60
        # Clearing the pay-from account
        assert edit(api, bankName="B", accountName="HE", accountType="heloc", preferredSourceBank="",
                    preferredSourceAccount="")["success"]
        assert reload().banks[0].heloc_accounts["HE"].preferred_source_bank is None


class TestBanks:

    def test_rename_bank_everything_follows(self, api):  # noqa: F811
        api('mutation { createAccount(bankName: "B", accountName: "Visa", accountType: "credit", balance: 100, '
            'creditLimit: 5000, paymentDueDate: 12) { success } }')
        api('mutation { createBill(billName: "Rent", amount: 1200, dueDate: 3, '
            'preferredSourceBank: "B", preferredSourceAccount: "Chk") { success } }')
        api('mutation { recordBalanceUpdate(bankName: "B", accountName: "Chk", newBalance: 2500) { success } }')
        r = api('mutation { updateBank(name: "B", newName: "Chase", bankType: "credit_issuer") '
                '{ success message name } }')["updateBank"]
        assert r == {"success": True, "message": "Saved Chase", "name": "Chase"}
        for m in (api.manager, reload()):
            assert [(b.name, b.bank_type) for b in m.banks] == [("Chase", "credit_issuer")]
            assert set(m.banks[0].accounts) == {"Chk"} and set(m.banks[0].credit_accounts) == {"Visa"}
            rent = next(b for b in m.bills if b.bill_name == "Rent")
            assert rent.preferred_source_bank == "Chase"
            card_bill = next(b for b in m.bills if isinstance(b, AccountLinkedBill))
            assert card_bill.linked_bank_name == "Chase"
        assert rows("SELECT bank_name FROM balance_history")[0][0] == "Chase"
        assert rows("SELECT COUNT(*) FROM bills")[0][0] == 2

    def test_bank_errors(self, api):  # noqa: F811
        api('mutation { createBank(name: "Other") { success } }')
        for args in ('newName: "Other"', 'newName: ""', 'bankType: "pirate"'):
            r = api('mutation { updateBank(name: "B", %s) { success message } }' % args)["updateBank"]
            assert not r["success"], args
        assert not api('mutation { updateBank(name: "Nope", newName: "X") { success } }')["updateBank"]["success"]
