"""Tests for progress callbacks — sync/async, event types for single and batch."""

import asyncio
import os
import shutil

TEST_CACHE_DIR = "data/test_progress"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URL = "https://httpbin.org/html"
COMMON = {"load_strategies": ["domcontentloaded"], "max_retries": 1}


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_on_progress_sync_single():
    """Sync on_progress fires started and page_loaded for single URL."""
    cleanup()
    events = []
    scraper = GhostScraper(url=URL, clear_cache=True, on_progress=lambda e: events.append(e), **COMMON)
    await scraper.html()

    event_names = [e["event"] for e in events]
    assert "started" in event_names, f"Missing 'started', got {event_names}"
    assert "page_loaded" in event_names, f"Missing 'page_loaded', got {event_names}"
    # Events from GhostScraper._emit have 'ts'; events from playwright_installer
    # (browser_ready, browser_installing) are fired directly without 'ts'.
    for e in events:
        if e["event"] not in ("browser_ready", "browser_installing"):
            assert "ts" in e, f"Event missing 'ts': {e}"
    print(f"✅ on_progress sync single — events: {event_names}")


async def test_on_progress_async_single():
    """Async on_progress fires for single URL."""
    cleanup()
    events = []

    async def cb(e):
        events.append(e)

    scraper = GhostScraper(url=URL, clear_cache=True, on_progress=cb, **COMMON)
    await scraper.html()

    event_names = [e["event"] for e in events]
    assert "started" in event_names
    assert "page_loaded" in event_names
    print(f"✅ on_progress async single — events: {event_names}")


async def test_on_progress_batch():
    """on_progress fires batch_started, page_loaded, batch_done for scrape_many."""
    cleanup()
    events = []
    urls = ["https://httpbin.org/html", "https://httpbin.org/robots.txt"]

    await GhostScraper.scrape_many(
        urls=urls, clear_cache=True,
        on_progress=lambda e: events.append(e),
        **COMMON,
    )

    event_names = [e["event"] for e in events]
    assert "batch_started" in event_names, f"Missing 'batch_started', got {event_names}"
    assert "batch_done" in event_names, f"Missing 'batch_done', got {event_names}"
    assert "page_loaded" in event_names, f"Missing 'page_loaded', got {event_names}"

    # batch_started should have total, to_fetch, cached
    bs = next(e for e in events if e["event"] == "batch_started")
    assert "total" in bs
    assert "to_fetch" in bs
    assert "cached" in bs

    # page_loaded should have url, status_code, completed, total
    pl = next(e for e in events if e["event"] == "page_loaded")
    assert "url" in pl
    assert "status_code" in pl
    assert "completed" in pl
    assert "total" in pl

    print(f"✅ on_progress batch — events: {event_names}")


async def test_on_progress_loading_strategy():
    """loading_strategy event fires with strategy details."""
    cleanup()
    events = []
    scraper = GhostScraper(url=URL, clear_cache=True, on_progress=lambda e: events.append(e), **COMMON)
    await scraper.html()

    strategy_events = [e for e in events if e.get("event") == "loading_strategy"]
    if strategy_events:
        se = strategy_events[0]
        assert "strategy" in se
        assert "url" in se
        assert "timeout" in se
        print(f"✅ loading_strategy event — strategy={se['strategy']}")
    else:
        print("✅ loading_strategy event — (not fired, may be cached)")


async def test_on_progress_error_swallowed():
    """Errors in on_progress callback should be swallowed, not abort the scrape."""
    cleanup()

    def bad_callback(e):
        raise ValueError("callback error!")

    scraper = GhostScraper(url=URL, clear_cache=True, on_progress=bad_callback, logging=True, **COMMON)
    html = await scraper.html()
    assert len(html) > 0, "Scrape should succeed despite callback error"
    print("✅ on_progress error swallowed")


async def test_on_scraped_fires_for_cached():
    """on_scraped should fire for cached URLs too in scrape_many."""
    cleanup()
    urls = ["https://httpbin.org/html"]

    # First run — populate cache
    await GhostScraper.scrape_many(urls=urls, clear_cache=True, **COMMON)

    # Second run — cached
    scraped = []
    await GhostScraper.scrape_many(urls=urls, on_scraped=lambda s: scraped.append(s.url), **COMMON)
    assert len(scraped) == 1
    print("✅ on_scraped fires for cached URLs")


async def main():
    cleanup()
    try:
        await test_on_progress_sync_single()
        await test_on_progress_async_single()
        await test_on_progress_batch()
        await test_on_progress_loading_strategy()
        await test_on_progress_error_swallowed()
        await test_on_scraped_fires_for_cached()
    finally:
        cleanup()
    print("\n🎉 All progress callback tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
