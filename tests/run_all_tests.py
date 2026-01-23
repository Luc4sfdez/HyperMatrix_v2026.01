#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperMatrix - Unified Test Runner
=================================
Executes ALL test suites and provides a combined report.

Usage:
    python tests/run_all_tests.py [--url http://localhost:26020] [--skip-e2e] [--skip-pytest]

Test Suites:
    1. Smoke Tests (API) - Python HTTP tests against running server
    2. E2E Tests (Playwright) - Browser-based UI tests
    3. Pytest Unit Tests - Local unit tests (parsers, integration)
"""

import sys
import os
import subprocess
import argparse
import time
from pathlib import Path

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'


def run_command(cmd: list, cwd: str = None, timeout: int = 300) -> tuple:
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def count_results(output: str, suite_type: str) -> tuple:
    """Parse test output to count passed/failed."""
    passed = 0
    failed = 0

    if suite_type == "smoke":
        passed = output.count("[OK]")
        failed = output.count("[FAIL]")
    elif suite_type == "e2e":
        # Look for "Passed: X" and "Failed: Y" in output
        for line in output.split('\n'):
            if "Passed:" in line:
                try:
                    passed = int(line.split("Passed:")[1].strip().split()[0])
                except:
                    pass
            if "Failed:" in line:
                try:
                    failed = int(line.split("Failed:")[1].strip().split()[0])
                except:
                    pass
    elif suite_type == "pytest":
        # Look for "X passed" and "Y failed" in summary line
        import re
        for line in output.split('\n'):
            # Match patterns like "134 passed", "2 failed", etc.
            passed_match = re.search(r'(\d+) passed', line)
            failed_match = re.search(r'(\d+) failed', line)
            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))

    return passed, failed


def print_header():
    """Print test runner header."""
    print(f"\n{BOLD}{'='*60}")
    print(f"  HYPERMATRIX - UNIFIED TEST RUNNER")
    print(f"{'='*60}{RESET}\n")


def print_section(name: str):
    """Print section header."""
    print(f"\n{CYAN}{BOLD}[{name}]{RESET}")
    print(f"{'-'*40}")


def print_result(name: str, passed: int, failed: int, skipped: bool = False):
    """Print test result."""
    if skipped:
        print(f"  {YELLOW}[SKIP]{RESET} {name}")
        return

    total = passed + failed
    if failed == 0:
        print(f"  {GREEN}[PASS]{RESET} {name}: {passed}/{total}")
    else:
        print(f"  {RED}[FAIL]{RESET} {name}: {passed}/{total} ({failed} failed)")


def main():
    parser = argparse.ArgumentParser(description="HyperMatrix Unified Test Runner")
    parser.add_argument("--url", default="http://localhost:26020",
                       help="Base URL for API/E2E tests")
    parser.add_argument("--skip-e2e", action="store_true",
                       help="Skip E2E browser tests")
    parser.add_argument("--skip-pytest", action="store_true",
                       help="Skip pytest unit tests")
    parser.add_argument("--skip-smoke", action="store_true",
                       help="Skip smoke API tests")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed output")
    args = parser.parse_args()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print_header()
    print(f"  URL: {args.url}")
    print(f"  Project: {project_root}")

    results = []
    total_passed = 0
    total_failed = 0
    start_time = time.time()

    # ================================================
    # 1. SMOKE TESTS (API)
    # ================================================
    print_section("SMOKE TESTS (API)")

    if args.skip_smoke:
        print_result("Smoke Tests", 0, 0, skipped=True)
    else:
        smoke_script = script_dir / "smoke_test.py"
        if smoke_script.exists():
            cmd = [sys.executable, str(smoke_script), "--url", args.url]
            success, output = run_command(cmd, cwd=str(project_root))
            passed, failed = count_results(output, "smoke")

            if args.verbose:
                print(output)

            print_result("Smoke Tests", passed, failed)
            results.append(("Smoke Tests", passed, failed))
            total_passed += passed
            total_failed += failed
        else:
            print(f"  {YELLOW}[WARN]{RESET} smoke_test.py not found")

    # ================================================
    # 2. E2E TESTS (Playwright)
    # ================================================
    print_section("E2E TESTS (Playwright)")

    if args.skip_e2e:
        print_result("E2E Tests", 0, 0, skipped=True)
    else:
        e2e_script = script_dir / "e2e_test.js"
        if e2e_script.exists():
            # Check if node is available
            node_check, _ = run_command(["node", "--version"])
            if not node_check:
                print(f"  {YELLOW}[WARN]{RESET} Node.js not available, skipping E2E")
            else:
                env = os.environ.copy()
                env["HYPERMATRIX_URL"] = args.url
                try:
                    result = subprocess.run(
                        ["node", str(e2e_script)],
                        capture_output=True,
                        text=True,
                        cwd=str(project_root),
                        timeout=120,
                        env=env
                    )
                    output = result.stdout + result.stderr
                    passed, failed = count_results(output, "e2e")

                    if args.verbose:
                        print(output)

                    print_result("E2E Tests", passed, failed)
                    results.append(("E2E Tests", passed, failed))
                    total_passed += passed
                    total_failed += failed
                except subprocess.TimeoutExpired:
                    print(f"  {RED}[FAIL]{RESET} E2E Tests: TIMEOUT")
                    results.append(("E2E Tests", 0, 1))
                    total_failed += 1
                except Exception as e:
                    print(f"  {RED}[FAIL]{RESET} E2E Tests: {e}")
                    results.append(("E2E Tests", 0, 1))
                    total_failed += 1
        else:
            print(f"  {YELLOW}[WARN]{RESET} e2e_test.js not found")

    # ================================================
    # 3. ADVANCED TESTS (Security, Edge Cases)
    # ================================================
    print_section("ADVANCED TESTS")

    if args.skip_pytest:  # Reuse flag for now
        print_result("Advanced Tests", 0, 0, skipped=True)
    else:
        advanced_script = script_dir / "advanced_test.py"
        if advanced_script.exists():
            cmd = [sys.executable, str(advanced_script), "--url", args.url]
            success, output = run_command(cmd, cwd=str(project_root), timeout=60)

            # Parse results from output
            passed = output.count("[PASS]")
            failed = output.count("[FAIL]")

            if args.verbose:
                print(output)

            print_result("Advanced Tests", passed, failed)
            results.append(("Advanced", passed, failed))
            total_passed += passed
            total_failed += failed
        else:
            print(f"  {YELLOW}[WARN]{RESET} advanced_test.py not found")

    # ================================================
    # 4. PYTEST UNIT TESTS
    # ================================================
    print_section("PYTEST UNIT TESTS")

    if args.skip_pytest:
        print_result("Pytest", 0, 0, skipped=True)
    else:
        cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=no", "-q"]
        success, output = run_command(cmd, cwd=str(project_root), timeout=180)
        passed, failed = count_results(output, "pytest")

        if args.verbose:
            print(output)

        print_result("Pytest Unit Tests", passed, failed)
        results.append(("Pytest", passed, failed))
        total_passed += passed
        total_failed += failed

    # ================================================
    # SUMMARY
    # ================================================
    elapsed = time.time() - start_time

    print(f"\n{BOLD}{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}{RESET}\n")

    for name, passed, failed in results:
        total = passed + failed
        status = f"{GREEN}PASS{RESET}" if failed == 0 else f"{RED}FAIL{RESET}"
        print(f"  {name:25} {passed:4}/{total:<4} [{status}]")

    print(f"\n  {'-'*40}")
    grand_total = total_passed + total_failed
    print(f"  {'TOTAL':25} {total_passed:4}/{grand_total:<4}", end="")

    if total_failed == 0:
        print(f" [{GREEN}{BOLD}ALL PASS{RESET}]")
    else:
        print(f" [{RED}{BOLD}{total_failed} FAILED{RESET}]")

    print(f"\n  Time: {elapsed:.1f}s")
    print(f"{'='*60}\n")

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
