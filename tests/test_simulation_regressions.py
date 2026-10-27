"""
Regression tests for domain/simulation-layer bugs (timeline simulator,
payment optimizer, bills, income, loans, bill groups, debt estimator,
financial report).
"""

from datetime import date, timedelta

import pytest

from models.bank import Bank
from models.bill_group import BillGroup
from models.debt_estimator import DebtInfo, DebtPayoffEstimator
from models.financial_report import FinancialReport
from models.fixed_bill import AccountLinkedBill, Bill, FloatingBill
from models.heloc_account import HELOCAccount
from models.income_source import IncomeFrequency, IncomeSource
from models.mortgage_account import EscrowBreakdown, MortgageAccount
from models.payment_optimizer import PaymentOptimizer
from models.timeline_simulator import TimelineEvent, TimelineSimulator
from models.types import AllocationMethod, BillFrequency, BillType, HELOCPhase


def scan_due_dates(bill, start, end):
    """All dates in [start, end] the simulator would treat as due dates."""
    out, d = [], start
    while d <= end:
        if bill.get_next_due_date(d - timedelta(days=1)) == d:
            out.append(d)
        d += timedelta(days=1)
    return out


def cf_of(result, cf_type):
    return [c for c in result["cash_flow"] if c["type"] == cf_type]


# ── 1. Paid flag only suppresses the first occurrence ─────────────────────

class TestPaidFlagFirstOccurrenceOnly:
    def test_bills_paid_every_month(self):
        b = Bank("B")
        b.add_account("checking", "chk", 10000)
        cc = b.add_credit_account("Card", 10000, 0.0, payment_due_date=10, statement_date=5)
        cc.make_purchase(3000, transaction_date=date(2026, 1, 1))
        bills = [Bill("Rent", 1000, 1), AccountLinkedBill(cc, "B", "credit")]
        r = TimelineSimulator([b], [], bills).project_balances(date(2026, 1, 1), date(2026, 6, 30))
        assert len(cf_of(r, "BILL_PAYMENT")) == 6
        assert len(cf_of(r, "CREDIT_PAYMENT")) == 6
        assert not cf_of(r, "BILL_ALREADY_PAID")

    def test_real_paid_flag_skips_only_first(self):
        b = Bank("B")
        b.add_account("checking", "chk", 10000)
        rent = Bill("Rent", 1000, 1)
        rent.is_paid_this_period = True
        r = TimelineSimulator([b], [], [rent]).project_balances(date(2026, 1, 1), date(2026, 4, 30))
        assert [c["date"] for c in cf_of(r, "BILL_ALREADY_PAID")] == [date(2026, 1, 1)]
        assert [c["date"] for c in cf_of(r, "BILL_PAYMENT")] == [
            date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]

    def test_group_paid_every_month(self):
        b = Bank("B")
        b.add_account("checking", "chk", 10000)
        loan = b.add_credit_account("L1", 10000, 0.0)
        loan.make_purchase(5000, transaction_date=date(2026, 1, 1))
        g = BillGroup("Loans", 200, 10, preferred_source_bank="B", preferred_source_account="chk")
        g.add_member("B", "L1")
        r = TimelineSimulator([b], [], [], [g]).project_balances(date(2026, 1, 1), date(2026, 4, 30))
        assert len(cf_of(r, "BILL_GROUP_PAYMENT")) == 4


# ── 2. Frequencies ────────────────────────────────────────────────────────

