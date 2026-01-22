#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperMatrix Smoke Tests
=======================
Tests rápidos que verifican que TODAS las funcionalidades críticas funcionan.
Ejecutar ANTES de cada deploy/commit.

Uso:
    python tests/smoke_test.py [--url http://localhost:26020]
"""

import sys
import json
import argparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

# Colores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

class SmokeTest:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.failed = 0
        self.passed = 0

    def test(self, name: str, endpoint: str, method: str = "GET",
             data: dict = None, expect_keys: list = None,
             expect_status: int = 200, timeout: int = 30):
        """Ejecutar un test individual."""
        url = f"{self.base_url}{endpoint}"

        try:
            if data:
                req = Request(url, data=json.dumps(data).encode('utf-8'),
                            headers={'Content-Type': 'application/json'},
                            method=method)
            else:
                req = Request(url, method=method)

            response = urlopen(req, timeout=timeout)
            status = response.getcode()
            body = response.read().decode('utf-8')

            try:
                json_data = json.loads(body)
            except:
                json_data = None

            # Verificar status
            if status != expect_status:
                self._fail(name, f"Status {status}, esperado {expect_status}")
                return False

            # Verificar keys esperadas
            if expect_keys and json_data:
                missing = [k for k in expect_keys if k not in json_data]
                if missing:
                    self._fail(name, f"Faltan keys: {missing}")
                    return False

            self._pass(name)
            return True

        except HTTPError as e:
            if e.code == expect_status:
                self._pass(name)
                return True
            self._fail(name, f"HTTP {e.code}: {e.reason}")
            return False
        except URLError as e:
            self._fail(name, f"Connection error: {e.reason}")
            return False
        except Exception as e:
            self._fail(name, str(e))
            return False

    def _pass(self, name: str):
        self.passed += 1
        self.results.append((name, True, None))
        print(f"  {GREEN}[OK]{RESET} {name}")

    def _fail(self, name: str, reason: str):
        self.failed += 1
        self.results.append((name, False, reason))
        print(f"  {RED}[FAIL]{RESET} {name}: {reason}")

    def section(self, name: str):
        print(f"\n{BOLD}> {name}{RESET}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        if self.failed == 0:
            print(f"{GREEN}{BOLD}[OK] TODOS LOS TESTS PASARON ({self.passed}/{total}){RESET}")
        else:
            print(f"{RED}{BOLD}[FAIL] FALLOS: {self.failed}/{total}{RESET}")
            print(f"\nTests fallidos:")
            for name, ok, reason in self.results:
                if not ok:
                    print(f"  - {name}: {reason}")
        print()
        return self.failed == 0


def run_smoke_tests(base_url: str) -> bool:
    """Ejecutar todos los smoke tests."""

    print(f"\n{BOLD}{'='*50}")
    print(f"  HYPERMATRIX SMOKE TESTS")
    print(f"  URL: {base_url}")
    print(f"{'='*50}{RESET}")

    t = SmokeTest(base_url)

    # ========================================
    # CORE API
    # ========================================
    t.section("CORE API")
    t.test("Health check", "/health", expect_keys=["status"])
    t.test("API root", "/api/scan/list", expect_keys=["scans"])

    # ========================================
    # FILE BROWSER (nuevo)
    # ========================================
    t.section("FILE BROWSER")
    t.test("Browse /projects", "/api/browse?path=/projects", expect_keys=["path", "items"])
    t.test("Browse root", "/api/browse?path=/", expect_keys=["items"])

    # ========================================
    # SCAN API
    # ========================================
    t.section("SCAN API")
    t.test("List scans", "/api/scan/list", expect_keys=["scans"])

    # ========================================
    # CONSOLIDATION API
    # ========================================
    t.section("CONSOLIDATION API")
    # Obtener primer scan para tests
    try:
        resp = urlopen(f"{base_url}/api/scan/list", timeout=10)
        data = json.loads(resp.read())
        scans = data.get('scans', [])
        if scans:
            scan_id = scans[0].get('scan_id')
            t.test(f"Get siblings (scan {scan_id[:8]})",
                   f"/api/consolidation/siblings/{scan_id}?limit=10",
                   expect_keys=["groups", "total"])
            t.test(f"Get summary (scan {scan_id[:8]})",
                   f"/api/scan/result/{scan_id}/summary",
                   expect_keys=["scan_id"])
        else:
            print(f"  {YELLOW}[WARN]{RESET} No hay scans para probar consolidation")
    except Exception as e:
        print(f"  {YELLOW}[WARN]{RESET} Skip consolidation tests: {e}")

    # ========================================
    # AI API
    # ========================================
    t.section("AI API (Ollama)")
    t.test("AI status", "/api/ai/status", expect_keys=["available"])
    t.test("AI models", "/api/ai/status", expect_keys=["models"])

    # Test chat solo si Ollama está disponible
    try:
        resp = urlopen(f"{base_url}/api/ai/status", timeout=5)
        ai_data = json.loads(resp.read())
        if ai_data.get('available'):
            t.test("AI chat", "/api/ai/chat", method="POST",
                   data={"message": "test", "model": ai_data.get('default_model', 'qwen2.5-coder:7b')},
                   expect_keys=["response"], timeout=60)
        else:
            print(f"  {YELLOW}[WARN]{RESET} Ollama no disponible, skip chat test")
    except:
        print(f"  {YELLOW}[WARN]{RESET} Skip AI chat test")

    # ========================================
    # WORKSPACE API
    # ========================================
    t.section("WORKSPACE API")
    t.test("Workspace status", "/api/workspace", expect_keys=["path", "used_bytes", "limit_bytes"])

    # ========================================
    # RULES API
    # ========================================
    t.section("RULES API")
    t.test("List presets", "/api/rules/presets", expect_keys=["presets"])

    # ========================================
    # FRONTEND
    # ========================================
    t.section("FRONTEND")
    t.test("Main page loads", "/", expect_status=200)

    # ========================================
    # RESULT
    # ========================================
    return t.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HyperMatrix Smoke Tests")
    parser.add_argument("--url", default="http://localhost:26020",
                       help="Base URL of HyperMatrix")
    args = parser.parse_args()

    success = run_smoke_tests(args.url)
    sys.exit(0 if success else 1)
