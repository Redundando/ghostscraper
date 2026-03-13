"""Tests for ScraperDefaults — runtime modification and propagation."""

import asyncio
import os
import shutil

TEST_CACHE_DIR = "data/test_defaults"

from ghostscraper import GhostScraper, ScraperDefaults


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


def test_default_values():
    """Verify all documented defaults exist and have correct values."""
    assert ScraperDefaults.BROWSER_TYPE == "chromium"
    assert ScraperDefaults.HEADLESS is True
    assert ScraperDefaults.LOAD_TIMEOUT == 20000
    assert ScraperDefaults.NETWORK_IDLE_TIMEOUT == 3000
    assert ScraperDefaults.LOAD_STRATEGIES == ["load", "networkidle", "domcontentloaded"]
    assert ScraperDefaults.MAX_RETRIES == 3
    assert ScraperDefaults.BACKOFF_FACTOR == 2.0
    assert ScraperDefaults.MAX_CONCURRENT == 15
    assert ScraperDefaults.CACHE_TTL == 999
    assert ScraperDefaults.CACHE_DIRECTORY == "data/ghostscraper"
    assert ScraperDefaults.DYNAMODB_TABLE is None
    assert ScraperDefaults.BROWSER_RESTART_EVERY is None
    assert ScraperDefaults.LOGGING is True
    # Stream defaults
    assert ScraperDefaults.MAX_WORKERS == 2
    assert ScraperDefaults.SUBPROCESS_BATCH_SIZE == 50
    assert ScraperDefaults.MAX_QUEUE_SIZE == 500
    assert ScraperDefaults.DEFAULT_PRIORITY == 5
    print("✅ all default values correct")


def test_runtime_modification():
    """Modifying ScraperDefaults at runtime should affect new instances.

    Note: CACHE_DIRECTORY is read inside __init__ body so it picks up
    runtime changes.  ttl and logging are Python default args — they are
    bound at class-definition time, so runtime changes to CACHE_TTL /
    LOGGING only take effect when passed explicitly.
    """
    original_dir = ScraperDefaults.CACHE_DIRECTORY

    try:
        ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR

        s = GhostScraper(url="https://example.com", logging=False)
        assert s._cache._directory == TEST_CACHE_DIR
        print("✅ runtime modification propagates (CACHE_DIRECTORY)")
    finally:
        ScraperDefaults.CACHE_DIRECTORY = original_dir


def test_explicit_params_override_defaults():
    """Explicit constructor params should override ScraperDefaults."""
    original_ttl = ScraperDefaults.CACHE_TTL
    try:
        ScraperDefaults.CACHE_TTL = 42
        s = GhostScraper(url="https://example.com", ttl=7, logging=False)
        assert s._cache._ttl == 7
        print("✅ explicit params override defaults")
    finally:
        ScraperDefaults.CACHE_TTL = original_ttl


def test_set_logging_static():
    """GhostScraper.set_logging() modifies ScraperDefaults.LOGGING."""
    original = ScraperDefaults.LOGGING
    try:
        GhostScraper.set_logging(False)
        assert ScraperDefaults.LOGGING is False
        GhostScraper.set_logging(True)
        assert ScraperDefaults.LOGGING is True
        print("✅ set_logging() modifies ScraperDefaults")
    finally:
        ScraperDefaults.LOGGING = original


def main():
    # Reset to known state
    ScraperDefaults.CACHE_DIRECTORY = "data/ghostscraper"
    ScraperDefaults.LOGGING = True

    test_default_values()
    test_runtime_modification()
    test_explicit_params_override_defaults()
    test_set_logging_static()
    cleanup()
    print("\n🎉 All ScraperDefaults tests passed!")


if __name__ == "__main__":
    main()