class TestFrequencies:
    def test_weekly_and_biweekly_bills(self):
        weekly = scan_due_dates(Bill("W", 50, 5, frequency="weekly"), date(2026, 1, 1), date(2026, 2, 28))
        assert weekly[0] == date(2026, 1, 5) and len(weekly) == 8
        assert all((b - a).days == 7 for a, b in zip(weekly, weekly[1:]))
        biweekly = scan_due_dates(Bill("BW", 50, 5, frequency="biweekly"), date(2026, 1, 1), date(2026, 2, 28))
        assert biweekly == [date(2026, 1, 5), date(2026, 1, 19), date(2026, 2, 2), date(2026, 2, 16)]

    def test_bill_start_date_anchor(self):
        bill = Bill("BW", 50, 1, frequency=BillFrequency.BIWEEKLY, start_date=date(2026, 1, 9))
        assert scan_due_dates(bill, date(2026, 1, 1), date(2026, 2, 28)) == [
            date(2026, 1, 9), date(2026, 1, 23), date(2026, 2, 6), date(2026, 2, 20)]
        q = Bill("Q", 50, 1, frequency="quarterly", start_date=date(2026, 2, 15))
        assert scan_due_dates(q, date(2026, 1, 1), date(2026, 12, 31)) == [
            date(2026, 2, 15), date(2026, 5, 15), date(2026, 8, 15), date(2026, 11, 15)]
        fb = FloatingBill("Water", 60, 1, frequency="weekly", start_date=date(2026, 3, 2))
        assert fb.start_date == date(2026, 3, 2)
        assert fb.get_next_due_date(date(2026, 3, 2)) == date(2026, 3, 9)

    def test_quarterly_semiannual_yearly_once(self):
        assert len(scan_due_dates(Bill("Q", 50, 5, frequency="quarterly"), date(2026, 1, 1), date(2026, 12, 31))) == 4
        assert len(scan_due_dates(Bill("S", 50, 5, frequency="semi_annual", due_month=3),
                                  date(2026, 1, 1), date(2026, 12, 31))) == 2
        # Yearly without due_month must not degrade into monthly
        assert len(scan_due_dates(Bill("Y", 50, 5, frequency="yearly"), date(2026, 1, 1), date(2027, 12, 31))) == 2
        once = Bill("O", 50, 5, frequency="once")
        assert scan_due_dates(once, date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 1, 5)]
        assert once.get_next_due_date(date(2026, 1, 5)) == date.max
        explicit_once = Bill("O2", 50, 1, frequency="once", start_date=date(2026, 7, 4))
        assert scan_due_dates(explicit_once, date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 7, 4)]

    def test_every_bill_frequency_handled(self):
        for freq in BillFrequency:
            bill = Bill("X", 10, 15, frequency=freq, due_month=1)
            assert bill.get_next_due_date(date(2026, 1, 1)) > date(2026, 1, 1)

    def test_income_frequencies(self):
        inc = IncomeSource("Pay", 2000, frequency="biweekly", pay_date=[2])
        dates = inc.get_pay_dates_in_range(date(2025, 12, 31), date(2026, 3, 31))
        assert dates[0] == date(2026, 1, 2) and len(dates) == 7
        inc = IncomeSource("Pay", 500, frequency="weekly", start_date=date(2026, 1, 9))
        assert inc.get_pay_dates_in_range(date(2025, 12, 31), date(2026, 1, 31)) == [
            date(2026, 1, 9), date(2026, 1, 16), date(2026, 1, 23), date(2026, 1, 30)]
        inc = IncomeSource("Bonus", 500, frequency="bimonthly", pay_date=[15])
        assert len(inc.get_pay_dates_in_range(date(2025, 12, 31), date(2026, 12, 31))) == 6
        inc = IncomeSource("Once", 500, frequency="once", start_date=date(2026, 5, 15))
        assert inc.get_pay_dates_in_range(date(2025, 12, 31), date(2026, 12, 31)) == [date(2026, 5, 15)]
        assert inc.get_next_pay_date(date(2026, 5, 15)) == date.max
        # Semimonthly keeps the pay_date list behavior
        inc = IncomeSource("Semi", 1000, frequency="semimonthly", pay_date=[15, 31])
        assert len(inc.get_pay_dates_in_range(date(2025, 12, 31), date(2026, 3, 31))) == 6

    def test_every_income_frequency_handled(self):
        for freq in IncomeFrequency:
            inc = IncomeSource("X", 10, frequency=freq, pay_date=[15])
            assert inc.get_next_pay_date(date(2026, 1, 1)) > date(2026, 1, 1)

    def test_weekend_shifted_paycheck_at_window_end(self):
        # Aug 1 2026 is a Saturday -> paid Friday Jul 31
        inc = IncomeSource("Pay", 500, pay_date=[1])
        assert inc.get_pay_dates_in_range(date(2026, 6, 30), date(2026, 7, 31)) == [
            date(2026, 7, 1), date(2026, 7, 31)]
        assert inc.get_next_pay_date(date(2026, 7, 30)) == date(2026, 7, 31)
        assert inc.get_next_pay_date(date(2026, 7, 31)) == date(2026, 9, 1)


