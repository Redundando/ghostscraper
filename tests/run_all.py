"""Run all README-based test suites in sequence."""

import subprocess
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    "test_exports.py",
    "test_defaults.py",
    "test_scrape_cache_unit.py",
    "test_deprecated.py",
    "test_single_url.py",
    "test_caching.py",
    "test_scrape_many.py",
    "test_fetch_bytes.py",
    "test_progress.py",
    "test_options.py",
    "test_playwright_scraper.py",
]


def main():
    failed = []
    for test in TESTS:
        path = os.path.join(TEST_DIR, test)
        print(f"\n{'='*60}")
        print(f"Running {test}...")
        print(f"{'='*60}")
        result = subprocess.run([sys.executable, path], cwd=os.path.dirname(TEST_DIR))
        if result.returncode != 0:
            failed.append(test)
            print(f"❌ {test} FAILED (exit code {result.returncode})")
        else:
            print(f"✅ {test} PASSED")

    print(f"\n{'='*60}")
    if failed:
        print(f"❌ {len(failed)} test suite(s) failed: {failed}")
        sys.exit(1)
    else:
        print(f"🎉 All {len(TESTS)} test suites passed!")


if __name__ == "__main__":
    main()
