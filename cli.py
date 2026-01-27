#!/usr/bin/env python3
"""
Interactive CLI interface for the Personal Finance Management System.
Run this to get an interactive menu with all features.
"""

from models.finance_manager import FinanceManager
from models.cli_menu import FinanceCLI


def main():
    """Main entry point for the CLI."""
    print("\n" + "=" * 80)
    print("🏦 PERSONAL FINANCE MANAGEMENT SYSTEM")
    print("=" * 80)

    # Initialize database
    print("\n⏳ Initializing database...")
    manager = FinanceManager([], [], [])
    manager.initialize_database()
    print("✓ Database initialized")

    # Try to load from database
    print("\n⏳ Attempting to load data from database...")
    if manager.load_from_database():
        print("✓ Data loaded from database")
        print(f"  - {len(manager.banks)} banks")
        print(f"  - {sum(len(b.accounts) + len(b.credit_accounts) for b in manager.banks)} accounts")
        print(f"  - {len(manager.bills)} bills")
        print(f"  - {len(manager.income_sources)} income sources")
    else:
        print("ℹ️  No data found in database.")
        print("    You can create banks, accounts, bills, and income from the menu.")
        print("    Or load from a previous save file using option 12.\n")

    print("\n" + "=" * 80)
    print("Starting interactive menu...\n")

    # Run CLI
    cli = FinanceCLI(manager)
    cli.run()


if __name__ == "__main__":
    main()

