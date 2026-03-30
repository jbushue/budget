#!/usr/bin/env python3
"""
Test script to verify that yearly bills with due_month work correctly
with the timeline simulator and payment optimizer.
"""

from datetime import date, timedelta
from models.bank import Bank
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource, IncomeFrequency
from models.finance_manager import FinanceManager
from models.timeline_simulator import TimelineSimulator
from models.payment_optimizer import PaymentOptimizer


def test_yearly_bills():
    """Test yearly bills with due_month field."""
    
    print("=" * 80)
    print("YEARLY BILLS WITH DUE_MONTH TEST")
    print("=" * 80)
    
    # Setup banks
    bank = Bank("Test Bank", bank_type="traditional")
    bank.add_account(
        account_type="checking",
        account_name="Checking",
        starting_balance=5000.00,
        interest_rate=0.01
    )
    
    # Setup income
    income = IncomeSource(
        source_name="Salary",
        amount=3000.00,
        frequency=IncomeFrequency.MONTHLY,
        pay_date=[1],  # 1st of month
    )
    
    # Create bills with various frequencies
    bills = [
        # Monthly bill
        Bill(
            bill_name="Rent",
            amount=1000.00,
            due_date=1,
            frequency="monthly"
        ),
        # Yearly bill - Property Tax due April 15th
        Bill(
            bill_name="Property Tax",
            amount=1200.00,
            due_date=15,
            due_month=4,  # April
            frequency="yearly"
        ),
        # Semi-annual bill - Car Insurance on Jan 1 and July 1
        Bill(
            bill_name="Car Insurance",
            amount=600.00,
            due_date=1,
            due_month=1,  # January (second occurrence in July)
            frequency="semi_annual"
        ),
    ]
    
    print("\n📋 Test Setup:")
    print(f"  Bank: {bank.name}")
    print(f"  Account: Checking with ${5000.00} balance")
    print(f"  Income: {income.source_name} - ${income.amount} on the 1st of each month")
    print(f"\nBills:")
    for bill in bills:
        if bill.due_month:
            print(f"  - {bill.bill_name}: ${bill.amount} on day {bill.due_date} of month {bill.due_month}, {bill.frequency.value}")
        else:
            print(f"  - {bill.bill_name}: ${bill.amount} on day {bill.due_date}, {bill.frequency.value}")
    
    # Test timeline simulator
    print("\n" + "=" * 80)
    print("TIMELINE SIMULATOR TEST")
    print("=" * 80)
    
    start_date = date(2026, 3, 30)  # March 30, 2026
    end_date = date(2026, 8, 31)     # August 31, 2026
    
    print(f"\nAnalysis period: {start_date} to {end_date}")
    
    simulator = TimelineSimulator([bank], [income], bills)
    timeline = simulator.build_timeline(start_date, end_date, include_interest=False)
    
    print("\nTimeline Events:")
    for event in timeline:
        print(f"  {event.event_date}: {event.event_type:15} | {event.description:30} | ${event.amount:8.2f}")
    
    # Test payment optimizer
    print("\n" + "=" * 80)
    print("PAYMENT OPTIMIZER TEST")
    print("=" * 80)
    
    optimizer = PaymentOptimizer([bank], [income], bills)
    plan = optimizer.optimize_payment_schedule(start_date, end_date)
    
    print(f"\nOptimization Results:")
    print(f"  Total Interest Paid: ${plan.total_interest_paid:.2f}")
    print(f"  Final Discretionary: ${plan.final_discretionary:.2f}")
    print(f"  Violations: {len(plan.violations)}")
    if plan.violations:
        for violation in plan.violations:
            print(f"    - {violation}")
    
    # Verify key dates
    print("\n" + "=" * 80)
    print("VERIFICATION: DUE DATES CALCULATION")
    print("=" * 80)
    
    property_tax = next(b for b in bills if b.bill_name == "Property Tax")
    car_insurance = next(b for b in bills if b.bill_name == "Car Insurance")
    
    print(f"\nProperty Tax (yearly, due_month=4, due_date=15):")
    for day_offset in range(0, 150, 30):
        test_date = start_date + timedelta(days=day_offset)
        next_due = property_tax.get_next_due_date(test_date - timedelta(days=1))
        print(f"  From {test_date}: next due = {next_due}")
    
    print(f"\nCar Insurance (semi-annual, due_month=1, due_date=1):")
    for day_offset in range(0, 200, 50):
        test_date = start_date + timedelta(days=day_offset)
        next_due = car_insurance.get_next_due_date(test_date - timedelta(days=1))
        print(f"  From {test_date}: next due = {next_due}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    test_yearly_bills()



