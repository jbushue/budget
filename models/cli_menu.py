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
            choice = input("\nSelect an option (1-13): ").strip()

            if choice == "1":
                self.view_snapshot()
            elif choice == "2":
                self.update_account_balance()
            elif choice == "3":
                self.project_balances()
            elif choice == "4":
                self.view_upcoming_bills()
            elif choice == "5":
                self.view_upcoming_income()
            elif choice == "6":
                self.optimize_payments()
            elif choice == "7":
                self.add_promotional_offer()
            elif choice == "8":
                self.view_reports()
            elif choice == "9":
                self.view_detailed_timeline()
            elif choice == "10":
                self.create_bank_menu()
            elif choice == "11":
                self.add_bills_income_menu()
            elif choice == "12":
                self.database_management()
            elif choice == "13":
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
        print("2.  Update Account Balance")
        print("3.  Project Balance on Specific Date")
        print("4.  View Upcoming Bills (Next 60 days)")
        print("5.  View Upcoming Income (Next 60 days)")
        print("6.  Get Payment Optimization Recommendations")
        print("7.  Add Promotional Offer to Credit Card")
        print("8.  Generate Financial Reports")
        print("9.  View Detailed Timeline")
        print("10. Create Banks & Accounts")
        print("11. Add Bills & Income")
        print("12. Database & File Management")
        print("13. Exit")

    def view_snapshot(self):
        """View current financial snapshot."""
        print("\n" + "=" * 80)
        print("CURRENT FINANCIAL SNAPSHOT")
        print("=" * 80)
        print(self.manager.generate_snapshot())

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
            print(f"  Total Interest: ${plan.total_interest_paid:,.2f}")
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
                    amount = f"${bill.amount:,.2f}" if bill else "Amount unknown"

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

            if plan.violations:
                print(f"\n  ⚠️  ISSUES DETECTED:")
                print(f"  {'-' * 76}")
                for violation in plan.violations:
                    print(f"    • {violation}")
            else:
                print(f"\n  ✓ No issues detected - plan is feasible")

        except ValueError:
            print("❌ Invalid input.")

    def add_promotional_offer(self):
        """Add promotional offer to a credit card."""
        print("\n" + "=" * 80)
        print("ADD PROMOTIONAL OFFER")
        print("=" * 80)

        # List credit accounts
        credit_accounts = []
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                credit_accounts.append((bank.name, credit.account_name, credit))
                print(f"  {len(credit_accounts)}. {bank.name} - {credit.account_name}")

        if not credit_accounts:
            print("\nNo credit accounts found.")
            return

        choice = input("\nSelect credit card (number): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(credit_accounts):
                bank_name, account_name, credit = credit_accounts[idx]

                promo_name = input("Promotion name (e.g., '0% APR 12 months'): ").strip()
                months = int(input("Months interest-free: ").strip())
                limit_str = input("Purchase limit ($, or press Enter for unlimited): ").strip()
                limit = float(limit_str) if limit_str else None

                promo = credit.add_promotional_offer(promo_name, months, limit)
                print(f"\n✓ Added promotion: {promo}")
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
            print("4. Back to main menu")

            choice = input("\nSelect option (1-4): ").strip()

            if choice == "1":
                self.save_to_database()
            elif choice == "2":
                self.load_from_database()
            elif choice == "3":
                self.view_database_info()
            elif choice == "4":
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

    def create_bank_menu(self):
        """Menu for creating banks and accounts."""
        while True:
            print("\n" + "=" * 80)
            print("CREATE BANKS & ACCOUNTS")
            print("=" * 80)
            print("\n1. Create new bank")
            print("2. Add account to existing bank")
            print("3. List all banks")
            print("4. Back to main menu")

            choice = input("\nSelect option (1-4): ").strip()

            if choice == "1":
                self.create_bank()
            elif choice == "2":
                self.add_account_to_bank()
            elif choice == "3":
                self.list_banks()
            elif choice == "4":
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

    def add_bills_income_menu(self):
        """Menu for adding bills and income sources."""
        while True:
            print("\n" + "=" * 80)
            print("ADD BILLS & INCOME")
            print("=" * 80)
            print("\n1. Add bill")
            print("2. Add floating bill")
            print("3. Add income source")
            print("4. List all bills")
            print("5. List all income sources")
            print("6. Back to main menu")

            choice = input("\nSelect option (1-6): ").strip()

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
                pay_date = [15, 31]
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
            print(f"  Pay date: {income.pay_date}")
            if income.distribution:
                print(f"  Distribution:")
                for account, value in income.distribution.items():
                    if value == "remainder":
                        print(f"    - {account}: remainder")
                    elif isinstance(value, float) and 0 < value < 1:
                        print(f"    - {account}: {value*100:.0f}%")
                    else:
                        print(f"    - {account}: ${value:,.2f}")

