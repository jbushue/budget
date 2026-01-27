"""
Example usage of the personal finance management system.

This demonstrates how to set up banks, accounts, income sources, and bills,
then run projections and optimization.
"""

from datetime import date, timedelta
from models.bank import Bank
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource
from models.finance_manager import FinanceManager


def example_setup():
    """Create a sample financial setup."""

    # ========== Create Banks ==========

    # Traditional bank with checking and savings accounts
    checking_bank = Bank("Chase Bank", bank_type="traditional")
    checking_bank.add_account(
        account_type="checking",
        account_name="Primary Checking",
        starting_balance=2500.00,
        interest_rate=0.01
    )
    checking_bank.add_account(
        account_type="savings",
        account_name="Emergency Fund",
        starting_balance=10000.00,
        interest_rate=4.5,  # 4.5% APR
        interest_accrual_date=1  # Accrue on 1st of month
    )

    # Bank with credit cards
    credit_issuer = Bank("American Express", bank_type="credit_issuer")
    credit_issuer.add_credit_account(
        account_name="Business Card",
        credit_limit=15000.00,
        interest_rate=18.5,  # 18.5% APR
        payment_due_date=20,  # Due on 20th of month
        statement_date=15  # Statement closes on 15th
    )

    # Alternate bank
    secondary_bank = Bank("Wells Fargo")
    secondary_bank.add_account(
        account_type="savings",
        account_name="Vacation Fund",
        starting_balance=5000.00,
        interest_rate=3.0
    )

    # ========== Create Income Sources ==========

    # Primary salary (deposited to checking)
    salary = IncomeSource(
        source_name="Monthly Salary",
        amount=5000.00,
        frequency="monthly",
        pay_date=1,  # 1st of month
        distribution={
            "Primary Checking": 3500.00,
            "Emergency Fund": "remainder"  # Remaining amount goes to savings
        }
    )

    # Side income (quarterly bonus)
    bonus = IncomeSource(
        source_name="Quarterly Bonus",
        amount=2000.00,
        frequency="quarterly",
        pay_date=15,
        distribution={
            "Vacation Fund": 1.0  # 100% to vacation fund
        }
    )

    # ========== Create Bills ==========

    bills = [
        # Fixed bills
        Bill(
            bill_name="Rent",
            amount=3000.00,
            due_date=1,
            frequency="monthly",
            preferred_source_bank="Chase Bank",
            preferred_source_account="Primary Checking"
        ),
        Bill(bill_name="Brockton"),
        Bill(
            bill_name="Internet",
            amount=90.00,
            due_date=15,
            frequency="monthly",
            preferred_source_bank="Chase Bank",
            preferred_source_account="Primary Checking"
        ),
        Bill(
            bill_name="Car Insurance",
            amount=1100.00,
            due_date=10,
            frequency="semi_annual",
            preferred_source_bank="Chase Bank",
            preferred_source_account="Primary Checking"
        ),
        Bill(
            bill_name="Gym Membership",
            amount=50.00,
            due_date=5,
            frequency="monthly"
        ),

        # Floating bills
        FloatingBill(
            bill_name="Groceries",
            estimated_amount=600.00,
            due_date=25,  # Estimated due date
            min_amount=500.00,
            max_amount=800.00,
            frequency="monthly"
        ),
        FloatingBill(
            bill_name="Utilities",
            estimated_amount=150.00,
            due_date=20,
            min_amount=100.00,
            max_amount=250.00,
            frequency="monthly"
        ),
    ]

    return [checking_bank, credit_issuer, secondary_bank], [salary, bonus], bills


def main():
    """Run example financial analysis."""

    banks, income_sources, bills = example_setup()

    # Create finance manager
    manager = FinanceManager(banks, income_sources, bills)

    # ========== Generate Reports ==========

    print("=" * 80)
    print("CURRENT FINANCIAL SNAPSHOT")
    print("=" * 80)
    print(manager.generate_snapshot())
    print("\n")

    # Get upcoming bills and income
    print("=" * 80)
    print("UPCOMING BILLS (Next 60 days)")
    print("=" * 80)
    upcoming_bills = manager.get_upcoming_bills(days=60)
    for bill in upcoming_bills:
        next_due = bill.get_next_due_date(date.today() - timedelta(days=1))
        print(f"  {next_due.strftime('%Y-%m-%d')}: {bill.bill_name} - ${bill.amount:.2f}")
    print("\n")

    print("=" * 80)
    print("UPCOMING INCOME (Next 60 days)")
    print("=" * 80)
    upcoming_income = manager.get_upcoming_income(days=60)
    for income in upcoming_income:
        next_pay = income.get_next_pay_date(date.today() - timedelta(days=1))
        print(f"  {next_pay.strftime('%Y-%m-%d')}: {income.source_name} - ${income.amount:.2f}")
    print("\n")

    # Generate payment schedule
    print("=" * 80)
    print("PAYMENT SCHEDULE (Next 90 days)")
    print("=" * 80)
    print(manager.generate_payment_schedule(months=3))
    print("\n")

    # Project balances for 90 days
    print("=" * 80)
    print("90-DAY BALANCE PROJECTION")
    print("=" * 80)
    end_date = date.today() + timedelta(days=180)
    result = manager.project_balances(start_date=date.today(), end_date=end_date)

    print(f"\nStarting date: {date.today()}")
    print(f"Ending date: {end_date}")
    print(f"\nFinal Account Balances:")
    for account_name, balance in sorted(result["final_balances"].items()):
        print(f"  {account_name}: ${balance:,.2f}")

    # Cash flow summary
    income_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "INCOME")
    expense_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "BILL_PAYMENT")

    print(f"\nCash Flow Summary:")
    print(f"  Total Income: ${income_total:,.2f}")
    print(f"  Total Expenses: ${-expense_total:,.2f}")
    print(f"  Net: ${income_total + expense_total:,.2f}")
    print("\n")

    # Get payment optimization
    print("=" * 80)
    print("PAYMENT OPTIMIZATION (Next 90 days)")
    print("=" * 80)
    optimized_plan = manager.optimize_payments(
        start_date=date.today(),
        end_date=end_date,
        optimization_goal="maximize_discretionary"
    )

    print(f"Optimized Payment Plan:")
    print(f"  Final Discretionary Funds: ${optimized_plan.final_discretionary:,.2f}")
    print(f"  Total Interest Paid: ${optimized_plan.total_interest_paid:,.2f}")
    print(f"  Constraint Violations: {len(optimized_plan.violations)}")

    if optimized_plan.strategy:
        print(f"\n  Recommended Payment Strategy:")
        for bill_name, assignment in optimized_plan.strategy.items():
            print(
                f"    {bill_name}: Pay from {assignment['bank']}/{assignment['account']} "
                f"on {assignment['date'].strftime('%Y-%m-%d')}"
            )

    if optimized_plan.violations:
        print(f"\n  Issues Detected:")
        for violation in optimized_plan.violations:
            print(f"    - {violation}")
    print("\n")

    # Generate detailed projection report
    print("=" * 80)
    print("DETAILED PROJECTION REPORT")
    print("=" * 80)
    print(manager.generate_projection_report(
        start_date=date.today(),
        end_date=end_date,
        include_optimization=True
    ))


if __name__ == "__main__":
    main()

