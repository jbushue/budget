"""A card's minimum payment: the issuer's formula, matched from a statement."""

import pytest

from models.bank import Bank
from models.finance_manager import FinanceManager
from models.min_payment import DEFAULT_RULE, amount, describe, match
from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)
from tests.test_tools import ok, run


class TestFormulas:

    def test_default_pays_down_a_high_apr_card(self):
        # 2% of $4,680 ($93.60) is less than a month's interest at 29.99%;
        # the default (1% + interest) always takes a bite out of the balance
        interest = 4680 * 29.99 / 1200
        assert amount(None, 4680, interest) == pytest.approx(46.80 + interest, abs=0.01)
        assert amount(None, 4680, interest) > interest

    def test_floor_and_balance_cap(self):
        rule = {"pct": 2, "floor": 35}
        assert amount(rule, 1000) == 35
        assert amount(rule, 20) == 20  # never more than the balance
        assert amount({"fixed": 178.09}, 5000) == 178.09
        assert amount(rule, 0) == 0

    def test_describe(self):
        assert describe(DEFAULT_RULE) == "1% of the balance + interest, at least $25"
        assert describe({"pct": 3, "floor": 0}) == "3% of the balance"
        assert describe({"fixed": 75}) == "Fixed $75 a month"


class TestMatching:

    def test_finds_the_formula(self):
        found = match(140.0, 4000, 0)
        assert found["best"] == {"pct": 3.5, "interest": False, "floor": 25.0} and not found["ambiguous"]

    def test_one_percent_plus_interest(self):
        found = match(round(52.0 + 81.25, 2), 5200, 81.25)
        assert found["best"]["pct"] == 1 and found["best"]["interest"]

    def test_whole_dollar_rounding(self):
        assert match(141.0, 4020, 0)["best"]["pct"] == 3.5  # $140.70 printed as $141

    def test_small_balance_only_tells_the_floor(self):
        found = match(35.0, 600, 12)
        assert found["ambiguous"] and found["best"]["floor"] == 35
        assert "only the $35 minimum applies" in found["message"]

    def test_installment_is_a_fixed_amount(self):
        found = match(178.09, 8900, 200)
        assert found["best"] == {"fixed": 178.09}

    def test_bad_input(self):
        with pytest.raises(ValueError):
            match(0, 1000, 0)
        with pytest.raises(ValueError):
            match(2000, 1000, 0)


def test_card_uses_its_rule():
    bank = Bank("B")
    card = bank.add_credit_account("Card", 10000, 0.0, payment_due_date=10)
    card.balance = card.regular_balance = 4000.0
    card.min_rule = {"pct": 3.5, "interest": False, "floor": 25}
    assert card.calculate_minimum_payment() == 140.0
    card.min_rule = {"fixed": 75}
    assert card.calculate_minimum_payment() == 75.0


def test_rule_is_saved_and_loaded(temp_db):  # noqa: F811
    bank = Bank("B")
    bank.add_account("checking", "Chk", 1000)
    card = bank.add_credit_account("Card", 10000, 20.0, payment_due_date=10)
    card.balance = card.regular_balance = 4000.0
    card.min_rule = {"pct": 2, "interest": True, "floor": 35}
    m = FinanceManager([bank], [], [])
    assert m.save_to_database()
    loaded = FinanceManager([], [], [])
    assert loaded.load_from_database()
    assert loaded.banks[0].credit_accounts["Card"].min_rule == {"pct": 2.0, "interest": True, "floor": 35.0}


def test_match_and_set_through_the_api(client):  # noqa: F811
    ok(client, 'mutation { createBank(name: "Chase") { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Chase", accountName: "Freedom", accountType: "credit", '
               'balance: 4000, interestRate: 0, creditLimit: 9000, paymentDueDate: 15) { success message } }')
    data = run(client, '{ minimumPaymentMatch(bankName: "Chase", accountName: "Freedom", minimumPayment: 140) '
                       '{ best bestLabel ambiguous message currentRuleLabel matches { label amount } } }')
    found = data["minimumPaymentMatch"]
    assert found["bestLabel"] == "3.5% of the balance, at least $25"
    assert found["currentRuleLabel"].endswith("(default)")
    ok(client, 'mutation($r: JSONString) { setMinimumPaymentRule(bankName: "Chase", accountName: "Freedom", rule: $r) '
               '{ success message } }', {"r": found["best"]})
    banks = run(client, '{ allBanks { creditAccounts { accountName minimumPayment minRuleLabel } } }')["allBanks"]
    card = banks[0]["creditAccounts"][0]
    assert card["minimumPayment"] == 140.0 and card["minRuleLabel"] == "3.5% of the balance, at least $25"
    # Back to the default
    ok(client, 'mutation { setMinimumPaymentRule(bankName: "Chase", accountName: "Freedom") { success message } }')
    card = run(client, '{ allBanks { creditAccounts { minimumPayment minRuleLabel } } }')["allBanks"][0]["creditAccounts"][0]
    assert card["minRuleLabel"].endswith("(default)") and card["minimumPayment"] == 40.0
