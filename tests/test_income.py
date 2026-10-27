"""
Tests for income source functionality.
"""

import pytest
from datetime import date, timedelta
from models.income_source import IncomeSource, IncomeFrequency


class TestIncomeSource:
    """Test IncomeSource class functionality."""

    def test_monthly_income_creation(self):
        """Test creating a monthly income source."""
        income = IncomeSource(
            source_name="Salary",
            amount=5000.00,
            frequency=IncomeFrequency.MONTHLY,
            pay_date=[1, 15]  # Semimonthly
        )

        assert income.source_name == "Salary"
        assert income.amount == 5000.00
        assert income.frequency == IncomeFrequency.MONTHLY
        assert income.pay_date == [1, 15]

    def test_income_validation(self):
        """Test income validation."""
        # Invalid amount
        with pytest.raises(ValueError, match="Income amount must be positive"):
            IncomeSource("Test", -100)

    def test_income_frequencies(self):
        """Test different income frequencies."""
        # Weekly
        weekly = IncomeSource("Weekly Pay", 1000, IncomeFrequency.WEEKLY, [1])
        assert weekly.frequency == IncomeFrequency.WEEKLY

        # Biweekly
        biweekly = IncomeSource("Biweekly Pay", 2000, IncomeFrequency.BIWEEKLY, [1])
        assert biweekly.frequency == IncomeFrequency.BIWEEKLY

        # Semimonthly
        semimonthly = IncomeSource("Semimonthly Pay", 2500, IncomeFrequency.SEMIMONTHLY, [1, 15])
        assert semimonthly.frequency == IncomeFrequency.SEMIMONTHLY

        # Quarterly
        quarterly = IncomeSource("Quarterly Bonus", 5000, IncomeFrequency.QUARTERLY, [1])
        assert quarterly.frequency == IncomeFrequency.QUARTERLY

        # Yearly
        yearly = IncomeSource("Annual Bonus", 10000, IncomeFrequency.YEARLY, [1])
        assert yearly.frequency == IncomeFrequency.YEARLY

    def test_get_pay_dates_monthly(self):
        """Test getting pay dates for monthly income."""
        income = IncomeSource("Monthly Salary", 5000, IncomeFrequency.MONTHLY, [15])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        expected_dates = [
            date(2024, 1, 15),
            date(2024, 2, 15),
            date(2024, 3, 15)
        ]

        assert pay_dates == expected_dates

    def test_get_pay_dates_semimonthly(self):
        """Test getting pay dates for semimonthly income."""
        income = IncomeSource("Semimonthly Pay", 2500, IncomeFrequency.SEMIMONTHLY, [1, 15])

        # get_pay_dates_in_range uses exclusive start, inclusive end
        # So we start before the first pay date we want
        start_date = date(2023, 12, 31)  # Before Jan 1
        end_date = date(2024, 1, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        expected_dates = [
            date(2024, 1, 1),
            date(2024, 1, 15)
        ]

        assert pay_dates == expected_dates

    # NOTE: the four tests below previously encoded a bug where weekly,
    # biweekly, quarterly and yearly income were paid on pay_date every month.
    # They now assert real frequency handling. Without a start_date the cycle
    # is anchored on the first pay_date day after the first queried date.

    def test_get_pay_dates_weekly(self):
        """Weekly income is paid every 7 days from the (implicit) anchor."""
        income = IncomeSource("Weekly Pay", 1000, IncomeFrequency.WEEKLY, [15])

        start_date = date(2023, 12, 31)  # Exclusive start
        end_date = date(2024, 3, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        # Anchored at Mon Jan 15 2024, then every Monday
        assert pay_dates[0] == date(2024, 1, 15)
        assert len(pay_dates) == 11
        assert all((b - a).days == 7 for a, b in zip(pay_dates, pay_dates[1:]))

    def test_get_pay_dates_biweekly(self):
        """Biweekly income is paid every 14 days from the (implicit) anchor."""
        income = IncomeSource("Biweekly Pay", 2000, IncomeFrequency.BIWEEKLY, [15])

        start_date = date(2023, 12, 31)  # Exclusive start
        end_date = date(2024, 2, 28)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        assert pay_dates == [date(2024, 1, 15), date(2024, 1, 29),
                             date(2024, 2, 12), date(2024, 2, 26)]

    def test_get_pay_dates_quarterly(self):
        """Quarterly income is paid every 3 months."""
        income = IncomeSource("Quarterly Bonus", 5000, IncomeFrequency.QUARTERLY, [15])

        start_date = date(2023, 12, 31)  # Exclusive start
        end_date = date(2024, 12, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        assert pay_dates == [date(2024, 1, 15), date(2024, 4, 15),
                             date(2024, 7, 15), date(2024, 10, 15)]

    def test_get_pay_dates_yearly(self):
        """Yearly income is paid once a year."""
        income = IncomeSource("Annual Bonus", 10000, IncomeFrequency.YEARLY, [15])

        start_date = date(2023, 12, 31)  # Exclusive start
        end_date = date(2024, 3, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        assert pay_dates == [date(2024, 1, 15)]

    def test_weekend_adjustment(self):
        """Test that pay dates falling on weekends are adjusted."""
        # Create income with pay date on 6th
        # January 6, 2024 is a Saturday
        income = IncomeSource("Saturday Pay", 1000, IncomeFrequency.MONTHLY, [6])

        # Use exclusive start before Jan 6
        start_date = date(2024, 1, 1)  # Before Jan 6
        end_date = date(2024, 1, 31)

        pay_dates = income.get_pay_dates_in_range(start_date, end_date)

        # Jan 6, 2024 is Saturday, should be adjusted to Friday Jan 5
        assert len(pay_dates) == 1
        assert pay_dates[0] == date(2024, 1, 5)  # Friday
        assert pay_dates[0].weekday() == 4  # Friday

    def test_income_deposit_to_bank(self):
        """Test depositing income to a bank account."""
        from models.bank import Bank

        # Create bank and income
        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 1000.00)

        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, [1])

        # Deposit income - returns dict {account_name: amount}
        deposits = income.deposit_to_bank(bank, deposit_date=date(2024, 1, 1))

        assert len(deposits) == 1
        assert "Checking" in deposits
        assert deposits["Checking"] == 5000.00
        assert bank.accounts["Checking"].balance == 6000.00

    def test_income_deposit_distribution(self):
        """Test income distribution across multiple accounts."""
        from models.bank import Bank

        # Create bank with multiple accounts
        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 1000.00)
        bank.add_account("savings", "Savings", 2000.00)

        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, [1])

        # Deposit with distribution
        deposits = income.deposit_to_bank(
            bank,
            {"Checking": 3000.00, "Savings": 2000.00},
            date(2024, 1, 1)
        )

        assert len(deposits) == 2
        assert bank.accounts["Checking"].balance == 4000.00  # 1000 + 3000
        assert bank.accounts["Savings"].balance == 4000.00    # 2000 + 2000

    def test_income_deposit_invalid_account(self):
        """Test depositing to non-existent account."""
        from models.bank import Bank

        bank = Bank("Test Bank")
        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, [1])

        with pytest.raises(ValueError, match="Account 'NonExistent' does not exist"):
            income.deposit_to_bank(
                bank,
                {"NonExistent": 5000.00},
                date(2024, 1, 1)
            )

    def test_income_copy(self):
        """Test copying an income source."""
        original = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, [1, 15])
        copy = original.copy()

        assert copy.source_name == original.source_name
        assert copy.amount == original.amount
        assert copy.frequency == original.frequency
        assert copy.pay_date == original.pay_date
        assert copy is not original

    def test_income_string_representation(self):
        """Test income string representation."""
        income = IncomeSource("Monthly Salary", 5000, IncomeFrequency.MONTHLY, [1])
        str_repr = str(income)

        assert "Monthly Salary" in str_repr
        assert "$5000.00" in str_repr
        assert "monthly" in str_repr


