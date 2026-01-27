# Personal Finance Management System

A comprehensive Python-based personal finance management system designed to model your financial situation, project future balances, and optimize payment strategies to maximize discretionary funds.

## Features

### 🏦 Bank & Account Management
- Multiple banks with different account types (checking, savings)
- Support for credit card accounts with credit limits and APR
- Transaction history tracking
- Interest accrual on savings accounts and credit cards
- Balance aggregation across accounts

### 💰 Income Management
- Support for multiple recurring income sources
- Flexible distribution across accounts (fixed amounts or percentages)
- Configurable payment dates and frequencies
- Income history tracking

### 📋 Bill Management
- Fixed bills (same amount every period)
- Floating bills (variable amounts with estimated ranges)
- Multiple payment frequencies (daily, weekly, biweekly, monthly, quarterly, yearly)
- Flexible assignment of payment sources
- Bill payment history

### 📊 Financial Analysis
- **Balance Projections**: See projected account balances on any future date
- **Cash Flow Forecasting**: Detailed transaction predictions
- **Payment Optimization**: Intelligent algorithm to maximize discretionary funds
- **Timeline Simulation**: Day-by-day account balance tracking
- **Critical Date Tracking**: Identify all upcoming financial events
- **What-If Analysis**: Compare different payment strategies

### 📈 Reporting
- Current financial snapshot
- Multi-month projection reports
- Day-by-day detailed timelines
- Budget analysis by month
- Payment schedules
- Constraint violation detection (overdrafts, etc.)

## Installation

### Prerequisites
- Python 3.13+
- No external dependencies (uses only Python standard library)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd budget

# Create virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# No additional packages needed!
```

## Quick Start

### Basic Example
```python
from datetime import date, timedelta
from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.finance_manager import FinanceManager

# Create a bank
bank = Bank("My Bank")
bank.add_account("checking", "Checking", starting_balance=2500.00)
bank.add_account("savings", "Savings", starting_balance=10000.00, interest_rate=4.5)

# Create income
salary = IncomeSource(
    source_name="Monthly Salary",
    amount=5000.00,
    frequency="monthly",
    pay_date=1,
    distribution={"Checking": 3500.00, "Savings": "remainder"}
)

# Create bills
rent = Bill("Rent", 1500.00, due_date=1, frequency="monthly")
utilities = Bill("Utilities", 150.00, due_date=15, frequency="monthly")

# Create manager and analyze
manager = FinanceManager([bank], [salary], [rent, utilities])

# Get balance in 30 days
balance = manager.get_balance_on_date(date.today() + timedelta(days=30))
print(f"Balance in 30 days: {balance}")

# See cash flow
cash_flow = manager.forecast_cash_flow(
    end_date=date.today() + timedelta(days=90)
)
for item in cash_flow:
    print(f"{item['date']}: {item['type']} - {item['description']} (${item['amount']:.2f})")

# Optimize payment strategy
plan = manager.optimize_payments(
    end_date=date.today() + timedelta(days=90)
)
print(f"Optimized discretionary funds: ${plan.final_discretionary:.2f}")
```

### Credit Cards
```python
# Create a credit card issuer
amex = Bank("American Express", bank_type="credit_issuer")
amex.add_credit_account(
    account_name="Business Card",
    credit_limit=15000.00,
    interest_rate=18.5,  # APR
    payment_due_date=20,
    statement_date=15
)

# Make a purchase
amex.credit_accounts["Business Card"].make_purchase(500.00)

# Add to manager for balance projections
manager = FinanceManager([bank, amex], [salary], bills)
```

### Multi-Bank Setup
```python
# Traditional bank
chase = Bank("Chase", bank_type="traditional")
chase.add_account("checking", "Main", 2500.00)
chase.add_account("savings", "Emergency Fund", 10000.00, interest_rate=4.5)

