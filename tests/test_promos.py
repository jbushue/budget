"""
Tests for promotional offers functionality.
"""

import pytest
from datetime import date, timedelta
from models.credit_card_account import PromoOffer


class TestPromotionalOffers:
    """Test PromotionalOffer class functionality."""

    def test_promo_creation(self):
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

    def test_promo_expiration(self):
        """Test promotional offer expiration."""
        # Active promo
        future_date = date.today() + timedelta(days=60)
        active_promo = PromoOffer(
            promo_name="Active Promo",
            months_interest_free=6,
            purchase_limit=1000.00
        )
        assert active_promo.is_active

        # Expired promo
        past_date = date.today() - timedelta(days=30)
        expired_promo = PromoOffer(
            promo_name="Expired Promo",
            months_interest_free=1,
            purchase_limit=1000.00,
            start_date=past_date
        )
        assert not expired_promo.is_active

    def test_promo_days_remaining(self):
        """Test calculating days remaining."""
        # Future end date
        end_date = date.today() + timedelta(days=45)
        promo = PromoOffer(
            promo_name="Test Promo",
            months_interest_free=6,
            purchase_limit=1000.00,
            end_date=end_date
        )
        assert promo.days_remaining == 45

        # Past end date
        end_date = date.today() - timedelta(days=10)
        promo = PromoOffer(
            promo_name="Expired Promo",
            months_interest_free=1,
            purchase_limit=1000.00,
            start_date=date.today() - timedelta(days=40)
        )
        assert promo.days_remaining == -10

    def test_promo_string_representation(self):
        """Test promotional offer string representation."""
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2500.00
        )

        str_repr = str(promo)
        assert "0% APR" in str_repr
        assert "12 months" in str_repr
        assert "$2500.00" in str_repr


class TestPromoIntegration:
    """Test promotional offers integration with credit cards."""

    def test_promo_with_credit_card(self, sample_credit_bank):
        """Test promotional offers with credit card accounts."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add promotional offers
        end_date = date.today() + timedelta(days=180)
        promo1 = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00
        )

        promo2 = PromoOffer(
            promo_name="5% Cash Back",
            months_interest_free=6,
            purchase_limit=1500.00
        )

        card.active_promos.extend([promo1, promo2])

        assert len(card.active_promos) == 2
        assert card.active_promos[0].promo_name == "0% APR"
        assert card.active_promos[1].promo_name == "5% Cash Back"

    def test_promo_balance_tracking(self, sample_credit_bank):
        """Test tracking balances on promotional offers."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add promo and track balance
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=12,
            purchase_limit=2000.00
        )
        card.active_promos.append(promo)

        # Simulate charges to promo
        card.promo_balance["0% APR"] = 1500.00

        assert card.promo_balance["0% APR"] == 1500.00

        # Add more to balance
        card.promo_balance["0% APR"] += 300.00
        assert card.promo_balance["0% APR"] == 1800.00

    def test_promo_payoff_priority(self, sample_credit_bank):
        """Test promotional offer payoff prioritization."""
        from models.payment_optimizer import PaymentOptimizer

        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add multiple promos with different expiration dates
        today = date.today()
        promo1 = PromoOffer(
            promo_name="Expires Soon",
            months_interest_free=1,
            purchase_limit=1000.00,
            start_date=today - timedelta(days=25)  # Started 25 days ago, 1 month = 30 days
        )
        promo2 = PromoOffer(
            promo_name="Expires Later",
            months_interest_free=3,
            purchase_limit=2000.00,
            start_date=today - timedelta(days=10)  # Started 10 days ago, 3 months = 90 days
        )

        card.active_promos.extend([promo1, promo2])
        card.promo_balance["Expires Soon"] = 800.00
        card.promo_balance["Expires Later"] = 1500.00

        optimizer = PaymentOptimizer([bank], [], [])

        start_date = today
        end_date = today + timedelta(days=60)

        priorities = optimizer._find_promo_payoff_priorities(start_date, end_date)

        assert len(priorities) == 2
        # Should be sorted by priority (expiring soonest first)
        assert priorities[0].promo_name == "Expires Soon"
        assert priorities[1].promo_name == "Expires Later"

    def test_promo_payoff_schedule(self, sample_credit_bank):
        """Test calculating promotional payoff schedules."""
        from models.payment_optimizer import PaymentOptimizer

        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add promo with balance
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=2,
            purchase_limit=2000.00,
            start_date=date.today() - timedelta(days=10)  # Started 10 days ago
        )
        card.active_promos.append(promo)
        card.promo_balance["0% APR"] = 1200.00

        optimizer = PaymentOptimizer([bank], [], [])

        start_date = date.today()
        end_date = start_date + timedelta(days=90)
        income_dates = [start_date + timedelta(days=1)]
        bill_schedule = []
        priorities = optimizer._find_promo_payoff_priorities(start_date, end_date)

        schedule = optimizer._calculate_promo_payoff_schedule(
            start_date, end_date, income_dates, bill_schedule, priorities
        )

        # Should create a payoff schedule
        assert isinstance(schedule, list)

    def test_promo_end_balance_transfer(self, sample_credit_bank):
        """Test handling promo balance when promo ends."""
        bank = sample_credit_bank
        card = bank.credit_accounts["Rewards Card"]

        # Add promo and balance
        promo = PromoOffer(
            promo_name="0% APR",
            months_interest_free=1,
            purchase_limit=2000.00,
            start_date=date.today() - timedelta(days=25)  # Started 25 days ago, expires in 5 days
        )
        card.active_promos.append(promo)
        card.promo_balance["0% APR"] = 1000.00

        # Simulate promo ending with remaining balance
        # The balance should transfer to regular card balance with full interest
        card.balance += card.promo_balance["0% APR"]  # Simulate transfer
        card.promo_balance["0% APR"] = 0.00

        assert card.balance == 1000.00
        assert card.promo_balance["0% APR"] == 0.00


