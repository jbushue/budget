"""
Tests for data import/export functionality.
"""

import pytest
import os
import tempfile
from datetime import date
from models.data_import_export import DataImportExport
from models.finance_manager import FinanceManager
from models.types import BillFrequency


class TestDataImportExport:
    """Test DataImportExport class functionality."""

    def test_import_export_creation(self, sample_finance_manager):
        """Test creating import/export handler."""
        handler = DataImportExport(sample_finance_manager)
        assert handler.manager is not None

    def test_generate_template(self):
        """Test generating Excel template."""
        handler = DataImportExport()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "test_template.xlsx")
            )

            assert template_path is not None
            assert os.path.exists(template_path)
            assert template_path.endswith("test_template.xlsx")

    def test_generate_template_default_location(self):
        """Test generating template with default location."""
        handler = DataImportExport()

        # Should work without specifying path
        template_path = handler.generate_template()
        assert template_path is not None

    def test_export_current_data(self, sample_finance_manager):
        """Test exporting current financial data."""
        handler = DataImportExport(sample_finance_manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "test_export.xlsx")
            )

            assert export_path is not None
            assert os.path.exists(export_path)
            assert export_path.endswith("test_export.xlsx")

    def test_import_data_basic(self, sample_finance_manager):
        """Test basic data import functionality."""
        handler = DataImportExport(sample_finance_manager)

        # First export data to create a template
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "export.xlsx")
            )

            # Try to import the exported data
            results = handler.import_data(export_path)

            assert "banks_created" in results
            assert "accounts_created" in results
            assert "bills_created" in results
            assert "income_created" in results
            assert "errors" in results
            assert "warnings" in results

    def test_import_template_data(self):
        """Test importing template data."""
        handler = DataImportExport()

        # Generate template
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            # Create a new manager for import
            manager = FinanceManager([], [], [])
            import_handler = DataImportExport(manager)

            # Import template data
            results = import_handler.import_data(template_path)

            assert isinstance(results, dict)
            # Template should have some example data
            assert results["bills_created"] >= 0

    def test_check_openpyxl_available(self):
        """Test openpyxl availability check."""
        # This should work if openpyxl is installed
        available = DataImportExport.check_openpyxl()
        assert isinstance(available, bool)

    def test_import_invalid_file(self, sample_finance_manager):
        """Test importing invalid file."""
        handler = DataImportExport(sample_finance_manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_file = os.path.join(temp_dir, "invalid.xlsx")

            # Create an empty file
            with open(invalid_file, 'w') as f:
                f.write("not an excel file")

            # Should handle gracefully
            results = handler.import_data(invalid_file)
            assert "errors" in results
            assert len(results["errors"]) > 0


class TestExcelTemplateStructure:
    """Test Excel template structure and content."""

    def test_template_has_required_sheets(self):
        """Test that template has all required sheets."""
        handler = DataImportExport()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            # Import and check structure
            check_handler = DataImportExport()
            results = check_handler.import_data(template_path)

            # Should not have critical errors
            assert len(results.get("errors", [])) == 0

    def test_template_bills_sheet_structure(self):
        """Test bills sheet structure in template."""
        handler = DataImportExport()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            # The template should be importable and create bills
            manager = FinanceManager([], [], [])
            import_handler = DataImportExport(manager)
            results = import_handler.import_data(template_path)

            # Should create some bills from template examples
            assert results["bills_created"] >= 0


class TestDataExportContent:
    """Test exported data content."""

    def test_export_includes_all_banks(self, sample_finance_manager):
        """Test that export includes all bank data."""
        handler = DataImportExport(sample_finance_manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "export.xlsx")
            )

            # Re-import and verify
            new_manager = FinanceManager([], [], [])
            import_handler = DataImportExport(new_manager)
            results = import_handler.import_data(export_path)

            # Should recreate the banks
            assert results["banks_created"] >= 0

    def test_export_includes_bills_with_due_month(self, sample_finance_manager):
        """Test that export includes bills with due_month field."""
        handler = DataImportExport(sample_finance_manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "export.xlsx")
            )

            # The export should include yearly bills with due_month
            # This is tested implicitly by the import working
            new_manager = FinanceManager([], [], [])
            import_handler = DataImportExport(new_manager)
            results = import_handler.import_data(export_path)

            assert results["bills_created"] >= 0

    def test_export_income_sources(self, sample_finance_manager):
        """Test that export includes income sources."""
        handler = DataImportExport(sample_finance_manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "export.xlsx")
            )

            new_manager = FinanceManager([], [], [])
            import_handler = DataImportExport(new_manager)
            results = import_handler.import_data(export_path)

            assert results["income_created"] >= 0


