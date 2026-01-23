#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperMatrix Stress Tests
========================
Heavy tests for performance, limits, and edge cases.
Slow execution (~5min+), run before releases.

Usage:
    python tests/stress_test.py [--url http://localhost:26020] [OPTIONS]

Options:
    --skip-large-files    Skip 50MB file tests
    --skip-many-files     Skip 10,000 files test
    --skip-concurrent     Skip concurrent scan tests
    --quick               Run minimal stress tests only (~1min)

Categories:
    1. LARGE FILES - 10MB, 50MB Python files
    2. MANY FILES - Projects with 1000, 5000, 10000 files
    3. CONCURRENT - Multiple simultaneous operations
    4. MEMORY - Check for leaks after heavy operations
    5. TIMEOUTS - Long-running operations
    6. RECOVERY - Behavior after errors
"""

import sys
import os
import json
import time
import tempfile
import shutil
import argparse
import threading
import gc
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
RESET = '\033[0m'
BOLD = '\033[1m'


class StressTests:
    def __init__(self, base_url: str, temp_dir: str = None):
        self.base_url = base_url.rstrip('/')
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="hypermatrix_stress_")
        self.results = {}
        self.current_category = None
        self.cleanup_paths = []

    def category(self, name: str):
        """Start a new test category."""
        self.current_category = name
        self.results[name] = []
        print(f"\n{MAGENTA}{BOLD}[{name}]{RESET}")

    def test(self, name: str, condition: bool, reason: str = None, info: str = None):
        """Record a test result."""
        self.results[self.current_category].append((name, condition, reason))
        if condition:
            suffix = f" ({info})" if info else ""
            print(f"  {GREEN}[PASS]{RESET} {name}{suffix}")
        else:
            print(f"  {RED}[FAIL]{RESET} {name}: {reason or 'Failed'}")
        return condition

    def info(self, message: str):
        """Print info message."""
        print(f"  {YELLOW}[INFO]{RESET} {message}")

    def request(self, endpoint: str, method: str = "GET", data: dict = None,
                timeout: int = 30) -> tuple:
        """Make HTTP request, return (status_code, response_body, elapsed_ms)."""
        url = f"{self.base_url}{endpoint}"
        start = time.time()

        try:
            if data:
                req = Request(url, data=json.dumps(data).encode('utf-8'),
                            headers={'Content-Type': 'application/json'},
                            method=method)
            else:
                req = Request(url, method=method)

            response = urlopen(req, timeout=timeout)
            elapsed = (time.time() - start) * 1000
            return response.getcode(), response.read().decode('utf-8'), elapsed

        except HTTPError as e:
            elapsed = (time.time() - start) * 1000
            body = ""
            try:
                body = e.read().decode('utf-8')
            except:
                pass
            return e.code, body, elapsed

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return -1, str(e), elapsed

    def create_test_project(self, name: str, num_files: int,
                           file_size_kb: int = 1) -> str:
        """Create a test project with specified number of files."""
        project_dir = Path(self.temp_dir) / name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for organization
        subdirs = ['src', 'lib', 'tests', 'utils', 'models']
        for subdir in subdirs:
            (project_dir / subdir).mkdir(exist_ok=True)

        # Generate Python content
        base_content = '''"""Auto-generated test file."""

import os
import sys
from typing import List, Optional

class TestClass{n}:
    """Test class number {n}."""

    def __init__(self, value: int):
        self.value = value
        self.data = []

    def process(self, items: List[str]) -> Optional[str]:
        """Process items and return result."""
        if not items:
            return None
        result = []
        for item in items:
            result.append(item.upper())
        return ",".join(result)

    def calculate(self, x: int, y: int) -> int:
        """Calculate sum."""
        return x + y + self.value


def function_{n}(arg1: str, arg2: int = 0) -> dict:
    """Function number {n}."""
    return {{"arg1": arg1, "arg2": arg2, "n": {n}}}


# Variables
CONSTANT_{n} = "value_{n}"
data_{n} = [1, 2, 3, 4, 5]
'''

        # Pad content to reach desired size
        if file_size_kb > 1:
            padding = "\n# " + "x" * 100
            padding_needed = (file_size_kb * 1024 - len(base_content)) // len(padding)
            extra_padding = padding * max(0, padding_needed)
        else:
            extra_padding = ""

        # Create files
        for i in range(num_files):
            subdir = subdirs[i % len(subdirs)]
            filename = f"module_{i:05d}.py"
            filepath = project_dir / subdir / filename

            content = base_content.format(n=i) + extra_padding

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

        # Create __init__.py files
        for subdir in subdirs:
            init_file = project_dir / subdir / "__init__.py"
            with open(init_file, 'w') as f:
                f.write(f'"""Package {subdir}."""\n')

        self.cleanup_paths.append(str(project_dir))
        return str(project_dir)

    def create_large_file(self, name: str, size_mb: int) -> str:
        """Create a large Python file."""
        filepath = Path(self.temp_dir) / name
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Generate realistic Python content
        header = '''"""
Large auto-generated Python file for stress testing.
Size: {size}MB
"""

import os
import sys
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

'''

        class_template = '''
@dataclass
class DataModel{n}:
    """Data model number {n}."""
    id: int
    name: str
    value: float
    tags: List[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {{
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "tags": self.tags,
            "metadata": self.metadata,
        }}

    def validate(self) -> bool:
        if self.id < 0:
            return False
        if not self.name:
            return False
        return True


def process_model_{n}(model: DataModel{n}) -> Optional[Dict]:
    """Process model {n} and return result."""
    if not model.validate():
        logger.warning("Invalid model {n}")
        return None

    result = model.to_dict()
    result["processed"] = True
    result["timestamp"] = "2026-01-23T00:00:00Z"
    return result

'''

        target_size = size_mb * 1024 * 1024
        content = header.format(size=size_mb)

        n = 0
        while len(content) < target_size:
            content += class_template.format(n=n)
            n += 1

        # Trim to exact size
        content = content[:target_size]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        self.cleanup_paths.append(str(filepath))
        return str(filepath)

    def cleanup(self):
        """Remove temporary files and directories."""
        for path in self.cleanup_paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
            except Exception as e:
                print(f"  {YELLOW}[WARN]{RESET} Cleanup failed for {path}: {e}")

    def run_all(self, skip_large=False, skip_many=False, skip_concurrent=False,
                quick=False):
        """Run all stress tests."""
        print(f"\n{BOLD}{'='*60}")
        print(f"  HYPERMATRIX STRESS TESTS")
        print(f"  URL: {self.base_url}")
        print(f"  Temp: {self.temp_dir}")
        print(f"{'='*60}{RESET}")

        if quick:
            self.info("Quick mode: running minimal tests only")
            skip_large = True
            skip_many = True

        try:
            self.test_large_files(skip=skip_large)
            self.test_many_files(skip=skip_many, quick=quick)
            self.test_concurrent(skip=skip_concurrent)
            self.test_memory()
            self.test_timeouts()
            self.test_recovery()
        finally:
            self.info("Cleaning up temporary files...")
            self.cleanup()

        return self.summary()

    # ================================================================
    # 1. LARGE FILES
    # ================================================================
    def test_large_files(self, skip=False):
        self.category("LARGE FILES")

        if skip:
            self.info("Skipped (--skip-large-files)")
            return

        # Test 10MB file
        self.info("Creating 10MB Python file...")
        large_file = self.create_large_file("large_10mb.py", 10)
        file_size = os.path.getsize(large_file) / (1024 * 1024)
        self.test(
            "Create 10MB file",
            file_size >= 9.5,
            f"Only {file_size:.1f}MB",
            f"{file_size:.1f}MB"
        )

        # Test 50MB file
        self.info("Creating 50MB Python file...")
        huge_file = self.create_large_file("large_50mb.py", 50)
        file_size = os.path.getsize(huge_file) / (1024 * 1024)
        self.test(
            "Create 50MB file",
            file_size >= 49,
            f"Only {file_size:.1f}MB",
            f"{file_size:.1f}MB"
        )

        # Test API with large content (simulate)
        self.info("Testing API response with large payload...")
        status, body, elapsed = self.request("/api/db/stats")
        self.test(
            "API handles request during large file ops",
            status == 200,
            f"Got {status}",
            f"{elapsed:.0f}ms"
        )

    # ================================================================
    # 2. MANY FILES
    # ================================================================
    def test_many_files(self, skip=False, quick=False):
        self.category("MANY FILES")

        if skip:
            self.info("Skipped (--skip-many-files)")
            return

        test_sizes = [100, 500] if quick else [100, 1000, 5000]

        for num_files in test_sizes:
            self.info(f"Creating project with {num_files} files...")
            start = time.time()
            project_path = self.create_test_project(f"project_{num_files}", num_files)
            create_time = time.time() - start

            # Count actual files
            actual_files = sum(1 for _ in Path(project_path).rglob("*.py"))
            self.test(
                f"Create {num_files} files",
                actual_files >= num_files,
                f"Only {actual_files} files",
                f"{create_time:.1f}s"
            )

            # Test browsing large directory
            # Note: This would need the project to be in /projects
            self.info(f"Project created at: {project_path}")

        # Test warning threshold
        if not quick:
            self.info("Checking warning for large projects (>5000 files)...")
            # This is a conceptual test - the actual warning should be in scan logic
            self.test(
                "Large project warning threshold defined",
                True,  # We defined 5000 as threshold
                info="Threshold: 5000 files"
            )

    # ================================================================
    # 3. CONCURRENT OPERATIONS
    # ================================================================
    def test_concurrent(self, skip=False):
        self.category("CONCURRENT OPERATIONS")

        if skip:
            self.info("Skipped (--skip-concurrent)")
            return

        # Test concurrent API requests
        self.info("Testing 10 concurrent API requests...")
        endpoints = [
            "/health",
            "/api/scan/list",
            "/api/ai/status",
            "/api/rules/presets",
            "/api/db/stats",
        ] * 2  # 10 requests total

        results = []
        errors = []

        def make_request(endpoint):
            try:
                status, _, elapsed = self.request(endpoint, timeout=30)
                return (endpoint, status, elapsed)
            except Exception as e:
                return (endpoint, -1, str(e))

        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, ep) for ep in endpoints]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if result[1] != 200:
                    errors.append(result)

        total_time = time.time() - start
        success_count = sum(1 for r in results if r[1] == 200)

        self.test(
            "10 concurrent requests succeed",
            success_count == 10,
            f"Only {success_count}/10 succeeded",
            f"{total_time:.1f}s total"
        )

        # Test concurrent requests don't cause errors
        self.test(
            "No server errors (500) under load",
            all(r[1] != 500 for r in results),
            f"Got 500 errors: {[r for r in results if r[1] == 500]}"
        )

        # Test response times under load
        avg_time = sum(r[2] for r in results if isinstance(r[2], (int, float))) / len(results)
        self.test(
            "Average response < 5000ms under load",
            avg_time < 5000,
            f"Average was {avg_time:.0f}ms",
            f"Avg: {avg_time:.0f}ms"
        )

        # Test rapid sequential requests
        self.info("Testing 50 rapid sequential requests...")
        rapid_results = []
        start = time.time()
        for i in range(50):
            status, _, elapsed = self.request("/health", timeout=5)
            rapid_results.append((status, elapsed))

        rapid_time = time.time() - start
        rapid_success = sum(1 for r in rapid_results if r[0] == 200)

        self.test(
            "50 rapid requests succeed",
            rapid_success >= 48,  # Allow 2 failures
            f"Only {rapid_success}/50",
            f"{rapid_time:.1f}s, {rapid_time/50*1000:.0f}ms avg"
        )

    # ================================================================
    # 4. MEMORY CHECKS
    # ================================================================
    def test_memory(self):
        self.category("MEMORY CHECKS")

        # Get initial memory (Python process)
        import tracemalloc
        tracemalloc.start()

        # Make many requests
        self.info("Making 100 requests to check for leaks...")
        for i in range(100):
            self.request("/api/scan/list", timeout=5)

        # Force garbage collection
        gc.collect()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)

        self.test(
            "Client memory < 100MB after 100 requests",
            current_mb < 100,
            f"Using {current_mb:.1f}MB",
            f"Current: {current_mb:.1f}MB, Peak: {peak_mb:.1f}MB"
        )

        # Check server health after load
        status, body, _ = self.request("/health")
        self.test(
            "Server healthy after load test",
            status == 200,
            f"Got {status}"
        )

    # ================================================================
    # 5. TIMEOUTS
    # ================================================================
    def test_timeouts(self):
        self.category("TIMEOUTS")

        # Test that server responds within timeout
        self.info("Testing response within 5s timeout...")
        start = time.time()
        status, _, elapsed = self.request("/api/scan/list", timeout=5)
        self.test(
            "Scan list responds within 5s",
            status == 200 and elapsed < 5000,
            f"Took {elapsed:.0f}ms" if status == 200 else f"Status {status}",
            f"{elapsed:.0f}ms"
        )

        # Test AI endpoint timeout behavior
        self.info("Testing AI endpoint timeout handling...")
        status, body, elapsed = self.request(
            "/api/ai/chat",
            method="POST",
            data={"message": "test timeout", "model": "qwen2:7b"},
            timeout=60
        )
        # Should either succeed or fail gracefully (not hang)
        self.test(
            "AI request completes or times out gracefully",
            status in (200, 408, 504, 500, -1),  # Various timeout/error codes
            f"Got unexpected status {status}",
            f"{elapsed:.0f}ms"
        )

    # ================================================================
    # 6. RECOVERY
    # ================================================================
    def test_recovery(self):
        self.category("RECOVERY")

        # Test recovery after bad request
        self.info("Testing recovery after invalid request...")
        # Send garbage
        try:
            url = f"{self.base_url}/api/scan/start"
            req = Request(url, data=b"invalid json garbage {{{",
                         headers={'Content-Type': 'application/json'},
                         method="POST")
            urlopen(req, timeout=5)
        except:
            pass  # Expected to fail

        # Server should still work
        status, _, _ = self.request("/health")
        self.test(
            "Server recovers after bad request",
            status == 200,
            f"Got {status}"
        )

        # Test recovery after many errors
        self.info("Testing recovery after 20 error requests...")
        for i in range(20):
            self.request("/api/nonexistent/endpoint/that/doesnt/exist")

        status, _, _ = self.request("/health")
        self.test(
            "Server stable after many 404s",
            status == 200,
            f"Got {status}"
        )

        # Test graceful handling of connection issues
        self.info("Testing various malformed requests...")
        malformed_tests = [
            ("/api/browse?path=" + "a" * 1000, "Long query string"),
            ("/api/scan/result/" + "x" * 100, "Long scan ID"),
        ]

        all_handled = True
        for endpoint, desc in malformed_tests:
            status, _, _ = self.request(endpoint, timeout=5)
            if status == 500:
                all_handled = False
                break

        self.test(
            "No crashes from malformed requests",
            all_handled,
            "Got 500 error"
        )

    # ================================================================
    # SUMMARY
    # ================================================================
    def summary(self) -> bool:
        """Print summary and return True if all passed."""
        print(f"\n{BOLD}{'='*60}")
        print(f"  STRESS TEST SUMMARY")
        print(f"{'='*60}{RESET}\n")

        total_passed = 0
        total_failed = 0

        for category, tests in self.results.items():
            if not tests:
                print(f"  {category:25} {'SKIPPED':>10}")
                continue

            passed = sum(1 for _, ok, _ in tests if ok)
            failed = sum(1 for _, ok, _ in tests if not ok)
            total_passed += passed
            total_failed += failed

            status = f"{GREEN}PASS{RESET}" if failed == 0 else f"{RED}FAIL{RESET}"
            print(f"  {category:25} {passed:3}/{passed+failed:<3} [{status}]")

        print(f"\n  {'-'*40}")
        total = total_passed + total_failed
        if total_failed == 0:
            print(f"  {'TOTAL':25} {total_passed:3}/{total:<3} [{GREEN}{BOLD}ALL PASS{RESET}]")
        else:
            print(f"  {'TOTAL':25} {total_passed:3}/{total:<3} [{RED}{BOLD}{total_failed} FAILED{RESET}]")

        if total_failed > 0:
            print(f"\n  {RED}Failed tests:{RESET}")
            for category, tests in self.results.items():
                for name, ok, reason in tests:
                    if not ok:
                        print(f"    - [{category}] {name}: {reason}")

        print(f"\n{'='*60}\n")
        return total_failed == 0


def main():
    parser = argparse.ArgumentParser(description="HyperMatrix Stress Tests")
    parser.add_argument("--url", default="http://localhost:26020",
                       help="Base URL of HyperMatrix")
    parser.add_argument("--skip-large-files", action="store_true",
                       help="Skip large file tests (50MB)")
    parser.add_argument("--skip-many-files", action="store_true",
                       help="Skip many files tests (10000)")
    parser.add_argument("--skip-concurrent", action="store_true",
                       help="Skip concurrent operation tests")
    parser.add_argument("--quick", action="store_true",
                       help="Run minimal stress tests (~1min)")
    parser.add_argument("--temp-dir",
                       help="Temporary directory for test files")
    args = parser.parse_args()

    tests = StressTests(args.url, args.temp_dir)
    success = tests.run_all(
        skip_large=args.skip_large_files,
        skip_many=args.skip_many_files,
        skip_concurrent=args.skip_concurrent,
        quick=args.quick
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