# Wells Fargo
wf = Bank("Wells Fargo", bank_type="traditional")
wf.add_account("savings", "Vacation Fund", 5000.00, interest_rate=3.0)

# Credit card issuer
amex = Bank("American Express", bank_type="credit_issuer")
amex.add_credit_account("Amex", 15000.00, 18.5, payment_due_date=20)

# Set up income to split between banks
salary = IncomeSource(
    "Salary",
    5000.00,
    "monthly",
    1,
    {
        "Main": 3500.00,
        "Emergency Fund": 1000.00,
        "Vacation Fund": 500.00
    }
)

# Manage it all with one manager
manager = FinanceManager([chase, wf, amex], [salary], bills)
```

## Key Concepts

### Income Distribution
Income can be distributed using fixed amounts or percentages:

```python
# Fixed amounts
distribution = {
    "Checking": 3500.00,
    "Savings": 1000.00,
    "Vacation": "remainder"  # Gets whatever is left
}

# Percentages
distribution = {
    "Checking": 0.7,   # 70%
    "Savings": 0.3     # 30%
}
```

### Bill Payment Sources
Bills can specify preferred payment sources:

```python
rent = Bill(
    "Rent",
    1500.00,
    due_date=1,
    preferred_source_bank="Chase",
    preferred_source_account="Checking"
)
```

If the preferred account doesn't have funds, the system automatically finds an account that does.

### Payment Optimization
The optimizer analyzes your income cycle (time between income deposits) and strategically assigns bills to accounts to:
1. **Maximize discretionary funds** - Keep the most liquid cash available
2. **Minimize interest** - Avoid carrying balances on high-APR accounts
3. **Preserve flexibility** - Keep high-balance accounts intact when possible

```python
# Get optimized strategy
plan = manager.optimize_payments(
    end_date=date.today() + timedelta(days=90),
    optimization_goal="maximize_discretionary"
)

print(f"Discretionary funds available: ${plan.final_discretionary:.2f}")
print(f"Strategy violations: {plan.violations}")
```

## API Reference

### FinanceManager (Main Interface)
```python
# Projections
manager.project_balances(start_date, end_date, payment_strategy)
manager.get_balance_on_date(target_date, bank_name, account_name)
manager.forecast_cash_flow(start_date, end_date)
manager.get_critical_dates(months)

# Optimization
manager.optimize_payments(start_date, end_date, optimization_goal)
manager.get_multiple_strategies(start_date, end_date, num_strategies)

# Management
manager.assign_bill_payment_source(bill_name, bank_name, account_name)
manager.set_income_distribution(income_name, distribution)
manager.get_upcoming_bills(days)
manager.get_upcoming_income(days)

# Queries
manager.get_account_balance(bank_name, account_name)
manager.get_total_assets()
manager.get_total_liabilities()
manager.get_net_worth()

# Reporting
manager.generate_snapshot()
manager.generate_projection_report(start_date, end_date, include_optimization)
manager.generate_detailed_timeline(start_date, end_date, payment_strategy)
manager.generate_budget_analysis(months)
manager.generate_payment_schedule(months)
```

### Bank
```python
bank = Bank(name, bank_type="traditional")
bank.add_account(account_type, account_name, starting_balance, interest_rate)
bank.add_credit_account(account_name, credit_limit, interest_rate, payment_due_date)
bank.get_account(account_name)
bank.get_credit_account(account_name)
bank.total_balance()
bank.total_credit_owed()
bank.total_available_credit()
```

### Bill
```python
bill = Bill(
    bill_name,
    amount,
    due_date,  # 1-31
    bill_type="fixed",
    frequency="monthly",
    preferred_source_bank,
    preferred_source_account
)
bill.get_next_due_date(reference_date)
bill.mark_paid(source_bank, source_account, amount_paid, payment_date)
```

### IncomeSource
```python
income = IncomeSource(
    source_name,
    amount,
    frequency="monthly",
    pay_date,  # 1-31
    distribution={}
)
income.get_next_pay_date(reference_date)
income.deposit_to_bank(bank, override_distribution, deposit_date)
```

## Examples

### Example 1: Simple Projection
```python
# Project 90 days forward
result = manager.project_balances(
    end_date=date.today() + timedelta(days=90)
)

