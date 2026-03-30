#!/usr/bin/env python3
"""
Test runner script for the personal finance management system.
Run comprehensive tests for all components.
"""

import subprocess
import sys
import os


def run_tests():
    """Run the complete test suite."""
    print("=" * 80)
    print("PERSONAL FINANCE MANAGEMENT SYSTEM - TEST SUITE")
    print("=" * 80)

    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Test categories
    test_categories = [
        ("Unit Tests", ["-m", "unit"]),
        ("Integration Tests", ["-m", "integration"]),
        ("All Tests", [])
    ]

    results = {}

    for category_name, markers in test_categories:
        print(f"\n{'='*60}")
        print(f"RUNNING {category_name.upper()}")
        print(f"{'='*60}")

        # Build pytest command
        cmd = [sys.executable, "-m", "pytest"]
        if markers:
            cmd.extend(markers)
        cmd.extend([
            "--tb=short",
            "--verbose",
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                print("✅ PASSED")
                results[category_name] = "PASSED"
            else:
                print("❌ FAILED")
                results[category_name] = "FAILED"

            # Print output
            if result.stdout:
                print("\nSTDOUT:")
                print(result.stdout)

            if result.stderr:
                print("\nSTDERR:")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print("⏰ TIMEOUT - Tests took too long")
            results[category_name] = "TIMEOUT"
        except Exception as e:
            print(f"💥 ERROR: {e}")
            results[category_name] = "ERROR"

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    all_passed = True
    for category, status in results.items():
        status_icon = "✅" if status == "PASSED" else "❌"
        print(f"{status_icon} {category}: {status}")
        if status != "PASSED":
            all_passed = False

    print(f"\n{'='*80}")
    if all_passed:
        print("🎉 ALL TESTS PASSED! The system is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED. Please review the output above.")
    print(f"{'='*80}")

    return 0 if all_passed else 1


def run_specific_test(test_file):
    """Run a specific test file."""
    print(f"Running specific test: {test_file}")

    cmd = [sys.executable, "-m", "pytest", f"tests/{test_file}", "--verbose", "--tb=short"]

    result = subprocess.run(cmd)
    return result.returncode


def show_help():
    """Show help information."""
    print("Personal Finance Management System - Test Runner")
    print()
    print("Usage:")
    print("  python run_tests.py                    # Run all tests")
    print("  python run_tests.py <test_file>        # Run specific test file")
    print("  python run_tests.py --help            # Show this help")
    print()
    print("Available test files:")
    test_files = [
        "test_bank.py",
        "test_bills.py",
        "test_income.py",
        "test_timeline.py",
        "test_optimizer.py",
        "test_data_import_export.py",
        "test_finance_manager.py",
        "test_mortgage.py",
        "test_credit.py",
        "test_promos.py"
    ]

    for test_file in test_files:
        print(f"  - {test_file}")
    print()
    print("Test categories:")
    print("  -m unit        # Unit tests only")
    print("  -m integration # Integration tests only")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h", "help"]:
            show_help()
        else:
            # Run specific test file
            test_file = sys.argv[1]
            if not test_file.endswith(".py"):
                test_file += ".py"
            sys.exit(run_specific_test(test_file))
    else:
        # Run all tests
        sys.exit(run_tests())