class TestIncomeIntegration:
    """Test income integration with other components."""

    def test_income_with_finance_manager(self, sample_finance_manager):
        """Test income integration with finance manager."""
        manager = sample_finance_manager

        # Should have income sources
        assert len(manager.income_sources) > 0

        # Test getting all income
        all_income = manager.get_all_income_sources()
        assert len(all_income) > 0

    def test_multiple_income_sources(self):
        """Test managing multiple income sources."""
        from models.finance_manager import FinanceManager
        from models.bank import Bank

        # Create bank
        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 1000.00)

        # Create multiple income sources
        incomes = [
            IncomeSource("Primary Salary", 5000, IncomeFrequency.MONTHLY, [1]),
            IncomeSource("Side Gig", 1000, IncomeFrequency.WEEKLY, [5]),
            IncomeSource("Quarterly Bonus", 2000, IncomeFrequency.QUARTERLY, [15])
        ]

        manager = FinanceManager([bank], incomes, [])

        # Test pay date calculation across all sources
        # Use exclusive start (day before) to include Jan 1
        start_date = date(2023, 12, 31)
        end_date = date(2024, 1, 31)

        all_pay_dates = []
        for income in manager.income_sources:
            pay_dates = income.get_pay_dates_in_range(start_date, end_date)
            all_pay_dates.extend([(income.source_name, d) for d in pay_dates])

        # Should have multiple pay dates in January
        assert len(all_pay_dates) > 0

        # Primary salary should pay on Jan 1
        primary_dates = [d for name, d in all_pay_dates if name == "Primary Salary"]
        assert date(2024, 1, 1) in primary_dates

    def test_income_history_tracking(self):
        """Test income deposit history tracking."""
        from models.bank import Bank

        bank = Bank("Test Bank")
        bank.add_account("checking", "Checking", 1000.00)

        income = IncomeSource("Salary", 5000, IncomeFrequency.MONTHLY, [1])

        # Make multiple deposits
        income.deposit_to_bank(bank, deposit_date=date(2024, 1, 1))
        income.deposit_to_bank(bank, deposit_date=date(2024, 2, 1))

        assert len(income.deposit_history) == 2

        first_deposit = income.deposit_history[0]
        assert first_deposit["date"] == date(2024, 1, 1)
        assert first_deposit["amount"] == 5000.00
        assert first_deposit["account_name"] == "Checking"

