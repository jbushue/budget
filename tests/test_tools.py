"""Tools that used to be CLI-only: transfers, promos, extra principal, the mortgage
calculator, balance check-ins, floating-bill reset, strategy comparison, reports,
the calendar file, database info, and percentage income splits."""

import json

import pytest

from tests.test_phase4 import client  # noqa: F401  (fixture)
from tests.test_persistence import temp_db  # noqa: F401  (fixture)


def run(client, query, variables=None):
    r = client.post("/graphql", json={"query": query, "variables": variables or {}})
    body = r.get_json()
    assert not body.get("errors"), body
    return body["data"]


def ok(client, query, variables=None):
    data = run(client, query, variables)
    payload = next(iter(data.values()))
    assert payload["success"], payload
    return payload


@pytest.fixture
def setup(client):  # noqa: F811
    ok(client, 'mutation { createBank(name: "Ally") { success message } }')
    ok(client, 'mutation { createBank(name: "Chase") { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Ally", accountName: "Checking", accountType: "checking", '
               'balance: 3000) { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Chase", accountName: "Savings", accountType: "savings", '
               'balance: 500, interestRate: 4.0) { success message } }')
    ok(client, 'mutation { createAccount(bankName: "Chase", accountName: "Freedom", accountType: "credit", '
               'balance: 0, interestRate: 24.0, creditLimit: 5000, paymentDueDate: 15) { success message } }')
    ok(client, 'mutation { addPromoOffer(bankName: "Chase", accountName: "Freedom", promoName: "Zero", '
               'monthsInterestFree: 12) { success message } }')
    ok(client, 'mutation { createMortgageAccount(bankName: "Ally", accountName: "Home", originalPrincipal: 300000, '
               'currentPrincipal: 250000, interestRate: 6.0, loanTermMonths: 360, paymentDueDate: 1) '
               '{ success message } }')
    return client


def balances(client):
    data = run(client, "{ allBanks { name bankAccounts { accountName balance } "
                       "creditAccounts { accountName balance } mortgageAccounts { accountName currentPrincipal } } }")
    out = {}
    for b in data["allBanks"]:
        for a in b["bankAccounts"]:
            out[a["accountName"]] = a["balance"]
        for a in b["creditAccounts"]:
            out[a["accountName"]] = a["balance"]
        for a in b["mortgageAccounts"]:
            out[a["accountName"]] = a["currentPrincipal"]
    return out


class TestMoneyMoves:
    def test_transfer_between_banks(self, setup):
        ok(setup, 'mutation { transferMoney(fromBank: "Ally", fromAccount: "Checking", toBank: "Chase", '
                  'toAccount: "Savings", amount: 700) { success message } }')
        b = balances(setup)
        assert b["Checking"] == 2300 and b["Savings"] == 1200

    def test_transfer_refuses_overdraft_and_same_account(self, setup):
        r = run(setup, 'mutation { transferMoney(fromBank: "Chase", fromAccount: "Savings", toBank: "Ally", '
                       'toAccount: "Checking", amount: 9999) { success message } }')["transferMoney"]
        assert not r["success"] and "only has" in r["message"]
        r = run(setup, 'mutation { transferMoney(fromBank: "Ally", fromAccount: "Checking", toBank: "Ally", '
                       'toAccount: "Checking", amount: 5) { success message } }')["transferMoney"]
        assert not r["success"]
        assert balances(setup)["Savings"] == 500

    def test_promo_purchase_then_payment(self, setup):
        ok(setup, 'mutation { recordPromoPurchase(bankName: "Chase", accountName: "Freedom", promoName: "Zero", '
                  'amount: 1200, description: "Couch") { success message } }')
        assert balances(setup)["Freedom"] == 1200
        r = ok(setup, 'mutation { payPromoBalance(bankName: "Chase", accountName: "Freedom", promoName: "Zero", '
                      'amount: 2000, sourceBank: "Ally", sourceAccount: "Checking") { success message } }')
        assert "paid off" in r["message"]
        b = balances(setup)
        assert b["Freedom"] == 0 and b["Checking"] == 1800  # capped at the promo balance

    def test_extra_principal_from_checking(self, setup):
        ok(setup, 'mutation { payExtraPrincipal(bankName: "Ally", accountName: "Home", amount: 1000, '
                  'sourceBank: "Ally", sourceAccount: "Checking") { success message } }')
        b = balances(setup)
        assert b["Home"] == 249000 and b["Checking"] == 2000

    def test_balance_check_in_skips_unchanged(self, setup):
        r = ok(setup, 'mutation($u: [BalanceInput!]!) { updateBalances(updates: $u) { success message } }', {"u": [
            {"bank": "Ally", "account": "Checking", "kind": "bank", "balance": 3100},
            {"bank": "Chase", "account": "Savings", "kind": "bank", "balance": 500},
            {"bank": "Chase", "account": "Freedom", "kind": "credit", "balance": 250},
        ]})
        assert r["message"] == "Updated 2 balances"
        b = balances(setup)
        assert b["Checking"] == 3100 and b["Freedom"] == 250


