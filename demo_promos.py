"""
Example demonstrating promotional offers on credit cards.
Shows how interest is charged when a promotional period expires with remaining balance.
"""

from datetime import date, timedelta
from models.bank import Bank


def demo_promotional_offers():
    """Demonstrate promotional offer functionality."""

    print("\n" + "=" * 80)
    print("CREDIT CARD PROMOTIONAL OFFER DEMO")
    print("=" * 80)

    # Create a credit card with a promotional offer
    amex = Bank("American Express")
    card = amex.add_credit_account(
        account_name="Premium Card",
        credit_limit=15000.00,
        interest_rate=18.5  # 18.5% APR
    )

    print(f"\n✓ Created credit card: {card.account_name}")
    print(f"  Credit Limit: ${card.credit_limit:,.2f}")
    print(f"  APR: {card.interest_rate}%")

    # Add a promotional offer
    promo_start = date.today()
    promo = card.add_promotional_offer(
        promo_name="Intro 0% APR 12 Months",
        months_interest_free=12,
        purchase_limit=5000.00,
        start_date=promo_start
    )

    print(f"\n✓ Added promotional offer:")
    print(f"  {promo}")
    print(f"  Start Date: {promo_start}")
    print(f"  End Date: {promo.end_date}")
    print(f"  Purchase Limit: ${promo.purchase_limit:,.2f}")

    # Make a purchase using the promo
    promo_purchase = 2000.00
    card.make_purchase(
        promo_purchase,
        description="Large purchase during promo",
        transaction_date=promo_start,
        promo_name="Intro 0% APR 12 Months"
    )

    print(f"\n✓ Made purchase during promotional period:")
    print(f"  Amount: ${promo_purchase:,.2f}")
    print(f"  Promotional Balance: ${card.promo_balance.get('Intro 0% APR 12 Months', 0):.2f}")
    print(f"  Regular Balance: ${card.regular_balance:.2f}")
    print(f"  Total Balance: ${card.balance:,.2f}")

    # Show promo status
    promo_status = card.get_promo_status()
    print(f"\n✓ Promo Status:")
    for name, info in promo_status.items():
        print(f"  {name}:")
        print(f"    Amount Used: ${info['amount_used']:,.2f} / ${info['purchase_limit']:.2f}")
        print(f"    Months Remaining: {info['months_remaining']}")

    # Simulate interest accrual during promo period (should not charge interest)
    print(f"\n--- Accruing interest DURING promo period (should NOT charge) ---")
    interest_during = card.accrue_interest(current_date=promo_start + timedelta(days=31))
    print(f"Interest charged: ${interest_during:.2f}")
    print(f"Promotional Balance: ${card.promo_balance.get('Intro 0% APR 12 Months', 0):.2f}")
    print(f"Regular Balance: ${card.regular_balance:.2f}")
    print(f"Total Balance: ${card.balance:,.2f}")

    # Make another regular purchase (not on promo)
    regular_purchase = 500.00
    card.make_purchase(
        regular_purchase,
        description="Regular purchase (no promo)",
        transaction_date=promo_start + timedelta(days=32)
    )

    print(f"\n✓ Made regular purchase (not on promo):")
    print(f"  Amount: ${regular_purchase:,.2f}")
    print(f"  Promotional Balance: ${card.promo_balance.get('Intro 0% APR 12 Months', 0):.2f}")
    print(f"  Regular Balance: ${card.regular_balance:.2f}")
    print(f"  Total Balance: ${card.balance:,.2f}")

    # Accrue interest on regular balance
    print(f"\n--- Accruing interest on regular balance (should charge on ${card.regular_balance:.2f}) ---")
    interest_regular = card.accrue_interest(current_date=promo_start + timedelta(days=62))
    print(f"Interest charged: ${interest_regular:.2f}")
    print(f"Promotional Balance: ${card.promo_balance.get('Intro 0% APR 12 Months', 0):.2f}")
    print(f"Regular Balance: ${card.regular_balance:.2f}")
    print(f"Total Balance: ${card.balance:,.2f}")

    # Simulate promotion expiring
    promo_end = promo.end_date + timedelta(days=1)
    print(f"\n--- PROMOTIONAL PERIOD EXPIRES ---")
    print(f"Promo expired on: {promo.end_date}")
    print(f"Current date (simulated): {promo_end}")

    print(f"\n⚠️ Processing expired promo and charging retroactive interest...")
    interest_expired = card.accrue_interest(current_date=promo_end)

    print(f"\nResult:")
    print(f"  Interest charged on expired promo: ${interest_expired:.2f}")
    print(f"  (This is the interest that would have accrued over 12 months at {card.interest_rate}% APR)")
    print(f"  Promotional Balance: ${card.promo_balance.get('Intro 0% APR 12 Months', 0):.2f}")
    print(f"  Regular Balance: ${card.regular_balance:.2f}")
    print(f"  Total Balance: ${card.balance:,.2f}")

    # Show transaction history
    print(f"\n--- TRANSACTION HISTORY ---")
    for trans in card.transaction_history:
        trans_type = trans["type"]
        amount = trans["amount"]
        desc = trans["description"]
        print(f"{trans['date']}: [{trans_type}] {desc}: ${amount:+.2f} → Balance: ${trans['balance_after']:,.2f}")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("""
1. Purchases made during promotional period are tracked separately
2. Interest does NOT accrue on promotional purchases during promo period
3. Regular purchases still accrue interest normally
4. When promo expires with remaining balance:
   - Retroactive interest is charged as if promo never existed
   - Interest = Principal × [(1 + monthly_rate)^months - 1]
   - For this example: $2,000 × [(1 + 0.01542)^12 - 1] ≈ $397.24
5. Going forward, the entire balance (including interest) accrues interest normally
    """)


if __name__ == "__main__":
    demo_promotional_offers()

