"""
Interactive CLI menu for the personal finance management system.
Provides easy access to all major features.
"""

from datetime import date, timedelta
import csv
import os
from models.finance_manager import FinanceManager
from models.income_source import IncomeFrequency


class FinanceCLI:
    """Interactive CLI menu for financial management."""

    def __init__(self, manager: FinanceManager):
        self.manager = manager

    def run(self):
        """Run the interactive CLI menu."""
        while True:
            self.print_main_menu()
            choice = input("\nSelect an option (1-17): ").strip()

            if choice == "1":
                self.view_snapshot()
            elif choice == "2":
                self.quick_balance_update()
            elif choice == "3":
                self.safe_to_spend()
            elif choice == "4":
                self.project_balances()
            elif choice == "5":
                self.view_upcoming_bills()
            elif choice == "6":
                self.view_upcoming_income()
            elif choice == "7":
                self.optimize_payments()
            elif choice == "8":
                self.manage_promotional_offers()
            elif choice == "9":
                self.manage_mortgages()
            elif choice == "10":
                self.view_reports()
            elif choice == "11":
                self.view_detailed_timeline()
            elif choice == "12":
                self.create_bank_menu()
            elif choice == "13":
                self.add_bills_income_menu()
            elif choice == "14":
                self.database_management()
            elif choice == "15":
                self.credit_payoff_planner()
            elif choice == "16":
                self.spending_budget_menu()
            elif choice == "17":
                print("\nGoodbye! 👋")
                break
            else:
                print("\n❌ Invalid choice. Please try again.")

    def print_main_menu(self):
        """Print the main menu."""
        print("\n" + "=" * 80)
        print("PERSONAL FINANCE MANAGEMENT SYSTEM - MAIN MENU")
        print("=" * 80)
        print("\n1.  View Current Financial Snapshot")
        print("2.  💰 Quick Balance Update (All Accounts)")
        print("3.  🎯 Safe-to-Spend Summary")
        print("4.  Project Balance on Specific Date")
        print("5.  View Upcoming Bills (Next 60 days)")
        print("6.  View Upcoming Income (Next 60 days)")
        print("7.  Get Payment Optimization Recommendations")
        print("8.  Manage Promotional Offers (Credit Cards)")
        print("9.  Manage Mortgages")
        print("10. Generate Financial Reports")
        print("11. View Detailed Timeline")
        print("12. Manage Banks & Accounts")
        print("13. Manage Bills & Income")
        print("14. Database & File Management")
        print("15. Credit Payoff Planner")
        print("16. 📊 Spending & Budget Tracking")
        print("17. Exit")

    def view_snapshot(self):
        """View current financial snapshot."""
        print("\n" + "=" * 80)
        print("CURRENT FINANCIAL SNAPSHOT")
        print("=" * 80)
        print(self.manager.generate_snapshot())

    def quick_balance_update(self):
        """Quickly update multiple account balances at once."""
        print("\n" + "=" * 80)
        print("💰 QUICK BALANCE UPDATE")
        print("=" * 80)
        print("\nUpdate your account balances (press Enter to skip an account)")
        
        updated_count = 0
        
        # Bank accounts (checking/savings)
        print("\n--- BANK ACCOUNTS ---")
        for bank in self.manager.banks:
            for name, account in bank.accounts.items():
                current = account.balance
                new_val = input(f"  {bank.name} - {name} [${current:,.2f}]: $").strip()
                if new_val:
                    try:
                        new_balance = float(new_val)
                        bank.update_account_balance(name, new_balance, "Quick Update")
                        change = new_balance - current
                        change_str = f"+${change:,.2f}" if change >= 0 else f"-${abs(change):,.2f}"
                        print(f"    ✓ Updated ({change_str})")
                        updated_count += 1
                    except ValueError:
                        print(f"    ❌ Invalid amount, skipped")
        
        # Credit accounts (monthly update)
        print("\n--- CREDIT ACCOUNTS ---")
        for bank in self.manager.banks:
            for name, credit in bank.credit_accounts.items():
                current = credit.balance
                new_val = input(f"  {bank.name} - {name} [${current:,.2f} owed]: $").strip()
                if new_val:
                    try:
                        new_balance = float(new_val)
                        bank.update_credit_balance(name, new_balance, "Quick Update")
                        change = new_balance - current
                        if change < 0:
                            print(f"    ✓ Updated (paid down ${abs(change):,.2f})")
                        elif change > 0:
                            print(f"    ✓ Updated (increased ${change:,.2f})")
                        else:
                            print(f"    ✓ No change")
                        updated_count += 1
                    except ValueError:
                        print(f"    ❌ Invalid amount, skipped")
        
        print(f"\n✓ Updated {updated_count} account(s)")
        
        # Offer to save
        save = input("\nSave to database? (y/n): ").strip().lower()
        if save == 'y':
            if self.manager.save_to_database():
                print("✓ Saved to database")
            else:
                print("❌ Failed to save")

    def safe_to_spend(self):
        """Calculate safe-to-spend amount until next income."""
        print("\n" + "=" * 80)
        print("🎯 SAFE-TO-SPEND SUMMARY")
        print("=" * 80)
        
        today = date.today()
        
        # Calculate current total cash
        total_cash = sum(
            account.balance
            for bank in self.manager.banks
            for account in bank.get_all_accounts()
        )
        
        # Find next income date
        next_income_date = None
        next_income_amount = 0
        for income in self.manager.income_sources:
            next_pay = income.get_next_pay_date(today - timedelta(days=1))
            if next_income_date is None or next_pay < next_income_date:
                next_income_date = next_pay
                next_income_amount = income.amount
        
        if next_income_date is None:
            next_income_date = today + timedelta(days=30)
        
        # Calculate bills due before next income
        bills_before_income = []
        total_bills_due = 0
        for bill in self.manager.bills:
            next_due = bill.get_next_due_date(today - timedelta(days=1))
            if next_due <= next_income_date:
                bills_before_income.append((next_due, bill))
                total_bills_due += bill.amount
        
        # Calculate promo payments needed (urgent ones)
        promo_payments_needed = 0
        urgent_promos = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    balance = credit.promo_balance.get(promo.promo_name, 0)
                    if balance > 0:
                        days_left = (promo.end_date - today).days
                        if days_left <= 60:  # Urgent if expiring within 60 days
                            months_left = max(days_left / 30, 0.5)
                            monthly_needed = balance / months_left
                            urgent_promos.append({
                                'name': promo.promo_name,
                                'balance': balance,
                                'days_left': days_left,
                                'monthly': monthly_needed
                            })
                            promo_payments_needed += monthly_needed
        
        # Calculate minimum credit payments
        min_credit_payments = sum(
            credit.calculate_minimum_payment()
            for bank in self.manager.banks
            for credit in bank.get_all_credit_accounts()
        )
        
        # Calculate safe-to-spend
        reserved_for_bills = total_bills_due
        reserved_for_credit = min_credit_payments
        reserved_for_promos = promo_payments_needed
        buffer = 100  # Safety buffer
        
        safe_to_spend = total_cash - reserved_for_bills - reserved_for_credit - reserved_for_promos - buffer
        
        # Display results
        print(f"\n📅 Today: {today.strftime('%A, %B %d, %Y')}")
        print(f"📅 Next payday: {next_income_date.strftime('%A, %B %d, %Y')} ({(next_income_date - today).days} days)")
        print(f"   Expected: ${next_income_amount:,.2f}")
        
        print(f"\n💵 CURRENT CASH: ${total_cash:,.2f}")
        
        print(f"\n📋 BILLS DUE BEFORE NEXT PAYDAY: ${total_bills_due:,.2f}")
        bills_before_income.sort(key=lambda x: x[0])
        for due_date, bill in bills_before_income[:5]:
            days_until = (due_date - today).days
            print(f"   • {due_date.strftime('%m/%d')} ({days_until}d): {bill.bill_name} - ${bill.amount:,.2f}")
        if len(bills_before_income) > 5:
            print(f"   ... and {len(bills_before_income) - 5} more")
        
        print(f"\n💳 MIN CREDIT PAYMENTS: ${min_credit_payments:,.2f}")
        
        if urgent_promos:
            print(f"\n⚠️  PROMO PAYOFFS NEEDED: ${promo_payments_needed:,.2f}/mo")
            for p in urgent_promos:
                print(f"   • {p['name']}: ${p['balance']:,.2f} ({p['days_left']} days left)")
        
        print(f"\n🛡️  SAFETY BUFFER: ${buffer:,.2f}")
        
        print(f"\n{'='*50}")
        if safe_to_spend >= 0:
            print(f"✅ SAFE TO SPEND: ${safe_to_spend:,.2f}")
            
            # Suggest allocation
            weekly_budget = safe_to_spend / max((next_income_date - today).days / 7, 1)
            daily_budget = safe_to_spend / max((next_income_date - today).days, 1)
            print(f"\n   📆 Weekly budget: ${weekly_budget:,.2f}")
            print(f"   📆 Daily budget:  ${daily_budget:,.2f}")
        else:
            print(f"❌ SHORTFALL: ${abs(safe_to_spend):,.2f}")
            print(f"\n   ⚠️  You may need to defer some bills or reduce spending")
        
        print(f"{'='*50}")
        
        # Show optimized payment suggestion
        show_optimization = input("\nShow payment optimization? (y/n): ").strip().lower()
        if show_optimization == 'y':
            self.optimize_payments()

    def spending_budget_menu(self):
        """Manage spending budgets and track discretionary expenses."""
        while True:
            print("\n" + "=" * 80)
            print("📊 SPENDING & BUDGET TRACKING")
            print("=" * 80)
            print("\n1. View Monthly Spending Summary")
            print("2. Calculate Discretionary Budget")
            print("3. View Spending Trends")
            print("4. Set Spending Goals")
            print("5. Back to main menu")
            
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                self._monthly_spending_summary()
            elif choice == "2":
                self._calculate_discretionary_budget()
            elif choice == "3":
                self._view_spending_trends()
            elif choice == "4":
                self._set_spending_goals()
            elif choice == "5":
                break
            else:
                print("❌ Invalid choice.")

    def _monthly_spending_summary(self):
        """Show monthly spending breakdown."""
        print("\n" + "-" * 80)
        print("MONTHLY SPENDING SUMMARY")
        print("-" * 80)
        
        # Calculate monthly totals
        total_fixed_bills = sum(bill.amount for bill in self.manager.bills)
        total_income = sum(income.amount for income in self.manager.income_sources)
        
        # For semimonthly income, double the amount
        for income in self.manager.income_sources:
            if income.frequency == IncomeFrequency.SEMIMONTHLY:
                total_income += income.amount  # Add again for 2x per month
        
        # Credit minimums
        min_credit = sum(
            credit.calculate_minimum_payment()
            for bank in self.manager.banks
            for credit in bank.get_all_credit_accounts()
        )
        
        # Mortgage payments
        total_mortgage = sum(
            mortgage.total_monthly_payment
            for bank in self.manager.banks
            for mortgage in bank.get_all_mortgage_accounts()
        )
        
        total_obligations = total_fixed_bills + min_credit + total_mortgage
        discretionary = total_income - total_obligations
        
        print(f"\n📈 MONTHLY INCOME: ${total_income:,.2f}")
        for income in self.manager.income_sources:
            freq_mult = 2 if income.frequency == IncomeFrequency.SEMIMONTHLY else 1
            print(f"   • {income.source_name}: ${income.amount * freq_mult:,.2f}/mo ({income.frequency.value})")
        
        print(f"\n📉 FIXED OBLIGATIONS: ${total_obligations:,.2f}")
        print(f"   Bills: ${total_fixed_bills:,.2f}")
        for bill in sorted(self.manager.bills, key=lambda b: b.amount, reverse=True)[:5]:
            print(f"     • {bill.bill_name}: ${bill.amount:,.2f}")
        if len(self.manager.bills) > 5:
            print(f"     ... and {len(self.manager.bills) - 5} more")
        
        if total_mortgage > 0:
            print(f"   Mortgages: ${total_mortgage:,.2f}")
        
        print(f"   Min Credit Payments: ${min_credit:,.2f}")
        
        print(f"\n{'='*50}")
        print(f"💰 DISCRETIONARY (Groceries, Personal, etc): ${discretionary:,.2f}")
        print(f"   Weekly: ${discretionary/4:,.2f}")
        print(f"{'='*50}")
        
        if discretionary < 0:
            print(f"\n⚠️  WARNING: Expenses exceed income by ${abs(discretionary):,.2f}")

    def _calculate_discretionary_budget(self):
        """Calculate recommended discretionary spending budget."""
        print("\n" + "-" * 80)
        print("DISCRETIONARY BUDGET CALCULATOR")
        print("-" * 80)
        
        months = int(input("\nAnalyze for how many months? [3]: ").strip() or "3")
        
        end_date = date.today() + timedelta(days=30 * months)
        result = self.manager.project_balances(end_date=end_date)
        
        # Calculate average monthly discretionary
        total_income = sum(
            cf['amount'] for cf in result['cash_flow']
            if cf['type'] == 'INCOME'
        )
        total_expenses = abs(sum(
            cf['amount'] for cf in result['cash_flow']
            if cf['type'] in ['BILL_PAYMENT', 'MORTGAGE_PAYMENT']
        ))
        
        monthly_income = total_income / months
        monthly_expenses = total_expenses / months
        monthly_discretionary = monthly_income - monthly_expenses
        
        print(f"\n📊 {months}-MONTH PROJECTION:")
        print(f"   Average monthly income:   ${monthly_income:,.2f}")
        print(f"   Average monthly expenses: ${monthly_expenses:,.2f}")
        print(f"   Average discretionary:    ${monthly_discretionary:,.2f}")
        
        # Suggest budget categories
        print(f"\n💡 SUGGESTED BUDGET ALLOCATION:")
        groceries = monthly_discretionary * 0.40
        personal = monthly_discretionary * 0.25
        entertainment = monthly_discretionary * 0.15
        savings_extra = monthly_discretionary * 0.20
        
        print(f"   🛒 Groceries (40%):      ${groceries:,.2f}")
        print(f"   👤 Personal (25%):       ${personal:,.2f}")
        print(f"   🎬 Entertainment (15%):  ${entertainment:,.2f}")
        print(f"   💰 Extra Savings (20%):  ${savings_extra:,.2f}")

    def _view_spending_trends(self):
        """View spending trends over time."""
        print("\n" + "-" * 80)
        print("SPENDING TRENDS")
        print("-" * 80)
        
        print(f"\nAnalyzing {len(self.manager.bills)} recurring bills...")
        
        # Group bills by frequency
        monthly_bills = [b for b in self.manager.bills if b.frequency.value == 'monthly']
        other_bills = [b for b in self.manager.bills if b.frequency.value != 'monthly']
        
        print(f"\n📅 MONTHLY BILLS ({len(monthly_bills)}):")
        for bill in sorted(monthly_bills, key=lambda b: b.amount, reverse=True):
            print(f"   Day {bill.due_date:2d}: {bill.bill_name:<30} ${bill.amount:,.2f}")
        
        if other_bills:
            print(f"\n📅 OTHER RECURRING ({len(other_bills)}):")
            for bill in other_bills:
                print(f"   {bill.frequency.value}: {bill.bill_name:<30} ${bill.amount:,.2f}")
        
        # Show expense by week of month
        print(f"\n📆 EXPENSES BY WEEK OF MONTH:")
        week_totals = {1: 0, 2: 0, 3: 0, 4: 0}
        for bill in self.manager.bills:
            week = min((bill.due_date - 1) // 7 + 1, 4)
            week_totals[week] += bill.amount
        
        for week, total in week_totals.items():
            bar = "█" * int(total / 100)
            print(f"   Week {week}: ${total:,.2f} {bar}")

    def _set_spending_goals(self):
        """Set spending goals (placeholder for future enhancement)."""
        print("\n" + "-" * 80)
        print("SPENDING GOALS")
        print("-" * 80)
        print("\n⚠️  This feature will allow you to:")
        print("   • Set monthly spending limits for categories")
        print("   • Track progress against goals")
        print("   • Get alerts when approaching limits")
        print("\n   Coming in a future update!")

    def update_account_balance(self):
        """Update an account balance."""
        print("\n" + "=" * 80)
        print("UPDATE ACCOUNT BALANCE")
        print("=" * 80)

        # List available accounts
        print("\nAvailable accounts:")
        accounts = []
        for bank in self.manager.banks:
            for account in bank.get_all_accounts():
                accounts.append((bank.name, account.account_name, account.balance))
                print(f"  {len(accounts)}. {bank.name} - {account.account_name} (${account.balance:,.2f})")

        choice = input("\nSelect account to update (number): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(accounts):
                bank_name, account_name, current_balance = accounts[idx]
                print(f"\nCurrent balance: ${current_balance:,.2f}")
                new_balance = input("Enter new balance: $").strip()

                try:
                    new_balance = float(new_balance)
                    bank = next(b for b in self.manager.banks if b.name == bank_name)
                    bank.update_account_balance(account_name, new_balance, "CLI Update")
                    print(f"✓ Updated {account_name} to ${new_balance:,.2f}")
                except ValueError:
                    print("❌ Invalid amount. Please enter a number.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def project_balances(self):
        """Project balance on a specific date."""
        print("\n" + "=" * 80)
        print("PROJECT BALANCE ON SPECIFIC DATE")
        print("=" * 80)

        try:
            days_ahead = int(input("\nHow many days ahead? ").strip())
            target_date = date.today() + timedelta(days=days_ahead)

            balances = self.manager.get_balance_on_date(target_date)

            print(f"\n📅 Projected balances for {target_date.strftime('%A, %B %d, %Y')}:")
            print("-" * 80)

            total = 0
            for account_name, balance in sorted(balances.items()):
                print(f"  {account_name}: ${balance:,.2f}")
                total += balance

            print(f"\n  TOTAL: ${total:,.2f}")
        except ValueError:
            print("❌ Invalid input.")

    def view_upcoming_bills(self):
        """View upcoming bills."""
        print("\n" + "=" * 80)
        print("UPCOMING BILLS (Next 60 days)")
        print("=" * 80)

        upcoming = self.manager.get_upcoming_bills(days=60)
        if not upcoming:
            print("\nNo upcoming bills found.")
            return

        print(f"\nFound {len(upcoming)} upcoming bills:\n")
        total_due = 0
        for bill in upcoming:
            next_due = bill.get_next_due_date(date.today() - timedelta(days=1))
            print(f"  {next_due.strftime('%Y-%m-%d')}: {bill.bill_name}")
            print(f"    Amount: ${bill.amount:,.2f}")
            print(f"    Frequency: {bill.frequency.value}")
            print()
            total_due += bill.amount

        print(f"  TOTAL DUE (60 days): ${total_due:,.2f}")

    def view_upcoming_income(self):
        """View upcoming income."""
        print("\n" + "=" * 80)
        print("UPCOMING INCOME (Next 60 days)")
        print("=" * 80)

        upcoming = self.manager.get_upcoming_income(days=60)
        if not upcoming:
            print("\nNo upcoming income found.")
            return

        print(f"\nFound {len(upcoming)} upcoming income sources:\n")
        total_income = 0
        for income in upcoming:
            next_pay = income.get_next_pay_date(date.today() - timedelta(days=1))
            print(f"  {next_pay.strftime('%Y-%m-%d')}: {income.source_name}")
            print(f"    Amount: ${income.amount:,.2f}")
            print(f"    Frequency: {income.frequency.value}")
            print()
            total_income += income.amount

        print(f"  TOTAL INCOME (60 days): ${total_income:,.2f}")

    def optimize_payments(self):
        """Get payment optimization recommendations."""
        print("\n" + "=" * 80)
        print("PAYMENT OPTIMIZATION")
        print("=" * 80)

        try:
            days = int(input("\nOptimize for how many days? (default 90): ").strip() or "90")
            end_date = date.today() + timedelta(days=days)

            print(f"\nAnalyzing payment strategy for {days} days...")
            plan = self.manager.optimize_payments(end_date=end_date)

            print(f"\n✓ Optimization Complete:")
            print(f"  Discretionary Funds Available: ${plan.final_discretionary:,.2f}")
            print(f"  Total Interest Paid: ${plan.total_interest_paid:,.2f}")
            if plan.estimated_interest_earned > 0:
                print(f"  Est. Interest Earned (Savings): ${plan.estimated_interest_earned:,.2f}")
            print(f"  Issues: {len(plan.violations)}")

            if plan.strategy:
                print(f"\n  📋 RECOMMENDED PAYMENT SCHEDULE:")
                print(f"  {'-' * 76}")

                # Sort by date for chronological display
                sorted_strategy = sorted(
                    plan.strategy.items(),
                    key=lambda x: x[1]['date']
                )

                for bill_name, assignment in sorted_strategy:
                    payment_date = assignment['date']
                    bank = assignment['bank']
                    account = assignment['account']

                    # Find the bill to get the amount
                    bill = next((b for b in self.manager.bills if b.bill_name == bill_name), None)
                    amount = f"${bill.amount:,.2f}" if bill else f"${assignment.get('amount', 0):,.2f}"

                    # Calculate days until payment
                    days_until = (payment_date - date.today()).days
                    if days_until == 0:
                        timing = "TODAY"
                    elif days_until == 1:
                        timing = "TOMORROW"
                    elif days_until > 0:
                        timing = f"in {days_until} days"
                    else:
                        timing = f"{-days_until} days ago (OVERDUE!)"

                    print(f"\n  • {bill_name.upper()}")
                    print(f"    When:    {payment_date.strftime('%A, %B %d, %Y')} ({timing})")
                    print(f"    From:    {bank} → {account}")
                    print(f"    Amount:  {amount}")
            else:
                print("\n  No payment strategy generated.")

            # Show promo payoff schedule if any
            if plan.promo_payoff_schedule:
                print(f"\n  🎯 PROMO PAYOFF SCHEDULE:")
                print(f"  {'-' * 76}")
                for promo_payment in plan.promo_payoff_schedule:
                    urgency = "🔴 URGENT" if promo_payment.get('is_urgent') else ""
                    print(f"\n  • {promo_payment['promo_name']} {urgency}")
                    print(f"    Account: {promo_payment['credit_account']}")
                    print(f"    Date:    {promo_payment['date'].strftime('%A, %B %d, %Y')}")
                    print(f"    Amount:  ${promo_payment['amount']:,.2f}")
                    if promo_payment.get('promo_end_date'):
                        print(f"    Promo expires: {promo_payment['promo_end_date']}")

            # Show transfer recommendations if any
            if plan.transfer_recommendations:
                print(f"\n  💰 SAVINGS OPTIMIZATION TRANSFERS:")
                print(f"  {'-' * 76}")
                print(f"  Move money to savings to earn ~${plan.estimated_interest_earned:.2f} extra interest")
                
                for transfer in plan.transfer_recommendations:
                    arrow = "→" if transfer.reason == 'maximize_interest' else "←"
                    reason_icon = "📈" if transfer.reason == 'maximize_interest' else "💵"
                    
                    print(f"\n  {reason_icon} {transfer.transfer_date.strftime('%m/%d')}: ", end="")
                    if transfer.reason == 'maximize_interest':
                        print(f"${transfer.amount:,.2f} Checking → Savings")
                        if transfer.estimated_interest_gain > 0:
                            print(f"       Est. interest gain: ${transfer.estimated_interest_gain:.2f}")
                    else:
                        print(f"${transfer.amount:,.2f} Savings → Checking (for bills)")

            if plan.violations:
                print(f"\n  ⚠️  ISSUES DETECTED:")
                print(f"  {'-' * 76}")
                for violation in plan.violations:
                    print(f"    • {violation}")
            else:
                print(f"\n  ✓ No issues detected - plan is feasible")

        except ValueError:
            print("❌ Invalid input.")

    def manage_promotional_offers(self):
        """Manage promotional offers on credit cards."""
        print("\n" + "=" * 80)
        print("PROMOTIONAL OFFERS MANAGEMENT")
        print("=" * 80)
        print("\n1. View All Promotional Offers")
        print("2. Add New Promotional Offer")
        print("3. Record Purchase on Promo")
        print("4. Pay Down Promo Balance")
        print("5. View Promo Payoff Priority")
        print("6. Remove Promo Offer")
        print("7. Back to main menu")

        choice = input("\nSelect option (1-7): ").strip()

        if choice == "1":
            self._view_all_promos()
        elif choice == "2":
            self._add_promotional_offer()
        elif choice == "3":
            self._record_promo_purchase()
        elif choice == "4":
            self._pay_promo_balance()
        elif choice == "5":
            self._view_promo_payoff_priority()
        elif choice == "6":
            self._remove_promo_offer()
        elif choice == "7":
            return
        else:
            print("❌ Invalid choice.")

    def _view_all_promos(self):
        """View all promotional offers across all credit accounts."""
        print("\n" + "-" * 80)
        print("ALL PROMOTIONAL OFFERS")
        print("-" * 80)

        has_promos = False
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                if credit.active_promos:
                    has_promos = True
                    print(f"\n{bank.name} - {credit.account_name}:")
                    for promo in credit.active_promos:
                        status = "ACTIVE" if promo.is_active and not promo.has_expired() else "EXPIRED"
                        days_left = (promo.end_date - date.today()).days
                        balance = credit.promo_balance.get(promo.promo_name, 0)
                        print(f"  • {promo.promo_name}")
                        print(f"    Status: {status}")
                        print(f"    Expires: {promo.end_date} ({days_left} days left)")
                        print(f"    Balance on promo: ${balance:,.2f}")
                        if promo.purchase_limit:
                            print(f"    Limit: ${promo.purchase_limit:,.2f} (${promo.amount_used:,.2f} used)")

        if not has_promos:
            print("\nNo promotional offers found.")

    def _add_promotional_offer(self):
        """Add a new promotional offer to a credit card."""
        print("\n" + "-" * 80)
        print("ADD PROMOTIONAL OFFER")
        print("-" * 80)

        # List credit accounts
        credit_accounts = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                credit_accounts.append((bank.name, credit.account_name, credit))
                print(f"  {len(credit_accounts)}. {bank.name} - {credit.account_name}")

        if not credit_accounts:
            print("\nNo credit accounts found. Create a credit account first.")
            return

        try:
            choice = input("\nSelect credit card (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(credit_accounts):
                bank_name, account_name, credit = credit_accounts[idx]

                promo_name = input("Promotion name (e.g., '0% APR 12 months'): ").strip()
                months = int(input("Months interest-free: ").strip())
                limit_str = input("Purchase limit ($, or press Enter for unlimited): ").strip()
                limit = float(limit_str) if limit_str else None
                
                # Ask for initial balance on promo
                initial_balance_str = input("Initial balance on promo ($ or Enter for 0): ").strip()
                initial_balance = float(initial_balance_str) if initial_balance_str else 0.0

                promo = credit.add_promotional_offer(promo_name, months, limit)
                
                if initial_balance > 0:
                    credit.promo_balance[promo_name] = initial_balance
                    promo.amount_used = initial_balance
                    credit.balance += initial_balance
                    
                print(f"\n✓ Added promotion: {promo}")
                if initial_balance > 0:
                    print(f"  Initial balance: ${initial_balance:,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _record_promo_purchase(self):
        """Record a purchase on a promotional offer."""
        print("\n" + "-" * 80)
        print("RECORD PROMO PURCHASE")
        print("-" * 80)

        # Find all active promos
        promo_list = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    if promo.is_active and not promo.has_expired():
                        promo_list.append((bank.name, credit, promo))
                        remaining = promo.purchase_limit - promo.amount_used if promo.purchase_limit else "Unlimited"
                        print(f"  {len(promo_list)}. {credit.account_name} - {promo.promo_name}")
                        print(f"      Available: {remaining if isinstance(remaining, str) else f'${remaining:,.2f}'}")

        if not promo_list:
            print("\nNo active promotional offers found.")
            return

        try:
            choice = input("\nSelect promo (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(promo_list):
                bank_name, credit, promo = promo_list[idx]
                
                amount = float(input("Purchase amount ($): ").strip())
                description = input("Description (optional): ").strip() or "Promo purchase"
                
                if promo.is_valid_for_purchase(amount):
                    credit.make_purchase(amount, description, promo_name=promo.promo_name)
                    print(f"\n✓ Recorded ${amount:,.2f} purchase on {promo.promo_name}")
                    print(f"  New promo balance: ${credit.promo_balance.get(promo.promo_name, 0):,.2f}")
                else:
                    print("❌ Purchase exceeds promo limit or promo has expired.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _view_promo_payoff_priority(self):
        """View prioritized list of promos that need to be paid off."""
        print("\n" + "-" * 80)
        print("PROMO PAYOFF PRIORITY")
        print("-" * 80)

        promos_with_balance = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    balance = credit.promo_balance.get(promo.promo_name, 0)
                    if balance > 0:
                        days_left = (promo.end_date - date.today()).days
                        promos_with_balance.append({
                            'bank': bank.name,
                            'credit': credit.account_name,
                            'promo': promo.promo_name,
                            'balance': balance,
                            'end_date': promo.end_date,
                            'days_left': days_left,
                            'apr_after': credit.interest_rate
                        })

        if not promos_with_balance:
            print("\nNo promotional balances to pay off.")
            return

        # Sort by days remaining (most urgent first)
        promos_with_balance.sort(key=lambda x: x['days_left'])

        print("\nPromos ordered by urgency (soonest expiration first):\n")
        for i, p in enumerate(promos_with_balance, 1):
            urgency = "🔴 URGENT!" if p['days_left'] <= 30 else "🟡 Soon" if p['days_left'] <= 60 else "🟢 OK"
            print(f"  {i}. {p['credit']} - {p['promo']}")
            print(f"     Balance: ${p['balance']:,.2f}")
            print(f"     Expires: {p['end_date']} ({p['days_left']} days) {urgency}")
            print(f"     APR after expiry: {p['apr_after']}%")
            
            # Calculate required monthly payment
            months_left = max(p['days_left'] / 30, 0.5)
            monthly_needed = p['balance'] / months_left
            print(f"     Suggested monthly payment: ${monthly_needed:,.2f}")
            print()

    def _pay_promo_balance(self):
        """Pay down a promotional balance."""
        print("\n" + "-" * 80)
        print("PAY PROMO BALANCE")
        print("-" * 80)

        # Find all promos with balances
        promo_list = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    balance = credit.promo_balance.get(promo.promo_name, 0)
                    if balance > 0:
                        promo_list.append((bank, credit, promo, balance))
                        days_left = (promo.end_date - date.today()).days
                        print(f"  {len(promo_list)}. {credit.account_name} - {promo.promo_name}")
                        print(f"      Balance: ${balance:,.2f}, Expires in {days_left} days")

        if not promo_list:
            print("\nNo promotional balances to pay.")
            return

        try:
            choice = int(input("\nSelect promo to pay (number): ").strip())
            if 1 <= choice <= len(promo_list):
                bank, credit, promo, balance = promo_list[choice - 1]
                
                print(f"\nPromo balance: ${balance:,.2f}")
                amount_str = input(f"Payment amount (Enter to pay in full): $").strip()
                amount = float(amount_str) if amount_str else balance
                
                if amount > balance:
                    print(f"⚠️  Amount exceeds promo balance. Paying ${balance:,.2f}")
                    amount = balance
                
                # Find source account for payment
                print("\nSelect payment source:")
                acc_list = []
                for b in self.manager.banks:
                    for name, acc in b.accounts.items():
                        acc_list.append((b, name, acc))
                        print(f"  {len(acc_list)}. {b.name} - {name}: ${acc.balance:,.2f}")
                
                if not acc_list:
                    print("❌ No bank accounts to pay from.")
                    return
                
                source_choice = int(input("\nSelect source (number): ").strip())
                if 1 <= source_choice <= len(acc_list):
                    source_bank, source_name, source_acc = acc_list[source_choice - 1]
                    
                    if amount > source_acc.balance:
                        print(f"❌ Insufficient funds. Available: ${source_acc.balance:,.2f}")
                        return
                    
                    # Process payment
                    source_acc.withdraw(amount, description=f"Payment to {credit.account_name} promo")
                    credit.promo_balance[promo.promo_name] -= amount
                    credit.balance -= amount
                    
                    new_promo_balance = credit.promo_balance[promo.promo_name]
                    print(f"\n✓ Paid ${amount:,.2f} to {promo.promo_name}")
                    print(f"  Promo balance: ${new_promo_balance:,.2f}")
                    print(f"  Credit balance: ${credit.balance:,.2f}")
                    
                    if new_promo_balance <= 0:
                        print(f"  🎉 Promo '{promo.promo_name}' paid off!")
                else:
                    print("❌ Invalid selection.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _remove_promo_offer(self):
        """Remove a promotional offer from a credit account."""
        print("\n" + "-" * 80)
        print("REMOVE PROMO OFFER")
        print("-" * 80)

        # Find all promos
        promo_list = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    promo_list.append((bank, credit, promo))
                    balance = credit.promo_balance.get(promo.promo_name, 0)
                    print(f"  {len(promo_list)}. {credit.account_name} - {promo.promo_name}")
                    print(f"      Balance: ${balance:,.2f}, Expires: {promo.end_date}")

        if not promo_list:
            print("\nNo promotional offers found.")
            return

        try:
            choice = int(input("\nSelect promo to remove (number): ").strip())
            if 1 <= choice <= len(promo_list):
                bank, credit, promo = promo_list[choice - 1]
                balance = credit.promo_balance.get(promo.promo_name, 0)
                
                if balance > 0:
                    print(f"\n⚠️  This promo has ${balance:,.2f} balance remaining.")
                    print("The balance will be moved to regular (non-promo) balance.")
                    confirm = input("Continue? (y/n): ").strip().lower()
                else:
                    confirm = input(f"\nRemove '{promo.promo_name}'? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    # Move promo balance to regular balance
                    if balance > 0:
                        credit.regular_balance += balance
                        del credit.promo_balance[promo.promo_name]
                    
                    credit.active_promos.remove(promo)
                    print(f"\n✓ Promo '{promo.promo_name}' removed from {credit.account_name}")
                else:
                    print("Cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def view_reports(self):
        """Generate and view financial reports with customizable time periods."""
        print("\n" + "=" * 80)
        print("FINANCIAL REPORTS")
        print("=" * 80)
        print("\n1. Current Snapshot")
        print("2. Projection Report (customizable period)")
        print("3. Budget Analysis (customizable months)")
        print("4. Payment Schedule (customizable months)")
        print("5. Back to main menu")

        choice = input("\nSelect report (1-5): ").strip()

        if choice == "1":
            print("\n" + self.manager.generate_snapshot())

        elif choice == "2":
            # Projection report with custom time period
            print("\n" + "-" * 80)
            print("PROJECTION REPORT - TIME PERIOD SELECTION")
            print("-" * 80)
            print("\nSpecify time period:")
            print("  Option 1: Days")
            print("  Option 2: Weeks")
            print("  Option 3: Months")
            print("  Option 4: Years")

            time_choice = input("\nSelect option (1-4): ").strip()
            try:
                amount = int(input("Enter amount: ").strip())

                if time_choice == "1":
                    end_date = date.today() + timedelta(days=amount)
                    period_str = f"{amount} days"
                elif time_choice == "2":
                    end_date = date.today() + timedelta(weeks=amount)
                    period_str = f"{amount} weeks"
                elif time_choice == "3":
                    end_date = date.today() + timedelta(days=30 * amount)
                    period_str = f"{amount} months"
                elif time_choice == "4":
                    end_date = date.today() + timedelta(days=365 * amount)
                    period_str = f"{amount} years"
                else:
                    print("❌ Invalid option.")
                    return

                print(f"\nGenerating {period_str} projection report...")
                print("\n" + self.manager.generate_projection_report(end_date=end_date))
            except ValueError:
                print("❌ Invalid input.")

        elif choice == "3":
            # Budget analysis with custom months
            print("\n" + "-" * 80)
            print("BUDGET ANALYSIS - DURATION SELECTION")
            print("-" * 80)
            print("\nSpecify analysis period:")
            print("  Option 1: Months")
            print("  Option 2: Years")

            time_choice = input("\nSelect option (1-2): ").strip()
            try:
                if time_choice == "1":
                    amount = int(input("Enter number of months: ").strip())
                    period_str = f"{amount} months"
                elif time_choice == "2":
                    amount = int(input("Enter number of years: ").strip())
                    amount = amount * 12  # Convert years to months
                    period_str = f"{amount // 12} year(s)"
                else:
                    print("❌ Invalid option.")
                    return

                print(f"\nGenerating {period_str} budget analysis...")
                print("\n" + self.manager.generate_budget_analysis(months=amount))
            except ValueError:
                print("❌ Invalid input.")

        elif choice == "4":
            # Payment schedule with custom months
            print("\n" + "-" * 80)
            print("PAYMENT SCHEDULE - DURATION SELECTION")
            print("-" * 80)
            print("\nSpecify schedule period:")
            print("  Option 1: Months")
            print("  Option 2: Years")
            print("  Option 3: Weeks")

            time_choice = input("\nSelect option (1-3): ").strip()
            try:
                if time_choice == "1":
                    amount = int(input("Enter number of months: ").strip())
                    period_str = f"{amount} months"
                elif time_choice == "2":
                    amount = int(input("Enter number of years: ").strip())
                    amount = amount * 12  # Convert years to months
                    period_str = f"{amount // 12} year(s)"
                elif time_choice == "3":
                    weeks = int(input("Enter number of weeks: ").strip())
                    amount = (weeks * 7) // 30  # Approximate weeks to months
                    period_str = f"{weeks} weeks"
                else:
                    print("❌ Invalid option.")
                    return

                print(f"\nGenerating {period_str} payment schedule...")
                print("\n" + self.manager.generate_payment_schedule(months=amount))
            except ValueError:
                print("❌ Invalid input.")

        elif choice != "5":
            print("❌ Invalid choice.")

    def view_detailed_timeline(self):
        """View detailed day-by-day timeline."""
        print("\n" + "=" * 80)
        print("DETAILED TIMELINE")
        print("=" * 80)

        try:
            days = int(input("\nShow timeline for how many days? (default 30): ").strip() or "30")
            end_date = date.today() + timedelta(days=days)

            print(f"\nGenerating timeline...")
            timeline = self.manager.generate_detailed_timeline(end_date=end_date)
            print("\n" + timeline)

            # Offer export option
            self._offer_export_timeline(days)
        except ValueError:
            print("❌ Invalid input.")

    def _offer_export_timeline(self, days: int):
        """Offer to export timeline after viewing."""
        export = input("\nExport this timeline? (y/n): ").strip().lower()
        if export == "y":
            self.export_report("timeline", days=days)

    def export_report(self, report_type: str, **kwargs):
        """Export reports to various formats."""
        print("\n" + "=" * 80)
        print("EXPORT REPORT")
        print("=" * 80)
        print("\nExport format:")
        print("  1. CSV")
        print("  2. Excel (.xlsx)")
        print("  3. PDF")
        print("  4. Text (.txt)")

        choice = input("\nSelect format (1-4): ").strip()

        if choice == "1":
            self._export_to_csv(report_type, **kwargs)
        elif choice == "2":
            self._export_to_excel(report_type, **kwargs)
        elif choice == "3":
            self._export_to_pdf(report_type, **kwargs)
        elif choice == "4":
            self._export_to_text(report_type, **kwargs)
        else:
            print("❌ Invalid choice.")

    def _export_to_csv(self, report_type: str, **kwargs):
        """Export report to CSV format."""
        try:
            filename = f"report_{report_type}_{date.today().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(os.path.expanduser("~"), "Desktop", filename)

            if report_type == "snapshot":
                self._snapshot_to_csv(filepath)
            elif report_type == "projection":
                self._projection_to_csv(filepath, **kwargs)
            elif report_type == "budget":
                self._budget_to_csv(filepath, **kwargs)
            elif report_type == "timeline":
                self._timeline_to_csv(filepath, **kwargs)
            else:
                print("❌ Unknown report type.")
                return

            print(f"✓ Report exported to: {filepath}")
        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _export_to_text(self, report_type: str, **kwargs):
        """Export report to plain text format."""
        try:
            filename = f"report_{report_type}_{date.today().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(os.path.expanduser("~"), "Desktop", filename)

            content = ""
            if report_type == "snapshot":
                content = self.manager.generate_snapshot()
            elif report_type == "projection":
                end_date = date.today() + timedelta(days=kwargs.get('days', 90))
                content = self.manager.generate_projection_report(end_date=end_date)
            elif report_type == "budget":
                months = kwargs.get('months', 3)
                content = self.manager.generate_budget_analysis(months=months)
            elif report_type == "timeline":
                days = kwargs.get('days', 30)
                end_date = date.today() + timedelta(days=days)
                content = self.manager.generate_detailed_timeline(end_date=end_date)
            else:
                print("❌ Unknown report type.")
                return

            with open(filepath, 'w') as f:
                f.write(content)

            print(f"✓ Report exported to: {filepath}")
        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _export_to_excel(self, report_type: str, **kwargs):
        """Export report to Excel format."""
        try:
            # Try to import openpyxl, provide helpful message if not available
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
            except ImportError:
                print("\n⚠️  Excel export requires 'openpyxl' package.")
                print("Install it with: pip install openpyxl")
                print("\nFalling back to CSV export...")
                self._export_to_csv(report_type, **kwargs)
                return

            filename = f"report_{report_type}_{date.today().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(os.path.expanduser("~"), "Desktop", filename)

            wb = Workbook()
            ws = wb.active
            ws.title = "Report"

            # Add title
            ws['A1'] = f"{report_type.upper()} REPORT"
            ws['A1'].font = Font(bold=True, size=14)
            ws['A2'] = f"Generated: {date.today().strftime('%A, %B %d, %Y')}"
            ws['A2'].font = Font(italic=True)

            if report_type == "snapshot":
                self._populate_snapshot_excel(ws, **kwargs)
            elif report_type == "projection":
                self._populate_projection_excel(ws, **kwargs)
            elif report_type == "budget":
                self._populate_budget_excel(ws, **kwargs)
            elif report_type == "timeline":
                self._populate_timeline_excel(ws, **kwargs)

            wb.save(filepath)
            print(f"✓ Report exported to: {filepath}")
        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _export_to_pdf(self, report_type: str, **kwargs):
        """Export report to PDF format."""
        try:
            # Try to import reportlab
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
            except ImportError:
                print("\n⚠️  PDF export requires 'reportlab' package.")
                print("Install it with: pip install reportlab")
                print("\nFalling back to text export...")
                self._export_to_text(report_type, **kwargs)
                return

            filename = f"report_{report_type}_{date.today().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Desktop", filename)

            # Get report content
            if report_type == "snapshot":
                content = self.manager.generate_snapshot()
            elif report_type == "projection":
                end_date = date.today() + timedelta(days=kwargs.get('days', 90))
                content = self.manager.generate_projection_report(end_date=end_date)
            elif report_type == "budget":
                months = kwargs.get('months', 3)
                content = self.manager.generate_budget_analysis(months=months)
            elif report_type == "timeline":
                days = kwargs.get('days', 30)
                end_date = date.today() + timedelta(days=days)
                content = self.manager.generate_detailed_timeline(end_date=end_date)
            else:
                print("❌ Unknown report type.")
                return

            # Create PDF
            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter

            y = height - 0.5 * inch
            c.setFont("Helvetica-Bold", 14)
            c.drawString(0.5 * inch, y, f"{report_type.upper()} REPORT")

            y -= 0.3 * inch
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(0.5 * inch, y, f"Generated: {date.today().strftime('%A, %B %d, %Y')}")

            y -= 0.5 * inch
            c.setFont("Courier", 9)

            # Split content into lines and draw
            lines = content.split('\n')
            for line in lines:
                if y < 0.5 * inch:
                    c.showPage()
                    y = height - 0.5 * inch
                    c.setFont("Courier", 9)

                # Truncate long lines
                if len(line) > 100:
                    line = line[:97] + "..."

                c.drawString(0.5 * inch, y, line)
                y -= 0.15 * inch

            c.save()
            print(f"✓ Report exported to: {filepath}")
        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _snapshot_to_csv(self, filepath: str):
        """Export snapshot to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Account", "Balance"])

            for bank in self.manager.banks:
                for account in bank.get_all_accounts():
                    key = f"{bank.name}:{account.account_name}"
                    writer.writerow([key, account.balance])

    def _projection_to_csv(self, filepath: str, **kwargs):
        """Export projection to CSV."""
        days = kwargs.get('days', 90)
        end_date = date.today() + timedelta(days=days)
        result = self.manager.project_balances(end_date=end_date)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Account", "Balance"])

            for snapshot in result["snapshots"]:
                snap_date = snapshot["date"]
                for account_name, balance in snapshot["balances"].items():
                    writer.writerow([snap_date, account_name, balance])

    def _budget_to_csv(self, filepath: str, **kwargs):
        """Export budget analysis to CSV."""
        months = kwargs.get('months', 3)
        end_date = date.today() + timedelta(days=30 * months)
        result = self.manager.project_balances(end_date=end_date)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Type", "Description", "Amount", "Account"])

            for cf_item in result["cash_flow"]:
                writer.writerow([
                    cf_item["date"],
                    cf_item["type"],
                    cf_item["description"],
                    cf_item["amount"],
                    cf_item.get("account", "")
                ])

    def _timeline_to_csv(self, filepath: str, **kwargs):
        """Export timeline to CSV."""
        days = kwargs.get('days', 30)
        end_date = date.today() + timedelta(days=days)
        result = self.manager.project_balances(end_date=end_date)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Type", "Description", "Amount", "Account", "Bank"])

            for cf_item in result["cash_flow"]:
                writer.writerow([
                    cf_item["date"],
                    cf_item["type"],
                    cf_item["description"],
                    cf_item["amount"],
                    cf_item.get("account", ""),
                    cf_item.get("bank", "")
                ])

    def _populate_snapshot_excel(self, ws, **kwargs):
        """Populate Excel sheet with snapshot data."""
        row = 4
        ws[f'A{row}'] = "Account"
        ws[f'B{row}'] = "Balance"

        for col in ['A', 'B']:
            ws[f'{col}{row}'].font = Font(bold=True)

        row += 1
        for bank in self.manager.banks:
            for account in bank.get_all_accounts():
                ws[f'A{row}'] = f"{bank.name}: {account.account_name}"
                ws[f'B{row}'] = account.balance
                ws[f'B{row}'].number_format = '$#,##0.00'
                row += 1

    def _populate_projection_excel(self, ws, **kwargs):
        """Populate Excel sheet with projection data."""
        days = kwargs.get('days', 90)
        end_date = date.today() + timedelta(days=days)
        result = self.manager.project_balances(end_date=end_date)

        row = 4
        ws[f'A{row}'] = "Date"
        ws[f'B{row}'] = "Account"
        ws[f'C{row}'] = "Balance"

        for col in ['A', 'B', 'C']:
            ws[f'{col}{row}'].font = Font(bold=True)

        row += 1
        for snapshot in result["snapshots"]:
            snap_date = snapshot["date"]
            for account_name, balance in snapshot["balances"].items():
                ws[f'A{row}'] = snap_date
                ws[f'B{row}'] = account_name
                ws[f'C{row}'] = balance
                ws[f'C{row}'].number_format = '$#,##0.00'
                row += 1

    def _populate_budget_excel(self, ws, **kwargs):
        """Populate Excel sheet with budget data."""
        months = kwargs.get('months', 3)
        end_date = date.today() + timedelta(days=30 * months)
        result = self.manager.project_balances(end_date=end_date)

        row = 4
        ws[f'A{row}'] = "Date"
        ws[f'B{row}'] = "Type"
        ws[f'C{row}'] = "Description"
        ws[f'D{row}'] = "Amount"
        ws[f'E{row}'] = "Account"

        for col in ['A', 'B', 'C', 'D', 'E']:
            ws[f'{col}{row}'].font = Font(bold=True)

        row += 1
        for cf_item in result["cash_flow"]:
            ws[f'A{row}'] = cf_item["date"]
            ws[f'B{row}'] = cf_item["type"]
            ws[f'C{row}'] = cf_item["description"]
            ws[f'D{row}'] = cf_item["amount"]
            ws[f'D{row}'].number_format = '$#,##0.00'
            ws[f'E{row}'] = cf_item.get("account", "")
            row += 1

    def _populate_timeline_excel(self, ws, **kwargs):
        """Populate Excel sheet with timeline data."""
        days = kwargs.get('days', 30)
        end_date = date.today() + timedelta(days=days)
        result = self.manager.project_balances(end_date=end_date)

        row = 4
        ws[f'A{row}'] = "Date"
        ws[f'B{row}'] = "Type"
        ws[f'C{row}'] = "Description"
        ws[f'D{row}'] = "Amount"
        ws[f'E{row}'] = "Account"
        ws[f'F{row}'] = "Bank"

        for col in ['A', 'B', 'C', 'D', 'E', 'F']:
            ws[f'{col}{row}'].font = Font(bold=True)

        row += 1
        for cf_item in result["cash_flow"]:
            ws[f'A{row}'] = cf_item["date"]
            ws[f'B{row}'] = cf_item["type"]
            ws[f'C{row}'] = cf_item["description"]
            ws[f'D{row}'] = cf_item["amount"]
            ws[f'D{row}'].number_format = '$#,##0.00'
            ws[f'E{row}'] = cf_item.get("account", "")
            ws[f'F{row}'] = cf_item.get("bank", "")
            row += 1

    def database_management(self):
        """Database and file management menu."""
        while True:
            print("\n" + "=" * 80)
            print("DATABASE & FILE MANAGEMENT")
            print("=" * 80)
            print("\n1. Save data to database")
            print("2. Load data from database")
            print("3. View database info")
            print("4. 📥 Import from Excel (bulk load)")
            print("5. 📤 Export to Excel")
            print("6. 📋 Generate Excel template")
            print("7. Back to main menu")

            choice = input("\nSelect option (1-7): ").strip()

            if choice == "1":
                self.save_to_database()
            elif choice == "2":
                self.load_from_database()
            elif choice == "3":
                self.view_database_info()
            elif choice == "4":
                self.import_from_excel()
            elif choice == "5":
                self.export_to_excel()
            elif choice == "6":
                self.generate_excel_template()
            elif choice == "7":
                break
            else:
                print("❌ Invalid choice.")

    def save_to_database(self):
        """Save current data to database."""
        print("\n" + "-" * 80)
        print("SAVE TO DATABASE")
        print("-" * 80)

        confirm = input("\nSave all banks, accounts, bills, and income sources? (y/n): ").strip().lower()
        if confirm == "y":
            if self.manager.save_to_database():
                print("✓ Data saved successfully to database")
                print(f"  Location: {os.path.expanduser('~')}/.budget_app/finance.db")
            else:
                print("❌ Failed to save data")

    def load_from_database(self):
        """Load data from database."""
        print("\n" + "-" * 80)
        print("LOAD FROM DATABASE")
        print("-" * 80)

        confirm = input("\nLoad data from database? This will replace current data. (y/n): ").strip().lower()
        if confirm == "y":
            if self.manager.load_from_database():
                print("✓ Data loaded successfully from database")
                self._show_loaded_data_summary()
            else:
                print("❌ Failed to load data")

    def view_database_info(self):
        """Show database information."""
        print("\n" + "-" * 80)
        print("DATABASE INFORMATION")
        print("-" * 80)

        try:
            from models.db_repository import DatabaseRepository
            from models.database import DB_PATH

            repo = DatabaseRepository()
            info = repo.export_data()
            repo.close()

            print(f"\nDatabase Location: {DB_PATH}")
            print(f"\nData Summary:")
            print(f"  Banks: {len(self.manager.banks)}")
            print(f"  Bank Accounts: {sum(len(b.accounts) for b in self.manager.banks)}")
            print(f"  Credit Accounts: {sum(len(b.credit_accounts) for b in self.manager.banks)}")
            print(f"  Bills: {len(self.manager.bills)}")
            print(f"  Income Sources: {len(self.manager.income_sources)}")

            print(f"\nDatabase Stats:")
            print(f"  Banks stored: {info['banks']}")
            print(f"  Total accounts: {info['accounts'] + info['credit_accounts']}")
            print(f"  Bills: {info['bills']}")
            print(f"  Income sources: {info['income_sources']}")
        except Exception as e:
            print(f"❌ Error reading database info: {e}")

    def _show_loaded_data_summary(self):
        """Show summary of loaded data."""
        print("\n✓ Loaded Data:")
        print(f"  Banks: {len(self.manager.banks)}")
        for bank in self.manager.banks:
            print(f"    • {bank.name} ({len(bank.accounts)} bank accounts, {len(bank.credit_accounts)} credit accounts)")
        print(f"  Bills: {len(self.manager.bills)}")
        for bill in self.manager.bills[:5]:  # Show first 5
            print(f"    • {bill.bill_name}")
        if len(self.manager.bills) > 5:
            print(f"    ... and {len(self.manager.bills) - 5} more")
        print(f"  Income sources: {len(self.manager.income_sources)}")
        for income in self.manager.income_sources:
            print(f"    • {income.source_name} (${income.amount:,.2f})")

    def generate_excel_template(self):
        """Generate an Excel template for bulk data import."""
        print("\n" + "-" * 80)
        print("📋 GENERATE EXCEL TEMPLATE")
        print("-" * 80)
        
        from models.data_import_export import DataImportExport
        
        importer = DataImportExport(self.manager)
        
        print("\nThis will create an Excel template with all the sheets")
        print("you need to fill out for bulk importing your financial data.")
        print("\nThe template includes:")
        print("  • Banks - Financial institutions")
        print("  • Bank_Accounts - Checking and savings accounts")
        print("  • Credit_Accounts - Credit cards")
        print("  • Mortgages - Home loans with escrow")
        print("  • Bills - Recurring expenses")
        print("  • Income - Income sources and pay schedules")
        print("  • Promo_Offers - Promotional 0% APR offers")
        
        custom_path = input("\nCustom file path (Enter for Desktop): ").strip()
        filepath = custom_path if custom_path else None
        
        result = importer.generate_template(filepath)
        
        if result:
            print(f"\n✓ Template created: {result}")
            print("\nNext steps:")
            print("  1. Open the template in Excel")
            print("  2. Fill in your financial data (delete example rows)")
            print("  3. Save the file")
            print("  4. Use 'Import from Excel' to load the data")
        else:
            print("\n❌ Failed to create template")

    def import_from_excel(self):
        """Import financial data from an Excel file."""
        print("\n" + "-" * 80)
        print("📥 IMPORT FROM EXCEL")
        print("-" * 80)
        
        from models.data_import_export import DataImportExport
        
        importer = DataImportExport(self.manager)
        
        print("\nImport financial data from an Excel file.")
        print("Use 'Generate Excel template' first if you haven't already.")
        
        # Check for existing data
        existing_data = (
            len(self.manager.banks) > 0 or
            len(self.manager.bills) > 0 or
            len(self.manager.income_sources) > 0
        )
        
        if existing_data:
            print("\n⚠️  You have existing data:")
            print(f"   {len(self.manager.banks)} banks, "
                  f"{len(self.manager.bills)} bills, "
                  f"{len(self.manager.income_sources)} income sources")
            
            mode = input("\n1. Add to existing data\n2. Replace all data\nSelect (1/2): ").strip()
            if mode == "2":
                confirm = input("⚠️  Delete all existing data? (type 'YES' to confirm): ").strip()
                if confirm == "YES":
                    self.manager.banks = []
                    self.manager.bills = []
                    self.manager.income_sources = []
                    print("✓ Existing data cleared")
                else:
                    print("Cancelled.")
                    return
        
        # Get file path
        default_path = os.path.join(os.path.expanduser("~"), "Desktop")
        print(f"\nDefault location: {default_path}")
        filepath = input("Enter Excel file path: ").strip()
        
        if not filepath:
            print("❌ No file path provided")
            return
        
        # Handle relative paths
        if not os.path.isabs(filepath):
            filepath = os.path.join(default_path, filepath)
        
        print(f"\nImporting from: {filepath}")
        print("Please wait...")
        
        results = importer.import_from_excel(filepath)
        
        print("\n" + "=" * 50)
        print("IMPORT RESULTS")
        print("=" * 50)
        
        if results["success"]:
            print("\n✅ Import completed successfully!")
        else:
            print("\n⚠️  Import completed with errors")
        
        print(f"\n📊 Items Created:")
        print(f"   Banks:           {results['banks_created']}")
        print(f"   Bank Accounts:   {results['bank_accounts_created']}")
        print(f"   Credit Accounts: {results['credit_accounts_created']}")
        print(f"   Mortgages:       {results['mortgages_created']}")
        print(f"   Bills:           {results['bills_created']}")
        print(f"   Income Sources:  {results['income_sources_created']}")
        print(f"   Promo Offers:    {results['promos_created']}")
        
        if results["warnings"]:
            print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
            for warning in results["warnings"][:5]:
                print(f"   • {warning}")
            if len(results["warnings"]) > 5:
                print(f"   ... and {len(results['warnings']) - 5} more")
        
        if results["errors"]:
            print(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results["errors"][:10]:
                print(f"   • {error}")
            if len(results["errors"]) > 10:
                print(f"   ... and {len(results['errors']) - 10} more")
        
        # Offer to save
        if results["success"] or results["banks_created"] > 0:
            save = input("\nSave imported data to database? (y/n): ").strip().lower()
            if save == 'y':
                if self.manager.save_to_database():
                    print("✓ Saved to database")
                else:
                    print("❌ Failed to save")

    def export_to_excel(self):
        """Export current financial data to Excel."""
        print("\n" + "-" * 80)
        print("📤 EXPORT TO EXCEL")
        print("-" * 80)
        
        from models.data_import_export import DataImportExport
        
        exporter = DataImportExport(self.manager)
        
        print("\nExport all your financial data to an Excel file.")
        print("This can be used as a backup or to transfer to another system.")
        
        # Show what will be exported
        print(f"\n📊 Data to export:")
        print(f"   Banks:           {len(self.manager.banks)}")
        print(f"   Bank Accounts:   {sum(len(b.accounts) for b in self.manager.banks)}")
        print(f"   Credit Accounts: {sum(len(b.credit_accounts) for b in self.manager.banks)}")
        print(f"   Mortgages:       {sum(len(b.mortgage_accounts) for b in self.manager.banks)}")
        print(f"   Bills:           {len(self.manager.bills)}")
        print(f"   Income Sources:  {len(self.manager.income_sources)}")
        
        promo_count = sum(
            len(credit.active_promos)
            for bank in self.manager.banks
            for credit in bank.get_all_credit_accounts()
        )
        print(f"   Promo Offers:    {promo_count}")
        
        custom_path = input("\nCustom file path (Enter for Desktop): ").strip()
        filepath = custom_path if custom_path else None
        
        result = exporter.export_current_data(filepath)
        
        if result:
            print(f"\n✓ Data exported to: {result}")
        else:
            print("\n❌ Failed to export data")

    def create_bank_menu(self):
        """Menu for creating banks and accounts."""
        while True:
            print("\n" + "=" * 80)
            print("MANAGE BANKS & ACCOUNTS")
            print("=" * 80)
            print("\n1. Create new bank")
            print("2. Add account to existing bank")
            print("3. List all banks")
            print("4. Update account balance")
            print("5. Update credit balance")
            print("6. Delete account")
            print("7. Delete bank")
            print("8. Transfer between accounts")
            print("9. Back to main menu")

            choice = input("\nSelect option (1-9): ").strip()

            if choice == "1":
                self.create_bank()
            elif choice == "2":
                self.add_account_to_bank()
            elif choice == "3":
                self.list_banks()
            elif choice == "4":
                self.update_account_balance()
            elif choice == "5":
                self.update_credit_balance()
            elif choice == "6":
                self.delete_account()
            elif choice == "7":
                self.delete_bank()
            elif choice == "8":
                self.transfer_between_accounts()
            elif choice == "9":
                break
            else:
                print("❌ Invalid choice.")

    def create_bank(self):
        """Create a new bank."""
        print("\n" + "-" * 80)
        print("CREATE NEW BANK")
        print("-" * 80)

        bank_name = input("\nBank name (e.g., 'Chase Bank'): ").strip()

        if not bank_name:
            print("❌ Bank name cannot be empty.")
            return

        # Check if bank already exists
        if any(b.name == bank_name for b in self.manager.banks):
            print(f"❌ Bank '{bank_name}' already exists.")
            return

        bank_type = input("Bank type (traditional/credit_issuer) [default: traditional]: ").strip().lower()
        if bank_type not in ["traditional", "credit_issuer", ""]:
            print("❌ Invalid bank type. Use 'traditional' or 'credit_issuer'.")
            return
        bank_type = bank_type or "traditional"

        try:
            from models.bank import Bank
            bank = Bank(bank_name, bank_type)
            self.manager.banks.append(bank)
            print(f"✓ Bank '{bank_name}' created successfully")
        except Exception as e:
            print(f"❌ Error creating bank: {e}")

    def add_account_to_bank(self):
        """Add an account to an existing bank."""
        print("\n" + "-" * 80)
        print("ADD ACCOUNT TO BANK")
        print("-" * 80)

        if not self.manager.banks:
            print("\n❌ No banks exist. Create a bank first.")
            return

        # List banks
        print("\nSelect bank:")
        for i, bank in enumerate(self.manager.banks, 1):
            print(f"  {i}. {bank.name}")

        try:
            bank_idx = int(input("\nBank number: ").strip()) - 1
            if not (0 <= bank_idx < len(self.manager.banks)):
                print("❌ Invalid selection.")
                return

            bank = self.manager.banks[bank_idx]

            account_name = input("Account name (e.g., 'Primary Checking'): ").strip()
            if not account_name:
                print("❌ Account name cannot be empty.")
                return

            account_type = input("Account type (checking/savings/credit) [default: checking]: ").strip().lower()
            if account_type not in ["checking", "savings", "credit", ""]:
                print("❌ Invalid type. Use 'checking', 'savings', or 'credit'.")
                return
            account_type = account_type or "checking"

            balance = float(input("Starting balance [$0.00]: ").strip() or "0")
            interest_rate = float(input("Interest rate (APR %) [0]: ").strip() or "0")

            if account_type == "credit":
                credit_limit = float(input("Credit limit: ").strip())
                due_date = input("Payment due date (1-31) [20]: ").strip() or "20"
                statement_date = input("Statement date (1-31) [15]: ").strip() or "15"

                account = bank.add_credit_account(
                    account_name=account_name,
                    credit_limit=credit_limit,
                    interest_rate=interest_rate,
                    payment_due_date=int(due_date),
                    statement_date=int(statement_date)
                )
            else:
                interest_accrual = input("Interest accrual date (1-31) [optional]: ").strip()

                account = bank.add_account(
                    account_type=account_type,
                    account_name=account_name,
                    starting_balance=balance,
                    interest_rate=interest_rate,
                    interest_accrual_date=int(interest_accrual) if interest_accrual else None
                )

            print(f"✓ Account '{account_name}' created successfully in {bank.name}")
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"❌ Error adding account: {e}")

    def list_banks(self):
        """List all banks and their accounts."""
        print("\n" + "-" * 80)
        print("BANKS & ACCOUNTS")
        print("-" * 80)

        if not self.manager.banks:
            print("\nNo banks created yet.")
            return

        for bank in self.manager.banks:
            print(f"\n{bank.name} ({bank.bank_type})")

            if bank.accounts:
                print("  Bank Accounts:")
                for name, account in bank.accounts.items():
                    print(f"    • {name}: ${account.balance:,.2f} ({account.account_type.value})")

            if bank.credit_accounts:
                print("  Credit Accounts:")
                for name, account in bank.credit_accounts.items():
                    print(f"    • {name}: ${account.balance:,.2f} owed (limit: ${account.credit_limit:,.2f})")

            if bank.mortgage_accounts:
                print("  Mortgage Accounts:")
                for name, mortgage in bank.mortgage_accounts.items():
                    print(f"    • {name}: ${mortgage.current_principal:,.2f} owed @ {mortgage.interest_rate}%")

    def update_credit_balance(self):
        """Update a credit account balance."""
        print("\n" + "-" * 80)
        print("UPDATE CREDIT BALANCE")
        print("-" * 80)

        # List credit accounts
        credit_list = []
        for bank in self.manager.banks:
            for name, credit in bank.credit_accounts.items():
                credit_list.append((bank, name, credit))
                print(f"  {len(credit_list)}. {bank.name} - {name}: ${credit.balance:,.2f}")

        if not credit_list:
            print("\nNo credit accounts found.")
            return

        try:
            choice = int(input("\nSelect account (number): ").strip())
            if 1 <= choice <= len(credit_list):
                bank, account_name, credit = credit_list[choice - 1]
                print(f"\nCurrent balance: ${credit.balance:,.2f}")
                new_balance = float(input("Enter new balance: $").strip())
                bank.update_credit_balance(account_name, new_balance, "CLI Update")
                print(f"✓ Updated {account_name} to ${new_balance:,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def delete_account(self):
        """Delete an account from a bank."""
        print("\n" + "-" * 80)
        print("DELETE ACCOUNT")
        print("-" * 80)

        # List all accounts
        account_list = []
        for bank in self.manager.banks:
            for name in bank.accounts:
                account_list.append((bank, "bank", name))
                print(f"  {len(account_list)}. {bank.name} - {name} (Bank Account)")
            for name in bank.credit_accounts:
                account_list.append((bank, "credit", name))
                print(f"  {len(account_list)}. {bank.name} - {name} (Credit Account)")
            for name in bank.mortgage_accounts:
                account_list.append((bank, "mortgage", name))
                print(f"  {len(account_list)}. {bank.name} - {name} (Mortgage)")

        if not account_list:
            print("\nNo accounts found.")
            return

        try:
            choice = int(input("\nSelect account to delete (number): ").strip())
            if 1 <= choice <= len(account_list):
                bank, acc_type, name = account_list[choice - 1]
                confirm = input(f"\nDelete '{name}' from {bank.name}? (y/n): ").strip().lower()
                if confirm == 'y':
                    if acc_type == "bank":
                        del bank.accounts[name]
                    elif acc_type == "credit":
                        del bank.credit_accounts[name]
                    elif acc_type == "mortgage":
                        del bank.mortgage_accounts[name]
                    print(f"\n✓ Account '{name}' deleted from {bank.name}")
                else:
                    print("Cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def delete_bank(self):
        """Delete a bank and all its accounts."""
        print("\n" + "-" * 80)
        print("DELETE BANK")
        print("-" * 80)

        if not self.manager.banks:
            print("\nNo banks to delete.")
            return

        print("\nSelect bank to delete:")
        for i, bank in enumerate(self.manager.banks, 1):
            acc_count = len(bank.accounts) + len(bank.credit_accounts) + len(bank.mortgage_accounts)
            print(f"  {i}. {bank.name} ({acc_count} accounts)")

        try:
            choice = int(input("\nSelect bank (number): ").strip())
            if 1 <= choice <= len(self.manager.banks):
                bank = self.manager.banks[choice - 1]
                acc_count = len(bank.accounts) + len(bank.credit_accounts) + len(bank.mortgage_accounts)
                
                if acc_count > 0:
                    confirm = input(f"\n⚠️  Delete '{bank.name}' and ALL {acc_count} accounts? (type 'DELETE' to confirm): ").strip()
                    if confirm == 'DELETE':
                        self.manager.banks.remove(bank)
                        print(f"\n✓ Bank '{bank.name}' and all accounts deleted")
                    else:
                        print("Cancelled.")
                else:
                    confirm = input(f"\nDelete '{bank.name}'? (y/n): ").strip().lower()
                    if confirm == 'y':
                        self.manager.banks.remove(bank)
                        print(f"\n✓ Bank '{bank.name}' deleted")
                    else:
                        print("Cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def transfer_between_accounts(self):
        """Transfer money between bank accounts."""
        print("\n" + "-" * 80)
        print("TRANSFER BETWEEN ACCOUNTS")
        print("-" * 80)

        # List bank accounts (checking/savings only)
        account_list = []
        for bank in self.manager.banks:
            for name, account in bank.accounts.items():
                account_list.append((bank, name, account))

        if len(account_list) < 2:
            print("\nNeed at least 2 bank accounts for transfers.")
            return

        print("\nSource account:")
        for i, (bank, name, acc) in enumerate(account_list, 1):
            print(f"  {i}. {bank.name} - {name}: ${acc.balance:,.2f}")

        try:
            source_choice = int(input("\nSelect source account (number): ").strip())
            if not (1 <= source_choice <= len(account_list)):
                print("❌ Invalid selection.")
                return
            
            source_bank, source_name, source_acc = account_list[source_choice - 1]

            print("\nDestination account:")
            for i, (bank, name, acc) in enumerate(account_list, 1):
                if i != source_choice:
                    print(f"  {i}. {bank.name} - {name}: ${acc.balance:,.2f}")

            dest_choice = int(input("\nSelect destination account (number): ").strip())
            if not (1 <= dest_choice <= len(account_list)) or dest_choice == source_choice:
                print("❌ Invalid selection.")
                return
            
            dest_bank, dest_name, dest_acc = account_list[dest_choice - 1]

            amount = float(input(f"\nAmount to transfer (max ${source_acc.balance:,.2f}): $").strip())
            
            if amount <= 0:
                print("❌ Amount must be positive.")
                return
            if amount > source_acc.balance:
                print("❌ Insufficient funds.")
                return

            # Perform transfer
            source_acc.withdraw(amount, description=f"Transfer to {dest_name}")
            dest_acc.deposit(amount, description=f"Transfer from {source_name}")
            
            print(f"\n✓ Transferred ${amount:,.2f}")
            print(f"  {source_name}: ${source_acc.balance:,.2f}")
            print(f"  {dest_name}: ${dest_acc.balance:,.2f}")

        except ValueError:
            print("❌ Invalid input.")

    def add_bills_income_menu(self):
        """Menu for adding bills and income sources."""
        while True:
            print("\n" + "=" * 80)
            print("MANAGE BILLS & INCOME")
            print("=" * 80)
            print("\n1. Add bill")
            print("2. Add floating bill")
            print("3. Add income source")
            print("4. List all bills")
            print("5. List all income sources")
            print("6. Edit bill")
            print("7. Delete bill")
            print("8. Edit income source")
            print("9. Delete income source")
            print("10. Back to main menu")

            choice = input("\nSelect option (1-10): ").strip()

            if choice == "1":
                self.add_fixed_bill()
            elif choice == "2":
                self.add_floating_bill()
            elif choice == "3":
                self.add_income()
            elif choice == "4":
                self.list_bills()
            elif choice == "5":
                self.list_income()
            elif choice == "6":
                self.edit_bill()
            elif choice == "7":
                self.delete_bill()
            elif choice == "8":
                self.edit_income()
            elif choice == "9":
                self.delete_income()
            elif choice == "10":
                break
            else:
                print("❌ Invalid choice.")

    def add_fixed_bill(self):
        """Add a fixed bill."""
        print("\n" + "-" * 80)
        print("ADD FIXED BILL")
        print("-" * 80)

        try:
            bill_name = input("\nBill name (e.g., 'Rent'): ").strip()
            amount = float(input("Amount ($): ").strip())
            due_date = int(input("Due date (1-31): ").strip())
            frequency = input("Frequency (monthly/weekly/biweekly/quarterly/semi_annual/yearly) [monthly]: ").strip().lower() or "monthly"

            if not 1 <= due_date <= 31:
                print("❌ Due date must be between 1 and 31.")
                return

            from models.fixed_bill import Bill
            bill = Bill(bill_name, amount, due_date, frequency=frequency)
            self.manager.bills.append(bill)
            print(f"✓ Bill '{bill_name}' added successfully")
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"❌ Error adding bill: {e}")

    def add_floating_bill(self):
        """Add a floating bill."""
        print("\n" + "-" * 80)
        print("ADD FLOATING BILL")
        print("-" * 80)

        try:
            bill_name = input("\nBill name (e.g., 'Utilities'): ").strip()
            estimated = float(input("Estimated amount ($): ").strip())
            due_date = int(input("Due date (1-31): ").strip())
            min_amount = float(input("Minimum amount ($): ").strip())
            max_amount = float(input("Maximum amount ($): ").strip())
            frequency = input("Frequency (monthly/weekly/biweekly/quarterly/yearly) [monthly]: ").strip().lower() or "monthly"

            if not 1 <= due_date <= 31:
                print("❌ Due date must be between 1 and 31.")
                return

            from models.fixed_bill import FloatingBill
            bill = FloatingBill(bill_name, estimated, due_date, min_amount, max_amount, frequency=frequency)
            self.manager.bills.append(bill)
            print(f"✓ Floating bill '{bill_name}' added successfully")
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"❌ Error adding bill: {e}")

    def add_income(self):
        """Add an income source."""
        print("\n" + "-" * 80)
        print("ADD INCOME SOURCE")
        print("-" * 80)

        try:
            source_name = input("\nIncome name (e.g., 'Monthly Salary'): ").strip()
            amount = float(input("Amount ($): ").strip())
            frequency = input("Frequency (monthly/weekly/biweekly/semimonthly/quarterly/yearly) [monthly]: ").strip().lower() or "monthly"
            
            if frequency == "semimonthly":
                # For semimonthly, prompt for two pay dates
                print("\nSemimonthly pay dates (typically 1st and 15th, or 15th and last day of month)")
                pay_date_1_str = input("First pay date (1-31) [15]: ").strip() or "15"
                pay_date_2_str = input("Second pay date (1-31) [31]: ").strip() or "31"
                
                pay_date_1 = int(pay_date_1_str)
                pay_date_2 = int(pay_date_2_str)
                
                if not (1 <= pay_date_1 <= 31 and 1 <= pay_date_2 <= 31):
                    print("❌ Pay dates must be between 1 and 31.")
                    return
                
                pay_date = sorted([pay_date_1, pay_date_2])
                print(f"  Pay dates set to: {pay_date[0]} and {pay_date[1]} of each month")
            else:
                pay_date = int(input("Pay date (1-31) [1]: ").strip() or "1")
                if not 1 <= pay_date <= 31:
                    print("❌ Pay date must be between 1 and 31.")
                    return
                pay_date = [pay_date]

            # Simple distribution: all to first account
            if not self.manager.banks:
                print("❌ No banks exist. Create a bank and account first.")
                return

            first_bank = self.manager.banks[0]
            if not first_bank.accounts:
                print(f"❌ Bank '{first_bank.name}' has no accounts. Add an account first.")
                return

            first_account = next(iter(first_bank.accounts))
            distribution = {first_account: amount}

            from models.income_source import IncomeSource
            income = IncomeSource(source_name, amount, IncomeFrequency(frequency), pay_date, distribution)
            self.manager.income_sources.append(income)
            print(f"✓ Income source '{source_name}' added (${amount:.2f} → {first_account})")
            if frequency == "semimonthly":
                print(f"  Paid on days {pay_date[0]} and {pay_date[1]} of each month")
        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"❌ Error adding income: {e}")

    def list_bills(self):
        """List all bills."""
        print("\n" + "-" * 80)
        print("BILLS")
        print("-" * 80)

        if not self.manager.bills:
            print("\nNo bills created yet.")
            return

        for bill in self.manager.bills:
            bill_type = "floating" if hasattr(bill, 'min_amount') else "fixed"
            print(f"\n• {bill.bill_name}")
            print(f"  Type: {bill_type}")
            print(f"  Amount: ${bill.amount:,.2f}")
            print(f"  Due date: {bill.due_date}")
            print(f"  Frequency: {bill.frequency.value}")

    def list_income(self):
        """List all income sources."""
        print("\n" + "-" * 80)
        print("INCOME SOURCES")
        print("-" * 80)

        if not self.manager.income_sources:
            print("\nNo income sources created yet.")
            return

        for income in self.manager.income_sources:
            print(f"\n• {income.source_name}")
            print(f"  Amount: ${income.amount:,.2f}")
            print(f"  Frequency: {income.frequency.value}")
            
            # Display pay dates properly (handles semimonthly with multiple dates)
            if income.pay_date and len(income.pay_date) > 1:
                pay_dates_str = ", ".join(str(d) for d in sorted(income.pay_date))
                print(f"  Pay dates: {pay_dates_str} of each month")
            elif income.pay_date and len(income.pay_date) == 1:
                print(f"  Pay date: {income.pay_date[0]} of each month")
            else:
                print(f"  Pay date: Not specified")
            
            if income.distribution:
                print(f"  Distribution:")
                for account, value in income.distribution.items():
                    if value == "remainder":
                        print(f"    - {account}: remainder")
                    elif isinstance(value, float) and 0 < value < 1:
                        print(f"    - {account}: {value*100:.0f}%")
                    else:
                        print(f"    - {account}: ${value:,.2f}")

    def edit_bill(self):
        """Edit an existing bill."""
        print("\n" + "-" * 80)
        print("EDIT BILL")
        print("-" * 80)

        if not self.manager.bills:
            print("\nNo bills to edit.")
            return

        # List bills
        print("\nSelect bill to edit:")
        for i, bill in enumerate(self.manager.bills, 1):
            print(f"  {i}. {bill.bill_name} - ${bill.amount:,.2f}")

        try:
            choice = int(input("\nSelect bill (number): ").strip())
            if 1 <= choice <= len(self.manager.bills):
                bill = self.manager.bills[choice - 1]
                
                print(f"\nEditing: {bill.bill_name}")
                print("Press Enter to keep current value")
                
                # Edit name
                new_name = input(f"Bill name [{bill.bill_name}]: ").strip()
                if new_name:
                    bill.bill_name = new_name
                
                # Edit amount
                new_amount = input(f"Amount [${bill.amount:,.2f}]: ").strip()
                if new_amount:
                    bill.amount = float(new_amount)
                
                # Edit due date
                new_due = input(f"Due date [{bill.due_date}]: ").strip()
                if new_due:
                    bill.due_date = int(new_due)
                
                # Edit frequency
                new_freq = input(f"Frequency [{bill.frequency.value}]: ").strip().lower()
                if new_freq:
                    from models.fixed_bill import BillFrequency
                    bill.frequency = BillFrequency(new_freq)
                
                print(f"\n✓ Bill '{bill.bill_name}' updated")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")
        except Exception as e:
            print(f"❌ Error editing bill: {e}")

    def delete_bill(self):
        """Delete an existing bill."""
        print("\n" + "-" * 80)
        print("DELETE BILL")
        print("-" * 80)

        if not self.manager.bills:
            print("\nNo bills to delete.")
            return

        # List bills
        print("\nSelect bill to delete:")
        for i, bill in enumerate(self.manager.bills, 1):
            print(f"  {i}. {bill.bill_name} - ${bill.amount:,.2f}")

        try:
            choice = int(input("\nSelect bill (number): ").strip())
            if 1 <= choice <= len(self.manager.bills):
                bill = self.manager.bills[choice - 1]
                confirm = input(f"\nDelete '{bill.bill_name}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.manager.bills.remove(bill)
                    print(f"\n✓ Bill '{bill.bill_name}' deleted")
                else:
                    print("Cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def edit_income(self):
        """Edit an existing income source."""
        print("\n" + "-" * 80)
        print("EDIT INCOME SOURCE")
        print("-" * 80)

        if not self.manager.income_sources:
            print("\nNo income sources to edit.")
            return

        # List income sources
        print("\nSelect income source to edit:")
        for i, income in enumerate(self.manager.income_sources, 1):
            print(f"  {i}. {income.source_name} - ${income.amount:,.2f}")

        try:
            choice = int(input("\nSelect income (number): ").strip())
            if 1 <= choice <= len(self.manager.income_sources):
                income = self.manager.income_sources[choice - 1]
                
                print(f"\nEditing: {income.source_name}")
                print("Press Enter to keep current value")
                
                # Edit name
                new_name = input(f"Name [{income.source_name}]: ").strip()
                if new_name:
                    income.source_name = new_name
                
                # Edit amount
                new_amount = input(f"Amount [${income.amount:,.2f}]: ").strip()
                if new_amount:
                    income.amount = float(new_amount)
                
                # Edit frequency
                new_freq = input(f"Frequency [{income.frequency.value}]: ").strip().lower()
                if new_freq:
                    income.frequency = IncomeFrequency(new_freq)
                
                # Edit pay dates
                if income.frequency == IncomeFrequency.SEMIMONTHLY:
                    current_dates = ", ".join(str(d) for d in income.pay_date) if income.pay_date else "Not set"
                    print(f"Current pay dates: {current_dates}")
                    new_dates = input("New pay dates (e.g., '15,31' or Enter to keep): ").strip()
                    if new_dates:
                        income.pay_date = [int(d.strip()) for d in new_dates.split(",")]
                else:
                    current_date = income.pay_date[0] if income.pay_date else "Not set"
                    new_date = input(f"Pay date [{current_date}]: ").strip()
                    if new_date:
                        income.pay_date = [int(new_date)]
                
                print(f"\n✓ Income source '{income.source_name}' updated")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")
        except Exception as e:
            print(f"❌ Error editing income: {e}")

    def delete_income(self):
        """Delete an existing income source."""
        print("\n" + "-" * 80)
        print("DELETE INCOME SOURCE")
        print("-" * 80)

        if not self.manager.income_sources:
            print("\nNo income sources to delete.")
            return

        # List income sources
        print("\nSelect income source to delete:")
        for i, income in enumerate(self.manager.income_sources, 1):
            print(f"  {i}. {income.source_name} - ${income.amount:,.2f}")

        try:
            choice = int(input("\nSelect income (number): ").strip())
            if 1 <= choice <= len(self.manager.income_sources):
                income = self.manager.income_sources[choice - 1]
                confirm = input(f"\nDelete '{income.source_name}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.manager.income_sources.remove(income)
                    print(f"\n✓ Income source '{income.source_name}' deleted")
                else:
                    print("Cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def manage_mortgages(self):
        """Manage mortgage accounts."""
        print("\n" + "=" * 80)
        print("MORTGAGE MANAGEMENT")
        print("=" * 80)
        print("\n1. View All Mortgages")
        print("2. Add New Mortgage")
        print("3. Make Mortgage Payment")
        print("4. Make Extra Principal Payment")
        print("5. View Amortization Schedule")
        print("6. Calculate Early Payoff")
        print("7. Back to main menu")

        choice = input("\nSelect option (1-7): ").strip()

        if choice == "1":
            self._view_all_mortgages()
        elif choice == "2":
            self._add_mortgage()
        elif choice == "3":
            self._make_mortgage_payment()
        elif choice == "4":
            self._make_extra_principal_payment()
        elif choice == "5":
            self._view_amortization_schedule()
        elif choice == "6":
            self._calculate_early_payoff()
        elif choice == "7":
            return
        else:
            print("❌ Invalid choice.")

    def _view_all_mortgages(self):
        """View all mortgage accounts."""
        print("\n" + "-" * 80)
        print("ALL MORTGAGES")
        print("-" * 80)

        has_mortgages = False
        for bank in self.manager.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                has_mortgages = True
                print(f"\n{bank.name} - {mortgage.account_name}")
                print(f"  Original Principal: ${mortgage.original_principal:,.2f}")
                print(f"  Current Principal:  ${mortgage.current_principal:,.2f}")
                print(f"  Interest Rate:      {mortgage.interest_rate}%")
                print(f"  Monthly Payment:    ${mortgage.total_monthly_payment:,.2f}")
                print(f"    - P&I:            ${mortgage.base_monthly_payment:,.2f}")
                print(f"    - Escrow:         ${mortgage.escrow.total_monthly:,.2f}")
                print(f"  Equity:             ${mortgage.equity:,.2f} ({(1-mortgage.loan_to_value_ratio)*100:.1f}%)")
                print(f"  Remaining:          ~{mortgage.remaining_months} months")
                print(f"  Est. Payoff Date:   {mortgage.payoff_date}")
                print(f"  Payment Due:        Day {mortgage.payment_due_date} of each month")
                
                if mortgage.escrow.total_monthly > 0:
                    print(f"\n  Escrow Breakdown:")
                    if mortgage.escrow.property_tax_monthly > 0:
                        print(f"    Property Tax:     ${mortgage.escrow.property_tax_monthly:,.2f}/mo")
                    if mortgage.escrow.homeowners_insurance_monthly > 0:
                        print(f"    Insurance:        ${mortgage.escrow.homeowners_insurance_monthly:,.2f}/mo")
                    if mortgage.escrow.pmi_monthly > 0:
                        print(f"    PMI:              ${mortgage.escrow.pmi_monthly:,.2f}/mo")
                    if mortgage.escrow.hoa_monthly > 0:
                        print(f"    HOA:              ${mortgage.escrow.hoa_monthly:,.2f}/mo")
                    print(f"    Escrow Balance:   ${mortgage.escrow_balance:,.2f}")

        if not has_mortgages:
            print("\nNo mortgage accounts found.")

    def _add_mortgage(self):
        """Add a new mortgage account."""
        print("\n" + "-" * 80)
        print("ADD MORTGAGE")
        print("-" * 80)

        # List banks or create new
        print("\nSelect a lender (bank):")
        banks_list = [(i+1, bank) for i, bank in enumerate(self.manager.banks)]
        for i, bank in banks_list:
            print(f"  {i}. {bank.name}")
        print(f"  {len(banks_list)+1}. Create new lender")

        try:
            choice = int(input("\nSelect option: ").strip())
            
            if choice == len(banks_list) + 1:
                # Create new bank
                bank_name = input("Lender name (e.g., 'Wells Fargo Mortgage'): ").strip()
                from models.bank import Bank
                new_bank = Bank(bank_name, "mortgage_lender")
                self.manager.banks.append(new_bank)
                selected_bank = new_bank
                print(f"✓ Created lender: {bank_name}")
            elif 1 <= choice <= len(banks_list):
                selected_bank = banks_list[choice-1][1]
            else:
                print("❌ Invalid selection.")
                return

            # Get mortgage details
            account_name = input("\nMortgage name (e.g., 'Primary Home'): ").strip()
            original_principal = float(input("Original loan amount ($): ").strip())
            current_principal = float(input("Current principal balance ($): ").strip())
            interest_rate = float(input("Interest rate (% APR, e.g., 6.5): ").strip())
            
            print("\nLoan term:")
            print("  1. 30-year (360 months)")
            print("  2. 15-year (180 months)")
            print("  3. Custom")
            term_choice = input("Select (1-3): ").strip()
            
            if term_choice == "1":
                loan_term_months = 360
            elif term_choice == "2":
                loan_term_months = 180
            else:
                loan_term_months = int(input("Enter term in months: ").strip())

            payment_due_date = int(input("Payment due date (1-31) [1]: ").strip() or "1")

            # Escrow details
            print("\nEscrow details (monthly amounts, press Enter to skip):")
            property_tax = float(input("  Property tax ($/mo): ").strip() or "0")
            insurance = float(input("  Homeowners insurance ($/mo): ").strip() or "0")
            pmi = float(input("  PMI ($/mo): ").strip() or "0")
            hoa = float(input("  HOA fees ($/mo): ").strip() or "0")

            from models.mortgage_account import EscrowBreakdown
            escrow = EscrowBreakdown(
                property_tax_monthly=property_tax,
                homeowners_insurance_monthly=insurance,
                pmi_monthly=pmi,
                hoa_monthly=hoa
            )

            # Create mortgage
            mortgage = selected_bank.add_mortgage_account(
                account_name=account_name,
                original_principal=original_principal,
                current_principal=current_principal,
                interest_rate=interest_rate,
                loan_term_months=loan_term_months,
                payment_due_date=payment_due_date,
                escrow=escrow
            )

            print(f"\n✓ Added mortgage: {mortgage}")
            print(f"  Monthly payment: ${mortgage.total_monthly_payment:,.2f}")

        except ValueError:
            print("❌ Invalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"❌ Error adding mortgage: {e}")

    def _make_mortgage_payment(self):
        """Make a regular mortgage payment."""
        print("\n" + "-" * 80)
        print("MAKE MORTGAGE PAYMENT")
        print("-" * 80)

        # List mortgages
        mortgage_list = []
        for bank in self.manager.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                mortgage_list.append((bank.name, mortgage))
                print(f"  {len(mortgage_list)}. {bank.name} - {mortgage.account_name}")
                print(f"      Monthly payment: ${mortgage.total_monthly_payment:,.2f}")

        if not mortgage_list:
            print("\nNo mortgages found.")
            return

        try:
            choice = int(input("\nSelect mortgage (number): ").strip())
            if 1 <= choice <= len(mortgage_list):
                bank_name, mortgage = mortgage_list[choice-1]
                
                print(f"\nStandard payment: ${mortgage.total_monthly_payment:,.2f}")
                amount_str = input(f"Payment amount (Enter for standard): ").strip()
                amount = float(amount_str) if amount_str else None
                
                extra_str = input("Extra principal amount ($, or Enter for none): ").strip()
                extra = float(extra_str) if extra_str else 0.0

                payment = mortgage.make_payment(amount=amount, extra_principal=extra)
                
                print(f"\n✓ Payment recorded:")
                print(f"  Total paid:     ${payment['total_amount']:,.2f}")
                print(f"  Principal:      ${payment['principal']:,.2f}")
                print(f"  Interest:       ${payment['interest']:,.2f}")
                print(f"  Escrow:         ${payment['escrow']:,.2f}")
                if extra > 0:
                    print(f"  Extra principal: ${payment['extra_principal']:,.2f}")
                print(f"  Remaining balance: ${payment['principal_after']:,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _make_extra_principal_payment(self):
        """Make an extra principal-only payment."""
        print("\n" + "-" * 80)
        print("EXTRA PRINCIPAL PAYMENT")
        print("-" * 80)

        # List mortgages
        mortgage_list = []
        for bank in self.manager.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                mortgage_list.append((bank.name, mortgage))
                print(f"  {len(mortgage_list)}. {mortgage.account_name} - Balance: ${mortgage.current_principal:,.2f}")

        if not mortgage_list:
            print("\nNo mortgages found.")
            return

        try:
            choice = int(input("\nSelect mortgage (number): ").strip())
            if 1 <= choice <= len(mortgage_list):
                bank_name, mortgage = mortgage_list[choice-1]
                
                amount = float(input("Extra principal amount ($): ").strip())
                
                payment = mortgage.make_extra_principal_payment(amount)
                
                print(f"\n✓ Extra principal payment of ${amount:,.2f} applied")
                print(f"  New balance: ${payment['principal_after']:,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _view_amortization_schedule(self):
        """View amortization schedule for a mortgage."""
        print("\n" + "-" * 80)
        print("AMORTIZATION SCHEDULE")
        print("-" * 80)

        # List mortgages
        mortgage_list = []
        for bank in self.manager.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                mortgage_list.append((bank.name, mortgage))
                print(f"  {len(mortgage_list)}. {mortgage.account_name}")

        if not mortgage_list:
            print("\nNo mortgages found.")
            return

        try:
            choice = int(input("\nSelect mortgage (number): ").strip())
            if 1 <= choice <= len(mortgage_list):
                bank_name, mortgage = mortgage_list[choice-1]
                
                months = int(input("How many months to show? [12]: ").strip() or "12")
                schedule = mortgage.get_amortization_schedule(months)
                
                print(f"\n{'Month':<6} {'Date':<12} {'Payment':<12} {'Principal':<12} {'Interest':<12} {'Balance':<14}")
                print("-" * 80)
                
                for entry in schedule:
                    print(f"{entry['month']:<6} {str(entry['date']):<12} "
                          f"${entry['payment']:>9,.2f} ${entry['principal']:>9,.2f} "
                          f"${entry['interest']:>9,.2f} ${entry['principal_remaining']:>11,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def _calculate_early_payoff(self):
        """Calculate early payoff scenarios."""
        print("\n" + "-" * 80)
        print("EARLY PAYOFF CALCULATOR")
        print("-" * 80)

        # List mortgages
        mortgage_list = []
        for bank in self.manager.banks:
            for mortgage in bank.get_all_mortgage_accounts():
                mortgage_list.append((bank.name, mortgage))
                print(f"  {len(mortgage_list)}. {mortgage.account_name} - ${mortgage.current_principal:,.2f} remaining")

        if not mortgage_list:
            print("\nNo mortgages found.")
            return

        try:
            choice = int(input("\nSelect mortgage (number): ").strip())
            if 1 <= choice <= len(mortgage_list):
                bank_name, mortgage = mortgage_list[choice-1]
                
                extra = float(input("Extra monthly principal payment ($): ").strip())
                
                result = mortgage.calculate_payoff_with_extra(extra)
                
                print(f"\n📊 Early Payoff Analysis:")
                print(f"  Current payoff: {mortgage.remaining_months} months ({mortgage.payoff_date})")
                print(f"  With ${extra:,.2f}/mo extra:")
                print(f"    New payoff: {result['new_payoff_months']} months ({result['new_payoff_date']})")
                print(f"    Time saved: {result['months_saved']} months ({result['years_saved']:.1f} years)")
                print(f"    Interest saved: ${result['interest_saved']:,.2f}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")

    def credit_payoff_planner(self):
        """Plan credit card/debt payoff."""
        print("\n" + "=" * 80)
        print("CREDIT PAYOFF PLANNER")
        print("=" * 80)
        print("\n1. View All Credit Balances")
        print("2. Generate Payoff Plan for Specific Account")
        print("3. Compare Payoff Strategies")
        print("4. View Promo Expiration Warnings")
        print("5. Back to main menu")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            self._view_all_credit_balances()
        elif choice == "2":
            self._generate_credit_payoff_plan()
        elif choice == "3":
            self._compare_payoff_strategies()
        elif choice == "4":
            self._view_promo_payoff_priority()
        elif choice == "5":
            return
        else:
            print("❌ Invalid choice.")

    def _view_all_credit_balances(self):
        """View all credit account balances."""
        print("\n" + "-" * 80)
        print("CREDIT ACCOUNT BALANCES")
        print("-" * 80)

        total_owed = 0
        total_limit = 0
        
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                total_owed += credit.balance
                total_limit += credit.credit_limit
                utilization = (credit.balance / credit.credit_limit * 100) if credit.credit_limit > 0 else 0
                
                print(f"\n{bank.name} - {credit.account_name}")
                print(f"  Balance:     ${credit.balance:,.2f}")
                print(f"  Limit:       ${credit.credit_limit:,.2f}")
                print(f"  Available:   ${credit.available_credit:,.2f}")
                print(f"  Utilization: {utilization:.1f}%")
                print(f"  APR:         {credit.interest_rate}%")
                print(f"  Min Payment: ${credit.calculate_minimum_payment():,.2f}")
                
                # Show promo balances
                if credit.promo_balance:
                    print(f"  Promo balances:")
                    for promo_name, bal in credit.promo_balance.items():
                        if bal > 0:
                            print(f"    - {promo_name}: ${bal:,.2f}")
                    print(f"  Regular balance: ${credit.regular_balance:,.2f}")

        if total_owed > 0:
            print(f"\n{'='*40}")
            print(f"TOTAL CREDIT DEBT: ${total_owed:,.2f}")
            print(f"TOTAL CREDIT LIMIT: ${total_limit:,.2f}")
            print(f"OVERALL UTILIZATION: {(total_owed/total_limit*100):.1f}%")

    def _generate_credit_payoff_plan(self):
        """Generate a payoff plan for a specific credit account."""
        print("\n" + "-" * 80)
        print("GENERATE PAYOFF PLAN")
        print("-" * 80)

        # List credit accounts
        credit_list = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                if credit.balance > 0:
                    credit_list.append((bank.name, credit.account_name, credit))
                    print(f"  {len(credit_list)}. {credit.account_name} - ${credit.balance:,.2f} @ {credit.interest_rate}%")

        if not credit_list:
            print("\nNo credit accounts with balances found.")
            return

        try:
            choice = int(input("\nSelect account (number): ").strip())
            if 1 <= choice <= len(credit_list):
                bank_name, account_name, credit = credit_list[choice-1]
                
                months = int(input("Payoff timeframe (months) [12]: ").strip() or "12")
                
                from models.payment_optimizer import PaymentOptimizer
                optimizer = PaymentOptimizer(
                    self.manager.banks,
                    self.manager.income_sources,
                    self.manager.bills
                )
                
                plan = optimizer.get_credit_payoff_plan(account_name, months)
                
                print(f"\n📊 Payoff Plan for {account_name}:")
                print(f"  Target account: {account_name}")
                print(f"  Current balance: ${credit.balance:,.2f}")
                print(f"  Timeframe: {months} months")
                print(f"\n  Promo payoffs scheduled: {len(plan.promo_payoff_schedule)}")
                for p in plan.promo_payoff_schedule[:5]:
                    print(f"    - {p['date']}: ${p['amount']:,.2f} to {p['promo_name']}")
                
                print(f"\n  Extra payments to {account_name}: {len(plan.extra_credit_payments)}")
                total_extra = sum(p['amount'] for p in plan.extra_credit_payments)
                print(f"    Total: ${total_extra:,.2f}")
                
                print(f"\n  Final discretionary funds: ${plan.final_discretionary:,.2f}")
                
                if plan.violations:
                    print(f"\n  ⚠️ Warnings:")
                    for v in plan.violations[:3]:
                        print(f"    - {v}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")
        except Exception as e:
            print(f"❌ Error generating plan: {e}")

    def _compare_payoff_strategies(self):
        """Compare different payoff strategies."""
        print("\n" + "-" * 80)
        print("COMPARE PAYOFF STRATEGIES")
        print("-" * 80)

        try:
            months = int(input("Analysis period (months) [6]: ").strip() or "6")
            
            from models.payment_optimizer import PaymentOptimizer
            optimizer = PaymentOptimizer(
                self.manager.banks,
                self.manager.income_sources,
                self.manager.bills
            )
            
            end_date = date.today() + timedelta(days=30 * months)
            
            print("\nAnalyzing strategies...")
            
            # Get maximize discretionary plan
            plan1 = optimizer.optimize_payment_schedule(date.today(), end_date, "maximize_discretionary")
            
            # Get minimize interest plan
            plan2 = optimizer.optimize_payment_schedule(date.today(), end_date, "minimize_interest")
            
            print(f"\n{'Strategy':<25} {'Discretionary':<15} {'Interest':<12} {'Promos':<10}")
            print("-" * 65)
            print(f"{'Maximize Cash':<25} ${plan1.final_discretionary:>12,.2f} ${plan1.total_interest_paid:>9,.2f} {len(plan1.promo_payoff_schedule):>8}")
            print(f"{'Minimize Interest':<25} ${plan2.final_discretionary:>12,.2f} ${plan2.total_interest_paid:>9,.2f} {len(plan2.promo_payoff_schedule):>8}")
            
            # Recommendations
            print(f"\n💡 Recommendation:")
            if plan1.final_discretionary > plan2.final_discretionary:
                print(f"  'Maximize Cash' leaves you with ${plan1.final_discretionary - plan2.final_discretionary:,.2f} more")
            else:
                print(f"  'Minimize Interest' saves ${plan2.final_discretionary - plan1.final_discretionary:,.2f} in interest")
                
        except ValueError:
            print("❌ Invalid input.")
        except Exception as e:
            print(f"❌ Error comparing strategies: {e}")