class TestCalculators:
    def test_mortgage_details_and_extra(self, setup):
        q = ('{ mortgageDetails(bankName: "Ally", accountName: "Home", extraMonthly: %s) { balance remainingMonths '
             'monthsSaved interestSaved schedule { principal interest } years { year endBalance } } }')
        base = run(setup, q % 0)["mortgageDetails"]
        assert base["balance"] == 250000 and base["monthsSaved"] == 0 and len(base["schedule"]) == 12
        assert base["years"][-1]["endBalance"] == 0
        extra = run(setup, q % 500)["mortgageDetails"]
        assert extra["monthsSaved"] > 0 and extra["interestSaved"] > 0

    def test_compare_strategies(self, setup):
        ok(setup, 'mutation { updateCreditBalance(bankName: "Chase", accountName: "Freedom", newBalance: 800) '
                  '{ success message } }')
        data = run(setup, '{ strategyTargets compareStrategies(days: 60, targetAccount: "Freedom") '
                          '{ goal finalCash interestPaid extraTotal } }')
        assert data["strategyTargets"] == ["Freedom"]
        assert [s["goal"] for s in data["compareStrategies"]] == [
            "maximize_discretionary", "minimize_interest", "payoff_credit_account"]

    def test_insights_accept_strategy(self, setup):
        data = run(setup, '{ paymentInsights(days: 30, strategy: "minimize_interest") { netBenefit } }')
        assert data["paymentInsights"] is not None

    def test_monthly_projection(self, setup):
        ok(setup, 'mutation { createIncomeSource(sourceName: "Pay", amount: 2000, frequency: "monthly", '
                  'payDates: [1]) { success message } }')
        months = run(setup, "{ monthlyProjection(days: 90) { month income endCash } }")["monthlyProjection"]
        assert len(months) >= 3 and sum(m["income"] for m in months) >= 4000


class TestBillsAndIncome:
    def test_floating_bill_history_and_reset(self, setup):
        ok(setup, 'mutation { createBill(billName: "Power", amount: 100, dueDate: 20, billType: "floating") '
                  '{ success message } }')
        ok(setup, 'mutation { setFloatingBillAmount(billName: "Power", actualAmount: 140) { success message } }')
        ok(setup, 'mutation { resetBillToEstimate(billName: "Power") { success message } }')
        bill = next(b for b in run(setup, "{ allBills { billName amount hasActualAmount amountHistory } }")["allBills"]
                    if b["billName"] == "Power")
        assert bill["amount"] == 100 and not bill["hasActualAmount"] and bill["amountHistory"] == []

    def test_percentage_split_round_trips(self, setup):
        dist = '{\\"Savings\\": {\\"value\\": 0.25, \\"type\\": \\"percentage\\"}, \\"Checking\\": null}'
        ok(setup, 'mutation { createIncomeSource(sourceName: "Pay", amount: 2000, frequency: "monthly", '
                  'payDates: [1]) { success message } }')
        ok(setup, 'mutation { updateIncome(sourceName: "Pay", distribution: "%s") { success message } }' % dist)
        inc = run(setup, "{ allIncome { sourceName distributionDetail } }")["allIncome"][0]
        assert json.loads(inc["distributionDetail"])["Savings"] == {"value": 0.25, "type": "percentage"}

    def test_small_fixed_amount_is_not_a_percentage(self):
        from models.bank import Bank
        from models.income_source import IncomeSource
        from models.types import DistributionType
        bank = Bank("B")
        bank.add_account("checking", "Checking")
        bank.add_account("savings", "Savings")
        inc = IncomeSource("Pay", 1000, "monthly", [1], DistributionType.__fromdict__(
            {"Savings": {"value": 1, "type": "fixed_amount"}, "Checking": None}))
        out = inc.deposit_to_bank(bank)
        assert out == {"Savings": 1, "Checking": 999}


class TestFiles:
    @pytest.mark.parametrize("kind", ["timeline", "monthly", "balances", "plan", "snapshot"])
    def test_reports_download(self, setup, kind):
        r = setup.get(f"/files/reports/{kind}.csv?days=30")
        assert r.status_code == 200 and r.mimetype == "text/csv"
        assert r.data.decode("utf-8-sig").splitlines()[0]
        x = setup.get(f"/files/reports/{kind}.xlsx?days=30")
        assert x.status_code == 200 and x.data[:2] == b"PK"

    def test_unknown_report(self, setup):
        assert setup.get("/files/reports/nope.csv").status_code == 404

    def test_calendar(self, setup):
        ok(setup, 'mutation { createBill(billName: "Rent", amount: 1500, dueDate: 1) { success message } }')
        r = setup.get("/files/calendar.ics")
        text = r.data.decode()
        assert r.status_code == 200 and text.startswith("BEGIN:VCALENDAR")
        assert text.count("SUMMARY:Rent due") >= 5

    def test_database_info(self, setup):
        info = run(setup, "{ databaseInfo { path sizeBytes tables { table rows } } }")["databaseInfo"]
        rows = {t["table"]: t["rows"] for t in info["tables"]}
        assert rows["banks"] == 2 and info["sizeBytes"] > 0


def test_cli_snapshot_menu_option(capsys):
    """Dashboard › 1 in the CLI used to crash (view_snapshot didn't exist)."""
    from models.cli_menu import FinanceCLI
    from models.finance_manager import FinanceManager
    FinanceCLI(FinanceManager([], [], [])).view_snapshot()
    assert capsys.readouterr().out.strip()