class TestPromoEdgeCases:
    """Test promotional offer edge cases."""

    def test_promo_zero_balance(self):
        """Test promotional offer with zero balance."""
        end_date = date.today() + timedelta(days=180)
        promo = PromoOffer(
            promo_name="Zero Balance Promo",
            months_interest_free=12,
            purchase_limit=2000.00,
            end_date=end_date
        )

        assert promo.is_active
        assert promo.days_remaining > 0

    def test_promo_expired_with_balance(self):
        """Test expired promotional offer that still has balance."""
        past_date = date.today() - timedelta(days=30)
        promo = PromoOffer(
            promo_name="Expired Promo",
            months_interest_free=6,
            purchase_limit=1000.00,
            end_date=past_date
        )

        assert not promo.is_active
        assert promo.days_remaining < 0

    def test_promo_multiple_cards(self):
        """Test promotional offers across multiple credit cards."""
        from models.bank import Bank

        bank = Bank("Multi-Card Bank")

        # Add multiple credit cards
        bank.add_credit_account("Card 1", 5000.00)
        bank.add_credit_account("Card 2", 10000.00)

        # Add promos to different cards
        end_date = date.today() + timedelta(days=90)

        card1 = bank.credit_accounts["Card 1"]
        promo1 = PromoOffer(
            promo_name="Card1 Promo",
            months_interest_free=12,
            purchase_limit=2000.00,
            end_date=end_date
        )
        card1.active_promos.append(promo1)
        card1.promo_balance["Card1 Promo"] = 1500.00

        card2 = bank.credit_accounts["Card 2"]
        promo2 = PromoOffer(
            promo_name="Card2 Promo",
            months_interest_free=6,
            purchase_limit=3000.00,
            end_date=end_date
        )
        card2.active_promos.append(promo2)
        card2.promo_balance["Card2 Promo"] = 2200.00

        # Verify isolation between cards
        assert card1.promo_balance["Card1 Promo"] == 1500.00
        assert card2.promo_balance["Card2 Promo"] == 2200.00
        assert "Card1 Promo" not in card2.promo_balance
        assert "Card2 Promo" not in card1.promo_balance

    def test_promo_calculation_edge_cases(self):
        """Test promotional offer calculation edge cases."""
        # Promo ending today - end_date is today, so it's expired
        today = date.today()
        promo_today = PromoOffer(
            promo_name="Ends Today",
            months_interest_free=1,
            purchase_limit=1000.00,
            end_date=today
        )
        assert promo_today.days_remaining == 0
        # has_expired checks date.today() >= self.end_date, so it's expired on end date
        assert not promo_today.is_active  # Expired on end date

        # Promo ending tomorrow
        tomorrow = date.today() + timedelta(days=1)
        promo_tomorrow = PromoOffer(
            promo_name="Ends Tomorrow",
            months_interest_free=1,
            purchase_limit=1000.00,
            end_date=tomorrow
        )
        assert promo_tomorrow.days_remaining == 1
        assert promo_tomorrow.is_active



class TestPromoSimulationDates:
    """Promo expiry must follow the simulated/transaction date, not the real clock."""

    def _card_with_promo(self):
        from models.credit_card_account import CreditAccount
        card = CreditAccount("Card", credit_limit=10000, interest_rate=24.0)
        card.add_promotional_offer("0% Promo", 6, start_date=date(2030, 1, 1))
        card.make_purchase(1200.0, promo_name="0% Promo", transaction_date=date(2030, 1, 10))
        return card

    def test_purchase_uses_transaction_date(self):
        card = self._card_with_promo()
        assert card.promo_balance["0% Promo"] == 1200.0
        assert card.regular_balance == 0.0

    def test_purchase_outside_window_goes_to_regular(self):
        from models.credit_card_account import CreditAccount
        card = CreditAccount("Card", credit_limit=10000, interest_rate=24.0)
        card.add_promotional_offer("0% Promo", 6, start_date=date(2030, 1, 1))
        card.make_purchase(500.0, promo_name="0% Promo", transaction_date=date(2031, 1, 1))
        assert card.promo_balance["0% Promo"] == 0.0
        assert card.regular_balance == 500.0

    def test_no_deferred_interest_before_simulated_expiry(self):
        card = self._card_with_promo()
        assert card.accrue_interest(date(2030, 3, 1)) == 0.0
        assert card.balance == 1200.0

    def test_deferred_interest_charged_at_simulated_expiry(self):
        card = self._card_with_promo()
        promo = card.active_promos[0]
        interest = card.process_expired_promos(promo.end_date)
        assert interest > 0
        assert promo.interest_charged
        # Remaining promo balance + deferred interest becomes regular debt
        assert card.promo_balance["0% Promo"] == 0.0
        assert card.regular_balance == pytest.approx(1200.0 + interest)
        assert card.regular_balance + sum(card.promo_balance.values()) == pytest.approx(card.balance)
