# Quick Reference Guide

## Setup (5 minutes)

```python
from datetime import date, timedelta
from models.bank import Bank
from models.fixed_bill import Bill, FloatingBill
from models.income_source import IncomeSource
from models.finance_manager import FinanceManager

# 1. Create banks
checking_bank = Bank("Chase Bank")
checking_bank.add_account("checking", "Main Checking", 2500.00)
checking_bank.add_account("savings", "Emergency Fund", 10000.00, interest_rate=4.5)

# 2. Create income
salary = IncomeSource(
    "Salary",
    5000.00,
    "monthly",
    pay_date=1,
    distribution={"Main Checking": 3500.00, "Emergency Fund": "remainder"}
)

# 3. Create bills
rent = Bill("Rent", 1500.00, due_date=1)
utilities = FloatingBill("Utilities", 150.00, due_date=20, min_amount=100, max_amount=250)

# 4. Create manager
manager = FinanceManager([checking_bank], [salary], [rent, utilities])

# Done! Now use it...
```

## Common Tasks

### Get Balance on Specific Date
```python
balance = manager.get_balance_on_date(date(2026, 3, 15))
print(f"Balance: ${balance['Chase Bank:Main Checking']:.2f}")
```

### See 90-Day Projection
```python
result = manager.project_balances(
    start_date=date.today(),
    end_date=date.today() + timedelta(days=90)
)

for account, balance in result["final_balances"].items():
    print(f"{account}: ${balance:,.2f}")
```

### Optimize Payment Strategy
```python
plan = manager.optimize_payments(
    end_date=date.today() + timedelta(days=90)
)

print(f"Discretionary funds: ${plan.final_discretionary:,.2f}")
for bill_name, assignment in plan.strategy.items():
    print(f"Pay {bill_name} from {assignment['bank']}/{assignment['account']}")
```

### Get Cash Flow Details
```python
cash_flow = manager.forecast_cash_flow(
    end_date=date.today() + timedelta(days=90)
)

for transaction in cash_flow:
    if transaction["type"] == "INCOME":
        print(f"✓ {transaction['date']}: +${transaction['amount']:.2f}")
    elif transaction["type"] == "BILL_PAYMENT":
        print(f"✗ {transaction['date']}: -${-transaction['amount']:.2f}")
```

### See Upcoming Bills & Income
```python
bills = manager.get_upcoming_bills(days=30)
for bill in bills:
    due = bill.get_next_due_date(date.today() - timedelta(days=1))
    print(f"{due}: {bill.bill_name} - ${bill.amount:.2f}")

income = manager.get_upcoming_income(days=30)
for inc in income:
    pay_date = inc.get_next_pay_date(date.today() - timedelta(days=1))
    print(f"{pay_date}: {inc.source_name} - ${inc.amount:.2f}")
```

### Generate Reports
```python
# Current snapshot
print(manager.generate_snapshot())

# Projection with optimization
print(manager.generate_projection_report(
    end_date=date.today() + timedelta(days=90)
))

# Payment schedule
print(manager.generate_payment_schedule(months=2))

# Day-by-day timeline
print(manager.generate_detailed_timeline(
    end_date=date.today() + timedelta(days=30)
))

# Budget analysis
print(manager.generate_budget_analysis(months=3))
```

## Modifying Your Setup

### Change Income Distribution
```python
manager.set_income_distribution("Salary", {
    "Main Checking": 0.7,    # 70%
    "Emergency Fund": 0.3    # 30%
})
```

### Assign Bill to Specific Account
```python
manager.assign_bill_payment_source("Rent", "Chase Bank", "Main Checking")
```

### Add New Account
```python
checking_bank.add_account("checking", "Travel Fund", 1000.00)

# Update income to use it
manager.set_income_distribution("Salary", {
    "Main Checking": 3000.00,
    "Emergency Fund": 1000.00,
    "Travel Fund": "remainder"
})
```

### Add Credit Card
```python
amex = Bank("American Express", bank_type="credit_issuer")
amex.add_credit_account(
    "Business Card",
    credit_limit=15000.00,
    interest_rate=18.5,  # APR
    payment_due_date=20,
    statement_date=15
)

# Add to manager
manager.banks.append(amex)
```

### Create Floating Bill
```python
groceries = FloatingBill(
    "Groceries",
    estimated_amount=600.00,
    due_date=25,
    min_amount=500.00,
    max_amount=800.00,
    frequency="monthly"
)
```

## Querying Current State

```python
# Single account balance
balance = manager.get_account_balance("Chase Bank", "Main Checking")

# All balances
assets = manager.get_total_assets()      # Sum of all bank accounts
liabilities = manager.get_total_liabilities()  # Sum of credit debt
net_worth = manager.get_net_worth()      # Assets - Liabilities

# Critical dates
dates = manager.get_critical_dates(months=3)
for critical_date, events in dates.items():
    print(f"{critical_date}:")
    for event in events:
        print(f"  - {event['description']} (${event['amount']:.2f})")
```

## Understanding Results

### project_balances() Returns:
```python
{
    "start_date": date,
    "end_date": date,
    "snapshots": [
        {"date": date, "balances": {"Account": 1000.00}},
        ...
    ],
    "final_balances": {"Account": 1000.00, ...},
    "cash_flow": [
        {
            "date": date,
            "type": "INCOME" | "BILL_PAYMENT" | "INTEREST",
            "description": str,
            "amount": float,
            "account": str,
            "bank": str
        },
        ...
    ],
    "events": [TimelineEvent, ...]
}
```