print("Final Balances:")
for account, balance in result["final_balances"].items():
    print(f"  {account}: ${balance:.2f}")

print("\nCash Flow Summary:")
income_total = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "INCOME")
expenses = sum(cf["amount"] for cf in result["cash_flow"] if cf["type"] == "BILL_PAYMENT")
print(f"  Total Income: ${income_total:.2f}")
print(f"  Total Expenses: ${-expenses:.2f}")
print(f"  Net Change: ${income_total + expenses:.2f}")
```

### Example 2: What-If Analysis
```python
# Compare two different payment strategies
strategies = manager.get_multiple_strategies(
    end_date=date.today() + timedelta(days=90),
    num_strategies=3
)

for i, strategy in enumerate(strategies, 1):
    print(f"Strategy {i}:")
    print(f"  Discretionary funds: ${strategy.final_discretionary:.2f}")
    print(f"  Interest paid: ${strategy.total_interest_paid:.2f}")
    print(f"  Violations: {len(strategy.violations)}")
    print()
```

### Example 3: Generate Reports
```python
# Current snapshot
print(manager.generate_snapshot())
print()

# Payment schedule for next 2 months
print(manager.generate_payment_schedule(months=2))
print()

# Detailed 30-day timeline
print(manager.generate_detailed_timeline(
    end_date=date.today() + timedelta(days=30)
))
```

## Design Philosophy

1. **Separation of Concerns**: Each component has a clear responsibility
2. **Immutability in Simulations**: Deep copies prevent state mutation during projections
3. **Flexibility**: Accounts, bills, and income are highly configurable
4. **Accuracy**: Simulations match real-world banking behavior (interest dates, payment due dates)
5. **User-Friendly**: High-level manager API for common tasks

## Limitations & Future Work

### Current Limitations
- Simple recurrence patterns (no complex schedules like "every other Friday")
- No GUI or API layer
- No persistent storage (in-memory only)
- No tax-advantaged account special handling
- No overdraft fees or late payment penalties

### Planned Features
1. **Advanced Recurrence**: Support for complex patterns via `dateutil.rrule`
2. **Persistence**: JSON/YAML serialization and database support
3. **Web API**: RESTful interface for external integrations
4. **GUI**: Web-based dashboard with visualizations
5. **Notifications**: Email/SMS alerts for critical events
6. **Tax Planning**: Tracking for 401k, IRA, HSA, etc.
7. **Goal Tracking**: Set and monitor financial goals
8. **Analytics**: Charts, trends, and forecasting improvements

## Testing

Run tests:
```bash
pytest tests/
```

Run example:
```bash
python example.py
```

## Architecture Overview

For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

### Component Diagram
```
FinanceManager (Orchestrator)
    ├── TimelineSimulator (Projects balances forward)
    ├── PaymentOptimizer (Optimizes payment strategy)
    └── FinancialReport (Generates reports)

Domain Models:
    ├── Bank (Container for accounts)
    │   ├── BankAccount (Checking/Savings)
    │   └── CreditAccount (Credit cards)
    ├── Bill (Fixed/Floating expenses)
    └── IncomeSource (Recurring income)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

[Your License Here]

## Support

For questions or issues:
1. Check the [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation
2. Review the [example.py](example.py) for usage examples
3. Create an issue on GitHub

## Changelog

### v0.1.0 (Current)
- Initial release
- Core domain models (Bank, Account, Bill, Income)
- Timeline simulation engine
- Payment optimization algorithm
- Financial reporting
- Comprehensive documentation

---

**Start planning your finances with confidence!** 💪💰