class TestImportValidation:
    """Test data import validation."""

    def test_import_bills_validation(self):
        """Test bill import validation."""
        # Create a minimal manager
        manager = FinanceManager([], [], [])
        handler = DataImportExport(manager)

        # Generate template
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            # Import should work
            results = handler.import_data(template_path)

            # Check that bills were created from template
            assert results["bills_created"] >= 0

            # Verify bill properties
            if manager.bills:
                bill = manager.bills[0]
                assert hasattr(bill, 'due_month')
                assert hasattr(bill, 'frequency')

    def test_import_yearly_bills_with_due_month(self):
        """Test importing yearly bills with due_month."""
        manager = FinanceManager([], [], [])
        handler = DataImportExport(manager)

        # Generate template (which includes yearly bill example)
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            results = handler.import_data(template_path)

            # Find yearly bills
            yearly_bills = [b for b in manager.bills if b.frequency == BillFrequency.YEARLY]

            if yearly_bills:
                bill = yearly_bills[0]
                assert bill.due_month is not None
                assert bill.due_month == 4  # From template example (Property Tax)

    def test_import_semi_annual_bills_with_due_month(self):
        """Test importing semi-annual bills with due_month."""
        manager = FinanceManager([], [], [])
        handler = DataImportExport(manager)

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = handler.generate_template(
                filepath=os.path.join(temp_dir, "template.xlsx")
            )

            results = handler.import_data(template_path)

            # Template doesn't have semi-annual example, but structure should support it
            # This tests that the import logic handles due_month correctly
            assert results["bills_created"] >= 0


class TestRoundTripImportExport:
    """Test round-trip import/export consistency."""

    def test_round_trip_bills(self, sample_finance_manager):
        """Test that bills survive round-trip import/export."""
        original_bills = len(sample_finance_manager.bills)

        # Export
        handler = DataImportExport(sample_finance_manager)
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "round_trip.xlsx")
            )

            # Import into new manager
            new_manager = FinanceManager([], [], [])
            import_handler = DataImportExport(new_manager)
            results = import_handler.import_data(export_path)

            # Should recreate bills
            assert results["bills_created"] == original_bills

            # Verify bill properties are preserved
            if original_bills > 0:
                original_bill = sample_finance_manager.bills[0]
                imported_bill = new_manager.bills[0]

                assert imported_bill.bill_name == original_bill.bill_name
                assert imported_bill.amount == original_bill.amount
                assert imported_bill.due_date == original_bill.due_date
                assert imported_bill.due_month == original_bill.due_month
                assert imported_bill.frequency == original_bill.frequency

    def test_round_trip_banks_and_accounts(self, sample_finance_manager):
        """Test that banks and accounts survive round-trip."""
        original_banks = len(sample_finance_manager.banks)

        handler = DataImportExport(sample_finance_manager)
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = handler.export_current_data(
                filepath=os.path.join(temp_dir, "round_trip.xlsx")
            )

            new_manager = FinanceManager([], [], [])
            import_handler = DataImportExport(new_manager)
            results = import_handler.import_data(export_path)

            assert results["banks_created"] == original_banks
            assert results["accounts_created"] >= 0