### optimize_payments() Returns PaymentPlan:
```python
PaymentPlan(
    strategy={
        "Rent": {"bank": "Chase Bank", "account": "Main Checking", "date": date},
        ...
    },
    total_interest_paid=50.00,
    total_fees=0.00,
    final_discretionary=2500.00,  # Cash left after all obligations
    violations=["Account X overdrawn", ...]
)
```

## Common Patterns

### Multi-Bank Setup
```python
chase = Bank("Chase")
chase.add_account("checking", "Main", 2500)
chase.add_account("savings", "Emergency", 10000, interest_rate=4.5)

wf = Bank("Wells Fargo")
wf.add_account("savings", "Vacation", 5000, interest_rate=3.0)

amex = Bank("American Express", bank_type="credit_issuer")
amex.add_credit_account("Amex", 15000, 18.5, payment_due_date=20)

manager = FinanceManager([chase, wf, amex], income_sources, bills)
```

### Percentage-Based Income Split
```python
income = IncomeSource(
    "Salary",
    5000.00,
    "monthly",
    pay_date=1,
    distribution={
        "Checking": 0.6,          # 60%
        "Savings": 0.3,           # 30%
        "Investment": 0.1         # 10%
    }
)
```

### Flexible Distribution with Remainder
```python
income = IncomeSource(
    "Salary",
    5000.00,
    "monthly",
    pay_date=1,
    distribution={
        "Rent Reserve": 1500.00,
        "Bills Reserve": 1000.00,
        "Living Expenses": 1000.00,
        "Savings": "remainder"  # Gets whatever is left
    }
)
```

### Check for Overdrafts
```python
result = manager.project_balances(end_date=date.today() + timedelta(days=90))

overdrafts = []
for account_name, balance in result["final_balances"].items():
    if balance < 0:
        overdrafts.append((account_name, balance))

if overdrafts:
    print("⚠️ WARNING: Overdrafts detected!")
    for account, balance in overdrafts:
        print(f"  {account}: ${balance:.2f}")
else:
    print("✓ All accounts stay positive")
```

### Compare Payment Strategies
```python
strategies = manager.get_multiple_strategies(
    end_date=date.today() + timedelta(days=90),
    num_strategies=3
)

for i, plan in enumerate(strategies, 1):
    print(f"\nStrategy {i}:")
    print(f"  Discretionary: ${plan.final_discretionary:,.2f}")
    print(f"  Interest: ${plan.total_interest_paid:,.2f}")
    print(f"  Issues: {len(plan.violations)}")
```

## Troubleshooting

### "Account doesn't exist"
Check that account name matches exactly (case-sensitive)
```python
# ✗ Wrong
manager.get_balance_on_date(date.today(), "Chase", "main checking")

# ✓ Correct
manager.get_balance_on_date(date.today(), "Chase Bank", "Main Checking")
```

### "No account has sufficient funds"
Use a date-specific query to see balances on that date:
```python
balance = manager.get_balance_on_date(bill_date)
if balance < bill.amount:
    print(f"Insufficient funds on {bill_date}")
```

### Income not distributing correctly
Verify total equals income amount:
```python
distribution = {"Account1": 2000, "Account2": 2000, "Account3": 1000}
total = sum(v for v in distribution.values() if isinstance(v, (int, float)))
# total should be 5000 if income is 5000
# OR use "remainder" for last account
```

### Optimization shows violations
Check constraint violations:
```python
plan = manager.optimize_payments()
for violation in plan.violations:
    print(f"⚠️ {violation}")
```

## Tips & Tricks

1. **Always project forward before making changes**
   ```python
   result = manager.project_balances(end_date=target_date)
   ```

2. **Use the optimizer to stress-test scenarios**
   ```python
   plan = manager.optimize_payments()  # Can the system handle it?
   ```

3. **Generate reports weekly to catch issues early**
   ```python
   print(manager.generate_snapshot())  # Current state
   ```

4. **Compare multiple strategies before deciding**
   ```python
   strategies = manager.get_multiple_strategies(num_strategies=5)
   ```

5. **Track critical dates to never miss a payment**
   ```python
   dates = manager.get_critical_dates(months=1)  # Next month
   for critical_date in sorted(dates.keys()):
       print(critical_date)
   ```

6. **Use floating bills for estimated expenses**
   ```python
   utilities = FloatingBill("Utilities", 150, 20, min=100, max=250)
   ```

7. **Set preferred payment sources as guidelines**
   ```python
   manager.assign_bill_payment_source("Rent", "Chase", "Checking")
   # System will use this if possible, but can override if needed
   ```

8. **Deep copy banks for safe simulations**
   ```python
   from copy import deepcopy
   test_bank = deepcopy(original_bank)
   test_bank.accounts["Checking"].balance -= 500  # Test impact
   ```

## Running Examples

```bash
# Full example with output
python example.py

# Quick system test
python -c "from example import example_setup; from models.finance_manager import FinanceManager; b,i,bl = example_setup(); m = FinanceManager(b,i,bl); print('✓ System working')"

# Interactive Python
python
>>> from models.finance_manager import FinanceManager
>>> # ... create banks, income, bills ...
>>> manager = FinanceManager(banks, income, bills)
>>> manager.generate_snapshot()
```

## Documentation Files

- **README.md** - User guide and features
- **ARCHITECTURE.md** - Detailed system design
- **PROJECT_SUMMARY.md** - What was built and why
- **example.py** - Complete working example

---

**For more details, see the full documentation!** 📚

