"""
Data Import/Export module for bulk loading financial data from Excel.
Supports importing banks, accounts, bills, income sources, mortgages, and promotional offers.
"""

import os
from datetime import date, timedelta
from typing import Optional

# Try to import openpyxl, provide helpful message if not available
try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class DataImportExport:
    """Handles bulk import/export of financial data via Excel files."""

    def __init__(self, manager=None):
        """
        Args:
            manager: FinanceManager instance (optional for template generation)
        """
        self.manager = manager

    @staticmethod
    def check_openpyxl():
        """Check if openpyxl is available."""
        if not OPENPYXL_AVAILABLE:
            print("\n⚠️  Excel import/export requires 'openpyxl' package.")
            print("Install it with: pip install openpyxl")
            print("   or: uv add openpyxl")
            return False
        return True

    def generate_template(self, filepath: str = None) -> str:
        """
        Generate an Excel template file with all required sheets and headers.
        
        Args:
            filepath: Path to save the template (default: Desktop)
            
        Returns:
            Path to the generated template file
        """
        if not self.check_openpyxl():
            return None

        if filepath is None:
            filepath = os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                f"budget_template_{date.today().strftime('%Y%m%d')}.xlsx"
            )

        wb = Workbook()
        
        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        required_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        optional_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        example_font = Font(italic=True, color="808080")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # ========== INSTRUCTIONS SHEET ==========
        ws_instructions = wb.active
        ws_instructions.title = "Instructions"
        
        instructions = [
            ("BUDGET DATA IMPORT TEMPLATE", None),
            ("", None),
            ("This template allows you to bulk import your financial data.", None),
            ("Fill out each sheet with your information and save the file.", None),
            ("Then use the CLI option 'Import from Excel' to load the data.", None),
            ("", None),
            ("SHEET DESCRIPTIONS:", None),
            ("", None),
            ("1. Banks - Define your financial institutions", None),
            ("2. Bank_Accounts - Checking and savings accounts", None),
            ("3. Credit_Accounts - Credit cards and lines of credit", None),
            ("4. Mortgages - Home loans with escrow details", None),
            ("5. Bills - Recurring bills and expenses", None),
            ("6. Income - Income sources and pay schedules", None),
            ("7. Promo_Offers - Promotional 0% APR offers on credit cards", None),
            ("", None),
            ("TIPS:", None),
            ("• Orange columns are REQUIRED", None),
            ("• Green columns are OPTIONAL", None),
            ("• Dates should be in YYYY-MM-DD format or Excel date format", None),
            ("• Amounts should be numbers without $ or commas", None),
            ("• Example rows are provided - DELETE them before importing", None),
        ]
        
        for row_num, (text, _) in enumerate(instructions, 1):
            cell = ws_instructions.cell(row=row_num, column=1, value=text)
            if row_num == 1:
                cell.font = Font(bold=True, size=16)
            elif text.endswith(":"):
                cell.font = Font(bold=True)
        
        ws_instructions.column_dimensions['A'].width = 80

        # ========== BANKS SHEET ==========
        ws_banks = wb.create_sheet("Banks")
        banks_headers = [
            ("bank_name", True, "Name of the bank/institution"),
            ("bank_type", False, "traditional, credit_issuer, or mortgage_lender"),
        ]
        self._setup_sheet(ws_banks, banks_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add example row
        ws_banks.cell(row=3, column=1, value="Chase Bank").font = example_font
        ws_banks.cell(row=3, column=2, value="traditional").font = example_font
        ws_banks.cell(row=4, column=1, value="Discover").font = example_font
        ws_banks.cell(row=4, column=2, value="credit_issuer").font = example_font

        # ========== BANK ACCOUNTS SHEET ==========
        ws_accounts = wb.create_sheet("Bank_Accounts")
        accounts_headers = [
            ("bank_name", True, "Must match a name in Banks sheet"),
            ("account_name", True, "Name for this account"),
            ("account_type", True, "checking or savings"),
            ("balance", True, "Current balance"),
            ("interest_rate", False, "APR % for savings accounts"),
            ("interest_accrual_date", False, "Day of month (1-31) for interest"),
        ]
        self._setup_sheet(ws_accounts, accounts_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add examples
        ws_accounts.cell(row=3, column=1, value="Chase Bank").font = example_font
        ws_accounts.cell(row=3, column=2, value="Primary Checking").font = example_font
        ws_accounts.cell(row=3, column=3, value="checking").font = example_font
        ws_accounts.cell(row=3, column=4, value=5000.00).font = example_font
        
        ws_accounts.cell(row=4, column=1, value="Chase Bank").font = example_font
        ws_accounts.cell(row=4, column=2, value="Savings").font = example_font
        ws_accounts.cell(row=4, column=3, value="savings").font = example_font
        ws_accounts.cell(row=4, column=4, value=10000.00).font = example_font
        ws_accounts.cell(row=4, column=5, value=4.5).font = example_font
        ws_accounts.cell(row=4, column=6, value=1).font = example_font

        # ========== CREDIT ACCOUNTS SHEET ==========
        ws_credit = wb.create_sheet("Credit_Accounts")
        credit_headers = [
            ("bank_name", True, "Must match a name in Banks sheet"),
            ("account_name", True, "Name for this credit account"),
            ("credit_limit", True, "Credit limit"),
            ("balance", True, "Current balance owed"),
            ("interest_rate", True, "APR %"),
            ("payment_due_date", False, "Day of month (1-31)"),
            ("statement_date", False, "Day of month (1-31)"),
        ]
        self._setup_sheet(ws_credit, credit_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add examples
        ws_credit.cell(row=3, column=1, value="Discover").font = example_font
        ws_credit.cell(row=3, column=2, value="Discover It").font = example_font
        ws_credit.cell(row=3, column=3, value=10000).font = example_font
        ws_credit.cell(row=3, column=4, value=2500.50).font = example_font
        ws_credit.cell(row=3, column=5, value=24.99).font = example_font
        ws_credit.cell(row=3, column=6, value=20).font = example_font
        ws_credit.cell(row=3, column=7, value=15).font = example_font

        # ========== MORTGAGES SHEET ==========
        ws_mortgage = wb.create_sheet("Mortgages")
        mortgage_headers = [
            ("bank_name", True, "Lender name (will be created if not in Banks)"),
            ("account_name", True, "Name for this mortgage"),
            ("original_principal", True, "Original loan amount"),
            ("current_principal", True, "Current principal balance"),
            ("interest_rate", True, "APR %"),
            ("loan_term_months", True, "Total term (e.g., 360 for 30-year)"),
            ("payment_due_date", False, "Day of month (1-31)"),
            ("property_tax_monthly", False, "Monthly escrow for property tax"),
            ("insurance_monthly", False, "Monthly escrow for insurance"),
            ("pmi_monthly", False, "Monthly PMI if applicable"),
            ("hoa_monthly", False, "Monthly HOA fees if applicable"),
        ]
        self._setup_sheet(ws_mortgage, mortgage_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add example
        ws_mortgage.cell(row=3, column=1, value="Wells Fargo Mortgage").font = example_font
        ws_mortgage.cell(row=3, column=2, value="Primary Home").font = example_font
        ws_mortgage.cell(row=3, column=3, value=350000).font = example_font
        ws_mortgage.cell(row=3, column=4, value=320000).font = example_font
        ws_mortgage.cell(row=3, column=5, value=6.5).font = example_font
        ws_mortgage.cell(row=3, column=6, value=360).font = example_font
        ws_mortgage.cell(row=3, column=7, value=1).font = example_font
        ws_mortgage.cell(row=3, column=8, value=350).font = example_font
        ws_mortgage.cell(row=3, column=9, value=150).font = example_font
        ws_mortgage.cell(row=3, column=10, value=0).font = example_font
        ws_mortgage.cell(row=3, column=11, value=0).font = example_font

        # ========== BILLS SHEET ==========
        ws_bills = wb.create_sheet("Bills")
        bills_headers = [
            ("bill_name", True, "Name of the bill"),
            ("amount", True, "Bill amount"),
            ("due_date", True, "Day of month (1-31)"),
            ("due_month", False, "Month (1-12) for yearly/semi-annual bills"),
            ("frequency", False, "monthly, weekly, biweekly, quarterly, semi_annual, yearly"),
            ("is_floating", False, "TRUE if amount varies, FALSE if fixed"),
            ("min_amount", False, "Minimum amount (for floating bills)"),
            ("max_amount", False, "Maximum amount (for floating bills)"),
            ("preferred_bank", False, "Preferred bank to pay from"),
            ("preferred_account", False, "Preferred account to pay from"),
        ]
        self._setup_sheet(ws_bills, bills_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add examples
        example_bills = [
            ("Rent/Mortgage", 2000, 1, None, "monthly", False, None, None, None, None),
            ("Electric", 150, 15, None, "monthly", True, 80, 250, None, None),
            ("Car Insurance", 180, 20, None, "monthly", False, None, None, None, None),
            ("Property Tax", 1200, 15, 4, "yearly", False, None, None, None, None),
            ("Netflix", 15.99, 5, None, "monthly", False, None, None, None, None),
        ]
        for row_num, bill in enumerate(example_bills, 3):
            for col_num, value in enumerate(bill, 1):
                if value is not None:
                    ws_bills.cell(row=row_num, column=col_num, value=value).font = example_font

        # ========== INCOME SHEET ==========
        ws_income = wb.create_sheet("Income")
        income_headers = [
            ("source_name", True, "Name of income source"),
            ("amount", True, "Amount per pay period"),
            ("frequency", True, "monthly, weekly, biweekly, semimonthly"),
            ("pay_date_1", True, "First pay date (day 1-31)"),
            ("pay_date_2", False, "Second pay date for semimonthly"),
            ("deposit_account", False, "Account to deposit into"),
            ("deposit_bank", False, "Bank for deposit account"),
        ]
        self._setup_sheet(ws_income, income_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add examples
        ws_income.cell(row=3, column=1, value="Salary").font = example_font
        ws_income.cell(row=3, column=2, value=3500).font = example_font
        ws_income.cell(row=3, column=3, value="semimonthly").font = example_font
        ws_income.cell(row=3, column=4, value=15).font = example_font
        ws_income.cell(row=3, column=5, value=31).font = example_font
        ws_income.cell(row=3, column=6, value="Primary Checking").font = example_font
        ws_income.cell(row=3, column=7, value="Chase Bank").font = example_font
        
        ws_income.cell(row=4, column=1, value="Side Gig").font = example_font
        ws_income.cell(row=4, column=2, value=500).font = example_font
        ws_income.cell(row=4, column=3, value="monthly").font = example_font
        ws_income.cell(row=4, column=4, value=1).font = example_font

        # ========== PROMO OFFERS SHEET ==========
        ws_promos = wb.create_sheet("Promo_Offers")
        promo_headers = [
            ("credit_account_name", True, "Must match a Credit Account name"),
            ("promo_name", True, "Name for this promotion"),
            ("months_interest_free", True, "Number of months at 0%"),
            ("purchase_limit", False, "Maximum amount for promo"),
            ("current_balance", False, "Current balance on this promo"),
            ("start_date", False, "When promo started (YYYY-MM-DD)"),
        ]
        self._setup_sheet(ws_promos, promo_headers, header_font, header_fill,
                         required_fill, optional_fill, thin_border)
        
        # Add example
        ws_promos.cell(row=3, column=1, value="Discover It").font = example_font
        ws_promos.cell(row=3, column=2, value="0% APR 18 months").font = example_font
        ws_promos.cell(row=3, column=3, value=18).font = example_font
        ws_promos.cell(row=3, column=4, value=5000).font = example_font
        ws_promos.cell(row=3, column=5, value=2000).font = example_font
        ws_promos.cell(row=3, column=6, value="2025-06-01").font = example_font

        # Save the workbook
        wb.save(filepath)
        return filepath

    def _setup_sheet(self, ws, headers, header_font, header_fill,
                     required_fill, optional_fill, thin_border):
        """Set up a worksheet with headers and formatting."""
        # Add header row
        for col_num, (header_name, is_required, description) in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
            
            # Add description row
            desc_cell = ws.cell(row=2, column=col_num, value=description)
            desc_cell.font = Font(italic=True, size=9)
            desc_cell.fill = required_fill if is_required else optional_fill
            desc_cell.border = thin_border
            desc_cell.alignment = Alignment(wrap_text=True)
            
            # Set column width
            ws.column_dimensions[get_column_letter(col_num)].width = max(len(header_name) + 5, 15)

        # Freeze the header rows
        ws.freeze_panes = 'A3'

    def import_from_excel(self, filepath: str) -> dict:
        """
        Import financial data from an Excel file.
        
        Args:
            filepath: Path to the Excel file to import
            
        Returns:
            Dictionary with import results and any errors
        """
        if not self.check_openpyxl():
            return {"success": False, "error": "openpyxl not installed"}

        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}"}

        results = {
            "success": True,
            "banks_created": 0,
            "bank_accounts_created": 0,
            "credit_accounts_created": 0,
            "mortgages_created": 0,
            "bills_created": 0,
            "income_sources_created": 0,
            "promos_created": 0,
            "errors": [],
            "warnings": []
        }

        try:
            wb = load_workbook(filepath)
            
            # Import in order of dependencies
            self._import_banks(wb, results)
            self._import_bank_accounts(wb, results)
            self._import_credit_accounts(wb, results)
            self._import_mortgages(wb, results)
            self._import_bills(wb, results)
            self._import_income(wb, results)
            self._import_promos(wb, results)
            
            if results["errors"]:
                results["success"] = False
                
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Failed to read Excel file: {str(e)}")

        return results

    def import_data(self, filepath: str) -> dict:
        """Alias for import_from_excel."""
        return self.import_from_excel(filepath)

    def _import_banks(self, wb, results: dict):
        """Import banks from the Banks sheet."""
        if "Banks" not in wb.sheetnames:
            results["warnings"].append("Banks sheet not found, skipping")
            return

        from models.bank import Bank
        
        ws = wb["Banks"]
        for row_num in range(3, ws.max_row + 1):  # Start from row 3 (after header and description)
            bank_name = ws.cell(row=row_num, column=1).value
            bank_type = ws.cell(row=row_num, column=2).value or "traditional"
            
            if not bank_name:
                continue
            
            # Skip example rows (italic text)
            if str(bank_name).startswith("Chase Bank") and row_num == 3:
                continue
                
            try:
                # Check if bank already exists
                existing = next((b for b in self.manager.banks if b.name == bank_name), None)
                if existing:
                    results["warnings"].append(f"Bank '{bank_name}' already exists, skipping")
                    continue
                
                bank = Bank(bank_name, bank_type)
                self.manager.banks.append(bank)
                results["banks_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create bank '{bank_name}': {str(e)}")

    def _import_bank_accounts(self, wb, results: dict):
        """Import bank accounts from the Bank_Accounts sheet."""
        if "Bank_Accounts" not in wb.sheetnames:
            results["warnings"].append("Bank_Accounts sheet not found, skipping")
            return

        ws = wb["Bank_Accounts"]
        for row_num in range(3, ws.max_row + 1):
            bank_name = ws.cell(row=row_num, column=1).value
            account_name = ws.cell(row=row_num, column=2).value
            account_type = ws.cell(row=row_num, column=3).value
            balance = ws.cell(row=row_num, column=4).value
            interest_rate = ws.cell(row=row_num, column=5).value or 0
            interest_accrual = ws.cell(row=row_num, column=6).value
            
            if not bank_name or not account_name:
                continue
                
            try:
                bank = next((b for b in self.manager.banks if b.name == bank_name), None)
                if not bank:
                    results["errors"].append(f"Row {row_num}: Bank '{bank_name}' not found")
                    continue
                
                bank.add_account(
                    account_type=account_type or "checking",
                    account_name=account_name,
                    starting_balance=float(balance or 0),
                    interest_rate=float(interest_rate),
                    interest_accrual_date=int(interest_accrual) if interest_accrual else None
                )
                results["bank_accounts_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create account '{account_name}': {str(e)}")

    def _import_credit_accounts(self, wb, results: dict):
        """Import credit accounts from the Credit_Accounts sheet."""
        if "Credit_Accounts" not in wb.sheetnames:
            results["warnings"].append("Credit_Accounts sheet not found, skipping")
            return

        ws = wb["Credit_Accounts"]
        for row_num in range(3, ws.max_row + 1):
            bank_name = ws.cell(row=row_num, column=1).value
            account_name = ws.cell(row=row_num, column=2).value
            credit_limit = ws.cell(row=row_num, column=3).value
            balance = ws.cell(row=row_num, column=4).value
            interest_rate = ws.cell(row=row_num, column=5).value
            due_date = ws.cell(row=row_num, column=6).value
            statement_date = ws.cell(row=row_num, column=7).value
            
            if not bank_name or not account_name:
                continue
                
            try:
                bank = next((b for b in self.manager.banks if b.name == bank_name), None)
                if not bank:
                    results["errors"].append(f"Row {row_num}: Bank '{bank_name}' not found")
                    continue
                
                credit = bank.add_credit_account(
                    account_name=account_name,
                    credit_limit=float(credit_limit or 0),
                    interest_rate=float(interest_rate or 0),
                    payment_due_date=int(due_date) if due_date else None,
                    statement_date=int(statement_date) if statement_date else None
                )
                
                # Set initial balance
                if balance and float(balance) > 0:
                    credit.balance = float(balance)
                    credit.regular_balance = float(balance)
                    
                results["credit_accounts_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create credit account '{account_name}': {str(e)}")

    def _import_mortgages(self, wb, results: dict):
        """Import mortgages from the Mortgages sheet."""
        if "Mortgages" not in wb.sheetnames:
            results["warnings"].append("Mortgages sheet not found, skipping")
            return

        from models.bank import Bank
        from models.mortgage_account import EscrowBreakdown

        ws = wb["Mortgages"]
        for row_num in range(3, ws.max_row + 1):
            bank_name = ws.cell(row=row_num, column=1).value
            account_name = ws.cell(row=row_num, column=2).value
            original_principal = ws.cell(row=row_num, column=3).value
            current_principal = ws.cell(row=row_num, column=4).value
            interest_rate = ws.cell(row=row_num, column=5).value
            loan_term = ws.cell(row=row_num, column=6).value
            due_date = ws.cell(row=row_num, column=7).value
            prop_tax = ws.cell(row=row_num, column=8).value
            insurance = ws.cell(row=row_num, column=9).value
            pmi = ws.cell(row=row_num, column=10).value
            hoa = ws.cell(row=row_num, column=11).value
            
            if not bank_name or not account_name:
                continue
                
            try:
                # Find or create bank
                bank = next((b for b in self.manager.banks if b.name == bank_name), None)
                if not bank:
                    bank = Bank(bank_name, "mortgage_lender")
                    self.manager.banks.append(bank)
                    results["banks_created"] += 1
                
                escrow = EscrowBreakdown(
                    property_tax_monthly=float(prop_tax or 0),
                    homeowners_insurance_monthly=float(insurance or 0),
                    pmi_monthly=float(pmi or 0),
                    hoa_monthly=float(hoa or 0)
                )
                
                bank.add_mortgage_account(
                    account_name=account_name,
                    original_principal=float(original_principal or 0),
                    current_principal=float(current_principal or 0),
                    interest_rate=float(interest_rate or 0),
                    loan_term_months=int(loan_term or 360),
                    payment_due_date=int(due_date) if due_date else 1,
                    escrow=escrow
                )
                results["mortgages_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create mortgage '{account_name}': {str(e)}")

    def _import_bills(self, wb, results: dict):
        """Import bills from the Bills sheet."""
        if "Bills" not in wb.sheetnames:
            results["warnings"].append("Bills sheet not found, skipping")
            return

        from models.fixed_bill import Bill, FloatingBill

        ws = wb["Bills"]
        for row_num in range(3, ws.max_row + 1):
            bill_name = ws.cell(row=row_num, column=1).value
            amount = ws.cell(row=row_num, column=2).value
            due_date = ws.cell(row=row_num, column=3).value
            due_month = ws.cell(row=row_num, column=4).value
            frequency = ws.cell(row=row_num, column=5).value or "monthly"
            is_floating = ws.cell(row=row_num, column=6).value
            min_amount = ws.cell(row=row_num, column=7).value
            max_amount = ws.cell(row=row_num, column=8).value
            pref_bank = ws.cell(row=row_num, column=9).value
            pref_account = ws.cell(row=row_num, column=10).value

            if not bill_name or not amount:
                continue
                
            try:
                # Convert due_month to int if provided
                due_month_int = None
                if due_month is not None:
                    due_month_int = int(due_month)
                
                # Check if floating
                if is_floating and str(is_floating).upper() == "TRUE":
                    bill = FloatingBill(
                        bill_name=bill_name,
                        estimated_amount=float(amount),
                        due_date=int(due_date or 1),
                        min_amount=float(min_amount or amount * 0.5),
                        max_amount=float(max_amount or amount * 1.5),
                        frequency=frequency,
                        due_month=due_month_int
                    )
                else:
                    bill = Bill(
                        bill_name=bill_name,
                        amount=float(amount),
                        due_date=int(due_date or 1),
                        frequency=frequency,
                        due_month=due_month_int
                    )
                
                # Set payment preferences
                if pref_bank:
                    bill.preferred_source_bank = pref_bank
                if pref_account:
                    bill.preferred_source_account = pref_account
                    
                self.manager.bills.append(bill)
                results["bills_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create bill '{bill_name}': {str(e)}")

    def _import_income(self, wb, results: dict):
        """Import income sources from the Income sheet."""
        if "Income" not in wb.sheetnames:
            results["warnings"].append("Income sheet not found, skipping")
            return

        from models.income_source import IncomeSource, IncomeFrequency

        ws = wb["Income"]
        for row_num in range(3, ws.max_row + 1):
            source_name = ws.cell(row=row_num, column=1).value
            amount = ws.cell(row=row_num, column=2).value
            frequency = ws.cell(row=row_num, column=3).value or "monthly"
            pay_date_1 = ws.cell(row=row_num, column=4).value
            pay_date_2 = ws.cell(row=row_num, column=5).value
            deposit_account = ws.cell(row=row_num, column=6).value
            deposit_bank = ws.cell(row=row_num, column=7).value
            
            if not source_name or not amount:
                continue
                
            try:
                # Build pay dates list
                pay_dates = []
                if pay_date_1:
                    pay_dates.append(int(pay_date_1))
                if pay_date_2:
                    pay_dates.append(int(pay_date_2))
                if not pay_dates:
                    pay_dates = [1]  # Default to 1st of month
                
                # Build distribution
                distribution = None
                if deposit_account:
                    distribution = {deposit_account: float(amount)}
                
                income = IncomeSource(
                    source_name=source_name,
                    amount=float(amount),
                    frequency=IncomeFrequency(frequency.lower()),
                    pay_date=pay_dates,
                    distribution=distribution
                )
                
                self.manager.income_sources.append(income)
                results["income_sources_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create income '{source_name}': {str(e)}")

    def _import_promos(self, wb, results: dict):
        """Import promotional offers from the Promo_Offers sheet."""
        if "Promo_Offers" not in wb.sheetnames:
            results["warnings"].append("Promo_Offers sheet not found, skipping")
            return

        ws = wb["Promo_Offers"]
        for row_num in range(3, ws.max_row + 1):
            credit_account = ws.cell(row=row_num, column=1).value
            promo_name = ws.cell(row=row_num, column=2).value
            months = ws.cell(row=row_num, column=3).value
            limit = ws.cell(row=row_num, column=4).value
            balance = ws.cell(row=row_num, column=5).value
            start_date_val = ws.cell(row=row_num, column=6).value
            
            if not credit_account or not promo_name:
                continue
                
            try:
                # Find credit account
                credit = None
                for bank in self.manager.banks:
                    credit = bank.get_credit_account(credit_account)
                    if credit:
                        break
                
                if not credit:
                    results["errors"].append(f"Row {row_num}: Credit account '{credit_account}' not found")
                    continue
                
                # Parse start date
                start_date = None
                if start_date_val:
                    if isinstance(start_date_val, date):
                        start_date = start_date_val
                    else:
                        start_date = date.fromisoformat(str(start_date_val))
                
                promo = credit.add_promotional_offer(
                    promo_name=promo_name,
                    months_interest_free=int(months or 12),
                    purchase_limit=float(limit) if limit else None
                )
                
                if start_date:
                    promo.start_date = start_date
                    promo.end_date = start_date + timedelta(days=30 * int(months or 12))
                
                # Set promo balance
                if balance and float(balance) > 0:
                    credit.promo_balance[promo_name] = float(balance)
                    promo.amount_used = float(balance)
                    # Adjust regular balance
                    credit.regular_balance = max(0, credit.balance - float(balance))
                    
                results["promos_created"] += 1
            except Exception as e:
                results["errors"].append(f"Row {row_num}: Failed to create promo '{promo_name}': {str(e)}")

    def export_current_data(self, filepath: str = None) -> str:
        """
        Export current financial data to an Excel file.
        
        Args:
            filepath: Path to save the export (default: Desktop)
            
        Returns:
            Path to the exported file
        """
        if not self.check_openpyxl():
            return None

        if filepath is None:
            filepath = os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                f"budget_export_{date.today().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )

        wb = Workbook()
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

        # ========== BANKS ==========
        ws_banks = wb.active
        ws_banks.title = "Banks"
        ws_banks.append(["bank_name", "bank_type"])
        ws_banks.cell(row=1, column=1).font = header_font
        ws_banks.cell(row=1, column=1).fill = header_fill
        ws_banks.cell(row=1, column=2).font = header_font
        ws_banks.cell(row=1, column=2).fill = header_fill
        
        for bank in self.manager.banks:
            ws_banks.append([bank.name, bank.bank_type])

        # ========== BANK ACCOUNTS ==========
        ws_accounts = wb.create_sheet("Bank_Accounts")
        ws_accounts.append(["bank_name", "account_name", "account_type", "balance", "interest_rate"])
        for col in range(1, 6):
            ws_accounts.cell(row=1, column=col).font = header_font
            ws_accounts.cell(row=1, column=col).fill = header_fill
        
        for bank in self.manager.banks:
            for name, account in bank.accounts.items():
                ws_accounts.append([
                    bank.name,
                    name,
                    account.account_type.value,
                    account.balance,
                    account.interest_rate
                ])

        # ========== CREDIT ACCOUNTS ==========
        ws_credit = wb.create_sheet("Credit_Accounts")
        ws_credit.append(["bank_name", "account_name", "credit_limit", "balance",
                         "interest_rate", "payment_due_date", "statement_date"])
        for col in range(1, 8):
            ws_credit.cell(row=1, column=col).font = header_font
            ws_credit.cell(row=1, column=col).fill = header_fill
        
        for bank in self.manager.banks:
            for name, credit in bank.credit_accounts.items():
                ws_credit.append([
                    bank.name,
                    name,
                    credit.credit_limit,
                    credit.balance,
                    credit.interest_rate,
                    credit.payment_due_date,
                    credit.statement_date
                ])

        # ========== MORTGAGES ==========
        ws_mortgage = wb.create_sheet("Mortgages")
        ws_mortgage.append(["bank_name", "account_name", "original_principal", "current_principal",
                           "interest_rate", "loan_term_months", "payment_due_date",
                           "property_tax_monthly", "insurance_monthly", "pmi_monthly", "hoa_monthly"])
        for col in range(1, 12):
            ws_mortgage.cell(row=1, column=col).font = header_font
            ws_mortgage.cell(row=1, column=col).fill = header_fill
        
        for bank in self.manager.banks:
            for name, mortgage in bank.mortgage_accounts.items():
                ws_mortgage.append([
                    bank.name,
                    name,
                    mortgage.original_principal,
                    mortgage.current_principal,
                    mortgage.interest_rate,
                    mortgage.loan_term_months,
                    mortgage.payment_due_date,
                    mortgage.escrow.property_tax_monthly,
                    mortgage.escrow.homeowners_insurance_monthly,
                    mortgage.escrow.pmi_monthly,
                    mortgage.escrow.hoa_monthly
                ])

        # ========== BILLS ==========
        ws_bills = wb.create_sheet("Bills")
        ws_bills.append(["bill_name", "amount", "due_date", "due_month", "frequency",
                        "is_floating", "min_amount", "max_amount"])
        for col in range(1, 9):
            ws_bills.cell(row=1, column=col).font = header_font
            ws_bills.cell(row=1, column=col).fill = header_fill
        
        for bill in self.manager.bills:
            is_floating = hasattr(bill, 'min_amount')
            ws_bills.append([
                bill.bill_name,
                bill.amount,
                bill.due_date,
                bill.due_month,
                bill.frequency.value,
                is_floating,
                getattr(bill, 'min_amount', None),
                getattr(bill, 'max_amount', None)
            ])

        # ========== INCOME ==========
        ws_income = wb.create_sheet("Income")
        ws_income.append(["source_name", "amount", "frequency", "pay_date_1", "pay_date_2"])
        for col in range(1, 6):
            ws_income.cell(row=1, column=col).font = header_font
            ws_income.cell(row=1, column=col).fill = header_fill
        
        for income in self.manager.income_sources:
            pay_dates = income.pay_date or []
            ws_income.append([
                income.source_name,
                income.amount,
                income.frequency.value,
                pay_dates[0] if len(pay_dates) > 0 else None,
                pay_dates[1] if len(pay_dates) > 1 else None
            ])

        # ========== PROMO OFFERS ==========
        ws_promos = wb.create_sheet("Promo_Offers")
        ws_promos.append(["credit_account_name", "promo_name", "months_interest_free",
                         "purchase_limit", "current_balance", "end_date"])
        for col in range(1, 7):
            ws_promos.cell(row=1, column=col).font = header_font
            ws_promos.cell(row=1, column=col).fill = header_fill
        
        for bank in self.manager.banks:
            for credit in bank.get_all_credit_accounts():
                for promo in credit.active_promos:
                    balance = credit.promo_balance.get(promo.promo_name, 0)
                    ws_promos.append([
                        credit.account_name,
                        promo.promo_name,
                        promo.months_interest_free,
                        promo.purchase_limit,
                        balance,
                        promo.end_date.isoformat()
                    ])

        wb.save(filepath)
        return filepath
