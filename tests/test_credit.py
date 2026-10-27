"""
Tests for credit card account functionality.
"""

import pytest
from datetime import date, timedelta
from models.credit_card_account import CreditAccount, PromoOffer
from models.types import CreditAccountStatus


class TestCreditCardAccount:
    """Test CreditCardAccount class functionality."""

    def test_credit_card_creation(self):
        """Test creating a credit card account."""
        card = CreditAccount(
            account_name="Rewards Card",
            credit_limit=10000.00,
            interest_rate=18.5,
            payment_due_date=15,
            statement_date=10
        )

        assert card.account_name == "Rewards Card"
        assert card.credit_limit == 10000.00
        assert card.balance == 0.00
        assert card.interest_rate == 18.5
        assert card.payment_due_date == 15
        assert card.statement_date == 10
        assert card.status == CreditAccountStatus.ACTIVE

    def test_credit_charge(self):
        """Test charging to a credit card."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=5000.00,
            interest_rate=15.0
        )

        # Charge amount
        card.make_purchase(1000.00, description="Test purchase")

        assert card.balance == 1000.00
        assert len(card.transaction_history) == 1
        assert card.transaction_history[0]["amount"] == 1000.00
        assert card.transaction_history[0]["description"] == "Test purchase"

    def test_credit_payment(self):
        """Test making payments on a credit card."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=5000.00,
            interest_rate=15.0
        )

        # Charge and pay
        card.make_purchase(1000.00)
        card.make_payment(600.00, description="Test payment")

        assert card.balance == 400.00
        assert len(card.transaction_history) == 2

    def test_credit_over_limit(self):
        """Test charging over credit limit."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=1000.00,
            interest_rate=15.0
        )

        with pytest.raises(ValueError, match="exceeds available credit"):
            card.make_purchase(1500.00)

        assert card.balance == 0.00  # Should remain unchanged

    def test_credit_interest_accrual(self):
        """Test interest accrual on credit card."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=5000.00,
            interest_rate=24.0,  # High rate for testing
            statement_date=15
        )

        # Charge and trigger interest accrual
        card.make_purchase(1000.00)
        card.accrue_interest()

        # Should accrue interest
        monthly_rate = 24.0 / 12 / 100
        expected_interest = 1000.00 * monthly_rate

        assert card.balance == 1000.00 + expected_interest
        assert len(card.transaction_history) == 2  # Charge + interest

    def test_credit_minimum_payment_calculation(self):
        """Test minimum payment calculation."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=10000.00,
            interest_rate=18.5
        )

        # With no balance, minimum payment should be 0
        assert card.calculate_minimum_payment() == 0.00

        # With balance
        card.make_purchase(2000.00)
        min_payment = card.calculate_minimum_payment()

        # Should be at least 2% of balance or $25, whichever is greater
        expected_min = max(2000.00 * 0.02, 25.00)
        assert min_payment == expected_min

    def test_credit_available_credit(self):
        """Test available credit calculation."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=5000.00,
            interest_rate=15.0
        )

        assert card.available_credit == 5000.00

        card.make_purchase(1500.00)
        assert card.available_credit == 3500.00

    def test_credit_copy(self):
        """Test copying a credit card account."""
        original = CreditAccount(
            account_name="Original Card",
            credit_limit=10000.00,
            interest_rate=18.5,
            payment_due_date=15,
            statement_date=10
        )

        original.make_purchase(1000.00)

        copy = original.copy()

        assert copy.account_name == original.account_name
        assert copy.balance == original.balance
        assert copy.credit_limit == original.credit_limit
        assert copy is not original

    def test_credit_string_representation(self):
        """Test credit card string representation."""
        card = CreditAccount(
            account_name="Rewards Card",
            credit_limit=10000.00,
            interest_rate=18.5
        )

        card.make_purchase(2500.00)

        str_repr = str(card)
        assert "Rewards Card" in str_repr
        assert "$2500.00" in str_repr
        assert "$10000.00" in str_repr


class TestPromotionalOffers:
    """Test promotional offer functionality."""

    def test_promo_offer_creation(self):
        """Test creating a promotional offer."""
        promo = PromoOffer(
            promo_name="0% APR for 12 months",
            months_interest_free=12,
            purchase_limit=2000.00
        )

        assert promo.promo_name == "0% APR for 12 months"
        assert promo.months_interest_free == 12
        assert promo.purchase_limit == 2000.00
        assert promo.is_active

    def test_promo_offer_expiration(self):
        """Test promotional offer expiration."""
        # Create a promo that started 30 days ago with 1 month duration
        start_date = date.today() - timedelta(days=30)
        promo = PromoOffer(
            promo_name="Expired Promo",
            months_interest_free=1,
            purchase_limit=1000.00,
            start_date=start_date
        )

        assert not promo.is_active

    def test_promo_offer_days_remaining(self):
        """Test calculating days remaining on promo."""
        # Create a promo with 2 months duration
        promo = PromoOffer(
            promo_name="Test Promo",
            months_interest_free=2,
            purchase_limit=1000.00
        )

        # Should have approximately 60 days remaining
        assert 50 <= promo.days_remaining <= 60

    def test_promo_offer_string_representation(self):
        """Test promotional offer string representation."""
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00
        )

        str_repr = str(promo)
        assert "0% APR" in str_repr
        assert "12 months" in str_repr
        assert "$2000.00" in str_repr


