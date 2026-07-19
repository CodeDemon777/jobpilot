"""Master test runner for JobPilot QA system.

Runs all test suites in order:
1. Unit Tests (all modules)
2. API Tests (all endpoints)
3. Security Tests (OWASP Top 10)
4. Performance Tests (response times)
5. Scraper Validation Tests
"""

import sys
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

TEST_SUITES = [
    ("Unit Tests", "test_unit_all_modules.py"),
    ("API Tests", "test_api_endpoints.py"),
    ("Security Tests", "test_security.py"),
    ("Performance Tests", "test_performance.py"),
    ("Scraper Validation", "test_scraper_validation.py"),
]


def run_suite(name: str, script: str) -> bool:
    """Run a single test suite."""
    print(f"\n{'='*70}")
    print(f"Running: {name}")
    print(f"{'='*70}")

    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / script)],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode == 0


def main():
    """Run all test suites and report results."""
    print("JobPilot QA System — Master Test Runner")
    print("=" * 70)

    results = {}
    for name, script in TEST_SUITES:
        results[name] = run_suite(name, script)

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} — {name}")
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"Total: {len(results)} suites | Passed: {passed} | Failed: {failed}")
    print(f"{'='*70}")

    if failed > 0:
        print("\n❌ Some test suites failed. Please fix issues before deployment.")
        sys.exit(1)
    else:
        print("\n✅ All test suites passed. Ready for deployment!")
        sys.exit(0)


if __name__ == "__main__":
    main()
