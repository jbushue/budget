# Personal Finance Management System - Test Suite

This directory contains a comprehensive test suite for the personal finance management system. The tests cover all major components and functionality.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared fixtures and configuration
├── test_bank.py             # Bank and account management tests
├── test_bills.py            # Bill management tests (including yearly/semi-annual)
├── test_income.py           # Income source tests
├── test_timeline.py         # Timeline simulator tests
├── test_optimizer.py        # Payment optimizer tests
├── test_data_import_export.py # Import/export functionality tests
├── test_finance_manager.py  # Integration and high-level tests
├── test_mortgage.py         # Mortgage account tests
├── test_credit.py           # Credit card account tests
└── test_promos.py           # Promotional offers tests
```

## Running Tests

### Run All Tests
```bash
# From project root
python run_tests.py

# Or using pytest directly
pytest
```

### Run Specific Test File
```bash
# Run specific test file
python run_tests.py test_bank.py

# Or using pytest
pytest tests/test_bank.py
```

### Run Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Run with coverage
pytest --cov=. --cov-report=html
```

### Run Tests with Different Output
```bash
# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show coverage in terminal
pytest --cov=. --cov-report=term-missing
```

## Test Categories

### Unit Tests (`-m unit`)
- Test individual components in isolation
- Mock external dependencies
- Fast execution
- Examples: `test_bank.py`, `test_bills.py`

### Integration Tests (`-m integration`)
- Test component interactions
- Use real dependencies
- Slower execution
- Examples: `test_finance_manager.py`, `test_data_import_export.py`

## Key Test Features

### 1. **Comprehensive Coverage**
- **Banks & Accounts**: Traditional, credit, mortgage accounts
- **Bills**: Monthly, yearly, semi-annual with due_month support
- **Income**: Multiple frequencies and distribution
- **Timeline Simulation**: Event generation and balance projection
- **Payment Optimization**: Strategy generation and constraint checking
- **Data Import/Export**: Excel template generation and round-trip testing
- **Promotional Offers**: Creation, expiration, and payoff prioritization

### 2. **Real-World Scenarios**
- Yearly bills (Property Tax on April 15th)
- Semi-annual bills (Car Insurance Jan/Jul)
- Credit card promotional offers
- Mortgage payment calculations
- Multi-bank account management

### 3. **Edge Cases**
- Month-end dates (Feb 31st → Feb 28th)
- Leap years
- Overdraft protection
- Credit limits
- Promo expiration

### 4. **Integration Testing**
- Full finance manager workflows
- Cross-component interactions
- Data persistence and round-trip operations

## Test Fixtures

### Shared Fixtures (`conftest.py`)
- `sample_bank`: Traditional bank with checking/savings
- `sample_credit_bank`: Bank with credit card
- `sample_mortgage_bank`: Bank with mortgage
- `sample_bills`: Mix of monthly, yearly, semi-annual bills
- `sample_income`: Multiple income sources
- `sample_finance_manager`: Complete setup with all components
- `sample_date_range`: Standard 3-month test period

## Test Examples

### Testing Yearly Bills
```python
def test_yearly_bill_due_dates():
    bill = Bill("Property Tax", 2400, 15, due_month=4, frequency=BillFrequency.YEARLY)

    # Test due date calculation
    reference = date(2024, 3, 10)
    next_due = bill.get_next_due_date(reference)
    assert next_due == date(2024, 4, 15)  # April 15th
```

### Testing Timeline Simulation
```python
def test_timeline_with_yearly_bills(sample_bank):
    yearly_bill = Bill("Tax", 1200, 15, due_month=4, frequency=BillFrequency.YEARLY)
    simulator = TimelineSimulator([sample_bank], [], [yearly_bill])

    events = simulator.build_timeline(date(2024, 4, 1), date(2024, 4, 30))
    bill_events = [e for e in events if e.event_type == "BILL_DUE"]

    assert len(bill_events) == 1
    assert bill_events[0].event_date == date(2024, 4, 15)
```

### Testing Payment Optimization
```python
def test_optimize_with_yearly_bills(sample_finance_manager):
    manager = sample_finance_manager
    optimizer = PaymentOptimizer(manager.banks, manager.income_sources, manager.bills)

    plan = optimizer.optimize_payment_schedule(date(2024, 3, 1), date(2024, 5, 31))

    # Should include yearly bills in strategy
    assert len(plan.strategy) > 0
    assert plan.final_discretionary >= 0
```

## Coverage Requirements

- **Minimum Coverage**: 80%
- **Target Coverage**: 90%+
- **Critical Paths**: All bill frequency calculations, payment optimization logic

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: |
    python run_tests.py
```

## Adding New Tests

### 1. Create Test File
```python
# tests/test_new_feature.py
import pytest
from models.new_feature import NewFeature

class TestNewFeature:
    def test_basic_functionality(self):
        feature = NewFeature()
        assert feature.do_something() == "expected"
```

### 2. Add Fixtures (if needed)
```python
# In conftest.py or test file
@pytest.fixture
def new_feature_fixture():
    return NewFeature()
```

### 3. Mark Test Categories
```python
@pytest.mark.unit
def test_unit_test():
    pass

@pytest.mark.integration
def test_integration_test():
    pass
```

## Test Data

### Sample Financial Setup
- **Banks**: Chase (checking/savings), Amex (credit), Wells Fargo (mortgage)
- **Accounts**: $5k checking, $10k savings, $10k credit limit, $300k mortgage
- **Income**: $5k monthly salary, $1k quarterly bonus
- **Bills**: Rent ($2k), Internet ($80), Property Tax ($2.4k yearly), Car Insurance ($1.2k semi-annual)
- **Time Period**: 3-month analysis windows

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're in the project root directory
2. **Missing Dependencies**: Run `pip install -e .[dev]`
3. **Test Timeouts**: Some integration tests may take longer
4. **Coverage Issues**: Check which lines aren't covered

### Debug Commands
```bash
# Run single test with debug output
pytest tests/test_bank.py::TestBank::test_bank_creation -v -s

# Run with coverage for specific file
pytest tests/test_bank.py --cov=models.bank --cov-report=html

# Profile slow tests
pytest --durations=10
```

## Contributing

When adding new features:

1. **Add corresponding tests** in the appropriate test file
2. **Update fixtures** if new sample data is needed
3. **Ensure coverage** stays above 80%
4. **Test edge cases** and error conditions
5. **Update this README** if test structure changes

## Test Statistics

- **Total Test Files**: 10
- **Test Classes**: ~50
- **Individual Tests**: ~200+
- **Lines of Test Code**: ~3000+
- **Coverage Target**: 90%+

The test suite provides comprehensive validation of the personal finance management system's functionality, ensuring reliability and correctness across all components and use cases.