# ── 3. Month-end clamping ─────────────────────────────────────────────────

class TestMonthEndClamping:
    def test_due_31_every_month_once(self):
        hits = scan_due_dates(Bill("X", 100, 31), date(2026, 1, 1), date(2026, 12, 31))
        assert len(hits) == 12
        assert date(2026, 2, 28) in hits and date(2026, 4, 30) in hits
        assert date(2026, 3, 1) not in hits

    def test_loans_and_groups_clamp(self):
        m = MortgageAccount("M", 100000, 5.0, 360, payment_due_date=31)
        assert m.get_next_due_date(date(2026, 2, 1)) == date(2026, 2, 28)
        h = HELOCAccount("H", 50000, 8.0, 120, 240, start_date=date(2025, 1, 31), payment_due_date=30)
        assert h.get_next_due_date(date(2026, 2, 1)) == date(2026, 2, 28)
        assert h.draw_end_date == date(2035, 1, 31)
        g = BillGroup("G", 100, 31)
        assert g.get_next_due_date(date(2026, 4, 1)) == date(2026, 4, 30)

    def test_interest_day_31_accrues_in_short_months(self):
        b = Bank("B")
        b.add_account("savings", "sav", 10000, interest_rate=4.0, interest_accrual_date=31)
        r = TimelineSimulator([b], [], []).project_balances(date(2026, 1, 1), date(2026, 12, 31))
        assert len(cf_of(r, "INTEREST")) == 12

    def test_credit_statement_day_31(self):
        b = Bank("B")
        b.add_account("checking", "chk", 100)
        cc = b.add_credit_account("Card", 10000, 24.0, statement_date=31)
        cc.make_purchase(1000, transaction_date=date(2026, 1, 1))
        r = TimelineSimulator([b], [], []).project_balances(date(2026, 2, 1), date(2026, 4, 30))
        assert [c["date"] for c in cf_of(r, "INTEREST")] == [
            date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


# ── 4. Report keeps linked bills connected to copied accounts ─────────────

class TestReportCopies:
    def test_projection_uses_copied_accounts(self):
        b = Bank("B")
        b.add_account("checking", "chk", 5000)
        cc = b.add_credit_account("Card", 10000, 0.0, payment_due_date=10)
        cc.make_purchase(3000, transaction_date=date(2026, 1, 1))
        bills = [AccountLinkedBill(cc, "B", "credit"), Bill("Rent", 1000, 15)]
        rep = FinancialReport([b], [], bills)
        r = rep.projection_report(date(2026, 1, 1), date(2026, 1, 31), include_optimization=False)["result"]
        assert r["credit_final_balances"]["B:Card"] == pytest.approx(3000 - 60)
        # Real objects untouched
        assert cc.balance == 3000 and b.accounts["chk"].balance == 5000

    def test_bill_groups_passed_through(self):
        b = Bank("B")
        b.add_account("checking", "chk", 5000)
        loan = b.add_credit_account("L1", 10000, 0.0)
        loan.make_purchase(2000, transaction_date=date(2026, 1, 1))
        g = BillGroup("Loans", 300, 10, preferred_source_bank="B", preferred_source_account="chk")
        g.add_member("B", "L1")
        rep = FinancialReport([b], [], [], bill_groups=[g])
        out = rep.projection_report(date(2026, 1, 1), date(2026, 1, 31), include_optimization=True)
        assert len(cf_of(out["result"], "BILL_GROUP_PAYMENT")) == 1
        assert loan.balance == 2000
        assert "Group Payments" in out["text"]


# ── 5/6. HELOC interest accrual and simulated-date phase ─────────────────

class TestHELOC:
    def test_interest_only_keeps_balance_flat(self):
        b = Bank("H")
        b.add_account("checking", "chk", 50000)
        h = b.add_heloc_account("HELOC", 100000, 9.0, draw_period_months=120, total_term_months=240,
                                start_date=date(2025, 1, 1), current_balance=50000, payment_due_date=15)
        hb = AccountLinkedBill(h, "H", "heloc", bill_type=BillType.HELOC_PAYMENT)
        r = TimelineSimulator([b], [], [hb]).project_balances(date(2026, 1, 1), date(2026, 3, 31))
        interest = cf_of(r, "INTEREST")
        assert len(interest) == 3 and all(c["account_kind"] == "heloc" for c in interest)
        assert len(cf_of(r, "HELOC_PAYMENT")) == 3
        assert h.balance == pytest.approx(50000)

    def test_unpaid_heloc_accrues_interest(self):
        b = Bank("H")
        b.add_account("checking", "chk", 0)
        h = b.add_heloc_account("HELOC", 100000, 12.0, 120, 240, start_date=date(2025, 1, 1),
                                current_balance=10000, payment_due_date=1)
        TimelineSimulator([b], [], []).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        assert h.balance == pytest.approx(10100)

    def test_phase_and_minimum_as_of(self):
        h = HELOCAccount("H2", 100000, 9.0, draw_period_months=12, total_term_months=120,
                         start_date=date(2026, 6, 1), current_balance=50000)
        assert h.get_phase_on_date(date(2027, 7, 1)) == HELOCPhase.REPAYMENT
        draw_min = h.calculate_minimum_payment(as_of=date(2026, 7, 1))
        repay_min = h.calculate_minimum_payment(as_of=date(2027, 7, 1))
        assert draw_min == pytest.approx(375.0)
        assert repay_min > draw_min
        assert h.get_available_credit(as_of=date(2027, 7, 1)) == 0.0
        with pytest.raises(ValueError):
            h.make_draw(100, transaction_date=date(2027, 7, 1))
        h.make_draw(100, transaction_date=date(2026, 7, 1))
        assert h.balance == 50100

    def test_linked_bill_uses_simulated_date(self):
        h = HELOCAccount("H2", 100000, 9.0, 12, 120, start_date=date(2026, 6, 1), current_balance=50000)
        bill = AccountLinkedBill(h, "B", "heloc", bill_type=BillType.HELOC_PAYMENT)
        assert bill.amount_on(date(2027, 7, 1)) == h.calculate_minimum_payment(as_of=date(2027, 7, 1))
        assert bill.amount_on(date(2026, 7, 1)) == pytest.approx(375.0)

    def test_credit_linked_bill_uses_simulated_date(self):
        b = Bank("C")
        b.add_account("checking", "chk", 50000)
        cc = b.add_credit_account("Card", 10000, 0.0, payment_due_date=10)
        cc.add_promotional_offer("0APR", 12, start_date=date(2026, 1, 1))
        cc.make_purchase(1200, transaction_date=date(2026, 1, 2), promo_name="0APR")
        bill = AccountLinkedBill(cc, "C", "credit")
        r = TimelineSimulator([b], [], [bill]).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        paid = -cf_of(r, "CREDIT_PAYMENT")[0]["amount"]
        # Promo payoff portion is based on Jan 10 2026, not on today's date
        expected = round(1200 / ((cc.active_promos[0].end_date - date(2026, 1, 10)).days / 30.0), 2)
        assert paid == pytest.approx(expected, abs=0.01)


# ── 7. Mortgage payment math ──────────────────────────────────────────────

class TestMortgage:
    def test_partial_payment_never_increases_principal(self):
        m = MortgageAccount("M", 200000, 6.0, 360, current_principal=1000,
                            escrow=EscrowBreakdown(property_tax_monthly=400))
        record = m.make_payment(amount=100)
        assert m.current_principal == 1000
        assert record["principal"] == 0
        assert record["interest"] == pytest.approx(5.0)
        assert record["escrow"] == pytest.approx(95.0)

    def test_overpayment_capped_at_principal(self):
        m = MortgageAccount("M", 200000, 6.0, 360, current_principal=300)
        record = m.make_payment(amount=5000)
        assert m.current_principal == 0
        assert record["principal"] == pytest.approx(300)

    def test_near_payoff_timeline_payment_covers_interest_and_escrow(self):
        b = Bank("B")
        b.add_account("checking", "chk", 50000)
        m = b.add_mortgage_account("Home", 200000, 6.0, 360, current_principal=300.0, payment_due_date=1,
                                   escrow=EscrowBreakdown(property_tax_monthly=400))
        bill = AccountLinkedBill(m, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)
        r = TimelineSimulator([b], [], [bill]).project_balances(date(2026, 1, 1), date(2026, 1, 1))
        cf = cf_of(r, "MORTGAGE_PAYMENT")[0]
        assert cf["amount"] == pytest.approx(-(300 + 1.5 + 400))
        assert cf["principal"] == pytest.approx(300) and cf["escrow"] == pytest.approx(400)
        assert cf["mortgage_name"] == "Home"
        assert m.current_principal == 0

    def test_payoff_with_zero_extra_reports_no_savings(self):
        res = MortgageAccount("M", 300000, 6.5, 360).calculate_payoff_with_extra(0)
        assert res["months_saved"] == 0
        assert res["interest_saved"] == pytest.approx(0.0)
        res = MortgageAccount("M", 300000, 6.5, 360).calculate_payoff_with_extra(500)
        assert res["months_saved"] > 0 and res["interest_saved"] > 0

    def test_zero_percent_loan(self):
        m = MortgageAccount("M0", 120000, 0.0, 360, current_principal=60000)
        assert m.base_monthly_payment == pytest.approx(333.33)
        assert m.remaining_months == 180


# ── 8. Bill group allocation ──────────────────────────────────────────────

class TestBillGroupAllocation:
    def _bank(self, balances):
        b = Bank("B")
        b.add_account("checking", "chk", 5000)
        for name, bal in balances.items():
            c = b.add_credit_account(name, 10000, 0.0)
            c.make_purchase(bal, transaction_date=date(2026, 1, 1))
        return b

    def test_fixed_scaled_to_payment(self):
        b = self._bank({"L1": 2000, "L2": 2000})
        g = BillGroup("Loans", 300, 10, preferred_source_bank="B", preferred_source_account="chk")
        g.add_member("B", "L1", AllocationMethod.FIXED, fixed_amount=250)
        g.add_member("B", "L2", AllocationMethod.FIXED, fixed_amount=250)
        r = TimelineSimulator([b], [], [], [g]).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        cf = cf_of(r, "BILL_GROUP_PAYMENT")[0]
        assert -cf["amount"] == pytest.approx(300)
        assert sum(s["amount"] for s in cf["sub_payments"]) == pytest.approx(300)
        assert r["final_balances"]["B:chk"] == pytest.approx(4700)

    def test_excess_redistributed(self):
        b = self._bank({"L1": 50, "L2": 1000})
        g = BillGroup("Loans", 300, 10)
        g.add_member("B", "L1", AllocationMethod.EQUAL)
        g.add_member("B", "L2", AllocationMethod.EQUAL)
        subs = g.distribute_payment(300, [b], date(2026, 1, 10))
        paid = {s["account_name"]: s["amount"] for s in subs}
        assert paid == {"L1": 50, "L2": 250}

    def test_withdraw_capped_at_group_balance(self):
        b = self._bank({"L1": 50})
        g = BillGroup("Loans", 300, 10, preferred_source_bank="B", preferred_source_account="chk")
        g.add_member("B", "L1")
        r = TimelineSimulator([b], [], [], [g]).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        assert -cf_of(r, "BILL_GROUP_PAYMENT")[0]["amount"] == pytest.approx(50)
        assert r["final_balances"]["B:chk"] == pytest.approx(4950)

    def test_fixed_plus_equal_split(self):
        b = self._bank({"L1": 1000, "L2": 1000, "L3": 3000})
        g = BillGroup("Loans", 300, 10)
        g.add_member("B", "L1", AllocationMethod.FIXED, fixed_amount=100)
        g.add_member("B", "L2", AllocationMethod.EQUAL)
        g.add_member("B", "L3", AllocationMethod.EQUAL)
        paid = {s["account_name"]: s["amount"] for s in g.distribute_payment(300, [b])}
        assert paid == {"L1": 100, "L2": 100, "L3": 100}


# ── 9. Debt estimator ─────────────────────────────────────────────────────

class TestDebtEstimator:
    def test_freed_minimums_roll_forward(self):
        debts = [DebtInfo("A", 200, 0, 100), DebtInfo("B", 1000, 0, 100)]
        r = DebtPayoffEstimator.estimate(debts, extra_monthly=0.0)
        assert r["avalanche"].months_to_payoff == 6
        assert r["snowball"].months_to_payoff == 6
        assert r["minimum"].months_to_payoff == 10
        assert r["avalanche"].pays_off and r["avalanche"].remaining_balance == 0.0

    def test_payoff_month_overpay_cascades(self):
        debts = [DebtInfo("A", 50, 0, 100), DebtInfo("B", 1000, 0, 100)]
        r = DebtPayoffEstimator.estimate(debts, extra_monthly=0.0)
        assert r["avalanche"].monthly_breakdown[0]["total_remaining"] == pytest.approx(850)

    def test_never_amortizing_debt_flagged(self):
        debts = [DebtInfo("Card", 10000, 24.0, 150)]  # interest 200/mo > min 150
        r = DebtPayoffEstimator.estimate(debts, 0)
        assert r["minimum"].pays_off is False
        assert r["minimum"].remaining_balance > 10000
        assert r["minimum"].never_amortizes == ["Card"]
        # Enough extra makes it amortize
        r = DebtPayoffEstimator.estimate(debts, 200)
        assert r["avalanche"].pays_off is True


# ── 10. Report totals ─────────────────────────────────────────────────────

class TestReportTotals:
    def test_budget_analysis_counts_all_payment_types(self):
        b = Bank("B")
        b.add_account("checking", "chk", 50000)
        cc = b.add_credit_account("Card", 10000, 0.0, payment_due_date=10)
        cc.make_purchase(1000, transaction_date=date.today())
        bills = [AccountLinkedBill(cc, "B", "credit"), Bill("Rent", 1000, 15)]
        text = FinancialReport([b], [], bills).budget_analysis(2)
        months = [line for line in text.splitlines() if "Expenses: $" in line]
        # Expenses are positive (abs of outflows) and include the $25 credit minimum
        assert not any("Expenses: $-" in line for line in months)
        assert any(line.split("Expenses: $")[1].startswith("1,025.00") for line in months)

    def test_projection_monthly_totals_include_heloc_and_exclude_charged_interest(self):
        b = Bank("H")
        b.add_account("checking", "chk", 50000)
        h = b.add_heloc_account("HELOC", 100000, 12.0, 120, 240, start_date=date(2025, 1, 1),
                                current_balance=10000, payment_due_date=15)
        hb = AccountLinkedBill(h, "H", "heloc", bill_type=BillType.HELOC_PAYMENT)
        out = FinancialReport([b], [], [hb]).projection_report(date(2026, 1, 1), date(2026, 1, 31),
                                                               include_optimization=False)
        text = out["text"]
        assert "HELOC Payments" in text
        # Only the $100 HELOC payment is a cash outflow; the $100 interest is not
        assert "Net Cash Flow:      -$      100.00" in text


# ── 11. Recalls before bills; deferred when no account can pay ────────────

class TestOrderingAndDeferral:
    def test_recall_processed_before_same_day_bill(self):
        b = Bank("B")
        b.add_account("checking", "chk", 0)
        b.add_account("savings", "sav", 5000, interest_rate=4.0, interest_accrual_date=28)
        bills = [Bill("Tuition", 2500, 15, preferred_source_bank="B", preferred_source_account="chk")]
        recall = TimelineEvent(date(2026, 1, 15), "SAVINGS_RECALL", 3000, "Recall from sav",
                               from_bank="B", from_account="sav", to_bank="B", to_account="chk")
        r = TimelineSimulator([b], [], bills).project_balances(
            date(2026, 1, 1), date(2026, 1, 31), injected_events={date(2026, 1, 15): [recall]})
        types = [c["type"] for c in r["cash_flow"] if c["date"] == date(2026, 1, 15)]
        assert types.index("SAVINGS_RECALL") < types.index("BILL_PAYMENT")
        assert not cf_of(r, "BILL_DEFERRED")

    def test_optimizer_recall_has_no_violations(self):
        b = Bank("B")
        b.add_account("checking", "chk", 300)
        b.add_account("savings", "sav", 0, interest_rate=4.0, interest_accrual_date=28)
        bills = [Bill("Small", 100, 2, preferred_source_bank="B", preferred_source_account="chk"),
                 Bill("Tuition", 2500, 15, preferred_source_bank="B", preferred_source_account="chk")]
        inc = [IncomeSource("Pay", 3000, pay_date=[1], distribution={"chk": "remainder"}),
               IncomeSource("Side", 100, pay_date=[15], distribution={"chk": "remainder"})]
        res, plan = PaymentOptimizer([b], inc, bills).run_optimized_simulation(date(2026, 1, 1), date(2026, 1, 31))
        assert len(cf_of(res, "BILL_PAYMENT")) == 2
        assert not [v for v in plan.violations if "could not be paid" in v or "overdraft" in v]

    def test_unpayable_bill_logged_as_deferred(self):
        b = Bank("B")
        b.add_account("checking", "chk", 10)
        r = TimelineSimulator([b], [], [Bill("Rent", 1000, 5)]).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        deferred = cf_of(r, "BILL_DEFERRED")
        assert len(deferred) == 1 and deferred[0]["amount"] == -1000
        m = b.add_mortgage_account("Home", 100000, 6.0, 360, payment_due_date=10)
        mb = AccountLinkedBill(m, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT)
        r = TimelineSimulator([b], [], [mb]).project_balances(date(2026, 1, 1), date(2026, 1, 31))
        assert cf_of(r, "MORTGAGE_DEFERRED")[0]["mortgage_name"] == "Home"


# ── 12/13. Optimizer strategy keys, violations, interest split ────────────

class TestOptimizer:
    def _setup(self):
        b = Bank("B")
        b.add_account("checking", "chk", 8000)
        b.add_account("checking", "chk2", 8000)
        b.add_account("savings", "sav", 10000, interest_rate=4.0, interest_accrual_date=28)
        cc = b.add_credit_account("Card", 10000, 24.0, payment_due_date=12, statement_date=3)
        cc.make_purchase(2000, transaction_date=date(2025, 12, 1))
        m = b.add_mortgage_account("Home", 200000, 6.0, 360, payment_due_date=5)
        bills = [AccountLinkedBill(m, "B", "mortgage", bill_type=BillType.MORTGAGE_PAYMENT),
                 AccountLinkedBill(cc, "B", "credit"), Bill("Rent", 500, 20)]
        inc = [IncomeSource("Pay", 4000, pay_date=[1], distribution={"chk": "remainder"})]
        return b, bills, inc

    def test_strategy_keys_match_simulator_and_no_false_violations(self):
        b, bills, inc = self._setup()
        opt = PaymentOptimizer([b], inc, bills)
        res, plan = opt.run_optimized_simulation(date(2026, 1, 1), date(2026, 2, 27))
        bill_names = {bl.bill_name for bl in bills}
        for key, entry in plan.strategy.items():
            name, _, iso = key.rpartition("_")
            assert name in bill_names
            date.fromisoformat(iso)
        assert not [v for v in plan.violations if "Mortgage payment not scheduled" in v]
        # Routing from the plan is applied by the simulator
        rent_key = next(k for k in plan.strategy if k.startswith("Rent_"))
        plan.strategy[rent_key]["account"] = "chk2"
        res2 = opt._run_simulation(date(2026, 1, 1), date(2026, 2, 27), plan.strategy)
        rent_cf = [c for c in res2["cash_flow"] if c["type"] == "BILL_PAYMENT" and c["description"] == "Rent"]
        assert any(c["account"] == "chk2" for c in rent_cf)

    def test_interest_split_paid_vs_earned(self):
        b, bills, inc = self._setup()
        res, plan = PaymentOptimizer([b], inc, bills).run_optimized_simulation(date(2026, 1, 1), date(2026, 2, 27))
        charged = sum(c["amount"] for c in cf_of(res, "INTEREST") if c["account"] == "Card")
        earned = sum(c["amount"] for c in cf_of(res, "INTEREST") if c["account"] == "sav")
        assert charged > 0 and earned > 0
        assert plan.total_interest_paid == pytest.approx(charged)
        assert plan.estimated_interest_earned == pytest.approx(earned)

    def test_linked_bills_not_double_counted(self):
        b, bills, inc = self._setup()
        opt = PaymentOptimizer([b], inc, bills)
        baseline = opt._run_simulation(date(2026, 1, 1), date(2026, 2, 27))
        names = {x["bill_name"] for x in opt._extract_bill_schedule(baseline)}
        assert names == {"Rent"}

    def test_group_payments_counted_in_schedule(self):
        b = Bank("B")
        b.add_account("checking", "chk", 5000)
        loan = b.add_credit_account("L1", 10000, 0.0)
        loan.make_purchase(2000, transaction_date=date(2026, 1, 1))
        g = BillGroup("Loans", 300, 10, preferred_source_bank="B", preferred_source_account="chk")
        g.add_member("B", "L1")
        opt = PaymentOptimizer([b], [], [], [g])
        sched = opt._extract_bill_schedule(opt._run_simulation(date(2026, 1, 1), date(2026, 1, 31)))
        assert [(x["amount"], x["is_group"]) for x in sched] == [(300, True)]

    def test_deferred_types_reported(self):
        b = Bank("B")
        b.add_account("checking", "chk", 10)
        cc = b.add_credit_account("Card", 10000, 0.0, payment_due_date=10)
        cc.make_purchase(3000, transaction_date=date(2026, 1, 1))
        opt = PaymentOptimizer([b], [], [AccountLinkedBill(cc, "B", "credit")])
        _, plan = opt.run_optimized_simulation(date(2026, 1, 1), date(2026, 1, 31))
        assert any("Credit card payment could not be paid" in v for v in plan.violations)


# ── 14. Promo payoff targets the promo balance ────────────────────────────

class TestPromoPayoff:
    def _card(self):
        b = Bank("C")
        b.add_account("checking", "chk", 5000)
        cc = b.add_credit_account("Card", 10000, 24.0)
        cc.add_promotional_offer("0APR", 12, start_date=date(2026, 1, 1))
        cc.make_purchase(1000, transaction_date=date(2026, 1, 2))
        cc.make_purchase(2000, transaction_date=date(2026, 1, 2), promo_name="0APR")
        return b, cc

    def test_make_payment_promo_name(self):
        _, cc = self._card()
        cc.make_payment(2500, promo_name="0APR")
        assert cc.promo_balance["0APR"] == 0
        assert cc.regular_balance == pytest.approx(500)

    def test_promo_payoff_event(self):
        b, cc = self._card()
        evt = TimelineEvent(date(2026, 1, 10), "PROMO_PAYOFF", 2000, "Promo payoff: 0APR on Card",
                            from_bank="C", from_account="chk", to_bank="C", to_account="Card")
        TimelineSimulator([b], [], []).project_balances(
            date(2026, 1, 10), date(2026, 1, 10), injected_events={date(2026, 1, 10): [evt]})
        assert cc.promo_balance["0APR"] == 0
        assert cc.regular_balance == pytest.approx(1000)


# ── 15. Bank credit balance update keeps sub-balances in sync ─────────────

def test_update_credit_balance_sets_regular_balance():
    b = Bank("C")
    cc = b.add_credit_account("Card", 10000, 24.0)
    cc.add_promotional_offer("0APR", 12, start_date=date(2026, 1, 1))
    cc.make_purchase(500, transaction_date=date(2026, 1, 2), promo_name="0APR")
    b.update_credit_balance("Card", 2000)
    assert cc.balance == 2000
    assert cc.regular_balance == pytest.approx(1500)
    b.update_credit_balance("Card", 100)
    assert cc.regular_balance == 0