class TestCreditCardIntegration:
    """Test credit card integration with other components."""

    def test_credit_card_with_bank(self, sample_credit_bank):
        """Test credit card integration with bank."""
        bank = sample_credit_bank

        assert "Rewards Card" in bank.credit_accounts
        card = bank.credit_accounts["Rewards Card"]

        # Should be accessible through bank methods
        all_credit = bank.get_all_credit_accounts()
        assert len(all_credit) == 1
        assert all_credit[0] == card

    def test_credit_card_with_promos(self, sample_credit_bank):
        """Test credit card with promotional offers."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add a promo
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00
        )
        card.active_promos.append(promo)

        assert len(card.active_promos) == 1
        assert card.active_promos[0].promo_name == "0% APR"

    def test_credit_card_promo_balance(self, sample_credit_bank):
        """Test promotional balance tracking."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add promo and charge to it
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00
        )
        card.active_promos.append(promo)

        # Simulate charging to promo
        card.promo_balance["0% APR"] = 1500.00

        assert card.promo_balance["0% APR"] == 1500.00

    def test_credit_card_in_timeline(self, sample_credit_bank):
        """Test credit card in timeline simulation."""
        from models.timeline_simulator import TimelineSimulator

        # Add balance to trigger interest
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        card.make_purchase(1000.00)

        simulator = TimelineSimulator([sample_credit_bank], [], [])

        start_date = date(2024, 1, 10)  # After statement date
        end_date = date(2024, 1, 31)

        events = simulator.build_timeline(start_date, end_date, include_interest=True)

        interest_events = [e for e in events if e.event_type == "INTEREST"]
        # Should have interest accrual on statement date
        assert len(interest_events) >= 1

    def test_credit_card_optimization(self, sample_bank, sample_credit_bank, sample_income):
        """Test credit card in payment optimization."""
        from models.payment_optimizer import PaymentOptimizer

        # Add balance to credit card
        card = sample_credit_bank.credit_accounts["Rewards Card"]
        card.make_purchase(2000.00)

        # Need both regular bank (for income deposits) and credit bank
        optimizer = PaymentOptimizer([sample_bank, sample_credit_bank], sample_income, [])

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        plan = optimizer.optimize_payment_schedule(
            start_date,
            end_date,
            optimization_goal="payoff_credit_account",
            target_credit_account="Rewards Card"
        )

        assert plan.target_credit_payoff == "Rewards Card"
        assert len(plan.extra_credit_payments) >= 0


class TestCreditCardEdgeCases:
    """Test credit card edge cases."""

    def test_credit_card_zero_balance(self):
        """Test credit card with zero balance."""
        card = CreditAccount(
            account_name="Zero Balance Card",
            credit_limit=5000.00,
            interest_rate=15.0
        )

        assert card.balance == 0.00
        assert card.available_credit == 5000.00
        assert card.calculate_minimum_payment() == 0.00

    def test_credit_card_maxed_out(self):
        """Test credit card at credit limit."""
        card = CreditAccount(
            account_name="Maxed Card",
            credit_limit=1000.00,
            interest_rate=15.0
        )

        card.make_purchase(1000.00)

        assert card.balance == 1000.00
        assert card.available_credit == 0.00

        # Should not allow further charges
        with pytest.raises(ValueError):
            card.make_purchase(1.00)

    def test_credit_card_overpayment(self):
        """Test overpaying credit card balance - code prevents overpayment."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=5000.00,
            interest_rate=15.0
        )

        card.make_purchase(1000.00)
        
        # Code prevents overpayment by raising an error
        with pytest.raises(ValueError, match="Payment exceeds balance"):
            card.make_payment(1200.00)  # Overpay

        # Balance should remain unchanged since payment was rejected
        assert card.balance == 1000.00

    def test_credit_card_multiple_charges(self):
        """Test multiple charges and payments."""
        card = CreditAccount(
            account_name="Test Card",
            credit_limit=10000.00,
            interest_rate=15.0
        )

        # Multiple charges
        card.make_purchase(1000.00, "Charge 1")
        card.make_purchase(500.00, "Charge 2")
        card.make_purchase(750.00, "Charge 3")

        assert card.balance == 2250.00

        # Multiple payments
        card.make_payment(1000.00, description="Payment 1")
        card.make_payment(750.00, description="Payment 2")

        assert card.balance == 500.00
        assert len(card.transaction_history) == 5  # 3 charges + 2 payments

