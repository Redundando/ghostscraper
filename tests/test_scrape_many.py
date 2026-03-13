"""Tests for scrape_many — batch scraping, fail_fast, on_scraped, browser_restart_every."""

import asyncio
import os
import shutil

TEST_CACHE_DIR = "data/test_scrape_many"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URLS = [
    "https://httpbin.org/html",
    "https://httpbin.org/robots.txt",
    "https://httpbin.org/links/1",
]
COMMON = {"load_strategies": ["domcontentloaded"], "max_retries": 1}


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_basic_batch():
    """scrape_many returns one scraper per URL in order."""
    cleanup()
    scrapers = await GhostScraper.scrape_many(urls=URLS, max_concurrent=3, clear_cache=True, **COMMON)
    assert len(scrapers) == len(URLS)
    for i, s in enumerate(scrapers):
        assert s.url == URLS[i]
        code = await s.response_code()
        assert code is not None
        print(f"  {s.url[-30:]} → {code}")
    print("✅ basic batch")


async def test_max_concurrent():
    """max_concurrent=1 should still work (sequential)."""
    cleanup()
    scrapers = await GhostScraper.scrape_many(urls=URLS[:2], max_concurrent=1, clear_cache=True, **COMMON)
    assert len(scrapers) == 2
    for s in scrapers:
        assert await s.response_code() is not None
    print("✅ max_concurrent=1")


async def test_fail_fast_false():
    """fail_fast=False captures errors per-scraper instead of aborting."""
    cleanup()
    bad_urls = ["https://httpbin.org/html", "https://httpbin.org/status/404"]
    scrapers = await GhostScraper.scrape_many(
        urls=bad_urls, fail_fast=False, clear_cache=True, no_retry_on=[404], **COMMON,
    )
    assert len(scrapers) == 2
    # First should succeed
    assert await scrapers[0].response_code() == 200
    # Second: 404 with no_retry_on means it returns 404 status, not an error
    code = await scrapers[1].response_code()
    assert code == 404 or scrapers[1].error is not None
    print("✅ fail_fast=False")


async def test_error_attribute():
    """When error is set, html() returns '' and response_code() returns None."""
    s = GhostScraper(url="https://example.com", logging=False)
    s.error = Exception("test error")
    assert await s.html() == ""
    assert await s.response_code() is None
    print("✅ error attribute behavior")


async def test_on_scraped_callback():
    """on_scraped fires for each URL (sync callback)."""
    cleanup()
    scraped_urls = []

    def on_scraped(scraper):
        scraped_urls.append(scraper.url)

    await GhostScraper.scrape_many(
        urls=URLS[:2], on_scraped=on_scraped, clear_cache=True, **COMMON,
    )
    assert len(scraped_urls) == 2
    print(f"✅ on_scraped sync — {scraped_urls}")


async def test_on_scraped_async_callback():
    """on_scraped fires for each URL (async callback)."""
    cleanup()
    scraped_urls = []

    async def on_scraped(scraper):
        scraped_urls.append(scraper.url)

    await GhostScraper.scrape_many(
        urls=URLS[:2], on_scraped=on_scraped, clear_cache=True, **COMMON,
    )
    assert len(scraped_urls) == 2
    print(f"✅ on_scraped async — {scraped_urls}")


async def test_browser_restart_every():
    """browser_restart_every splits batch into browser chunks."""
    cleanup()
    scrapers = await GhostScraper.scrape_many(
        urls=URLS, browser_restart_every=2, clear_cache=True, **COMMON,
    )
    assert len(scrapers) == len(URLS)
    for s in scrapers:
        assert await s.response_code() is not None
    print("✅ browser_restart_every=2")


async def test_cached_urls_skipped():
    """Second scrape_many call should skip already-cached URLs."""
    cleanup()
    # First run — fetches all
    await GhostScraper.scrape_many(urls=URLS[:2], clear_cache=True, **COMMON)

    # Second run — should find them cached
    scrapers = await GhostScraper.scrape_many(urls=URLS[:2], **COMMON)
    assert len(scrapers) == 2
    for s in scrapers:
        assert s._html is not None
    print("✅ cached URLs skipped on second run")


async def test_scrape_many_preserves_order():
    """Results should be in the same order as input URLs."""
    cleanup()
    scrapers = await GhostScraper.scrape_many(urls=URLS, clear_cache=True, **COMMON)
    for i, s in enumerate(scrapers):
        assert s.url == URLS[i], f"Order mismatch at index {i}"
    print("✅ scrape_many preserves order")


async def main():
    cleanup()
    try:
        await test_basic_batch()
        await test_max_concurrent()
        await test_fail_fast_false()
        await test_error_attribute()
        await test_on_scraped_callback()
        await test_on_scraped_async_callback()
        await test_browser_restart_every()
        await test_cached_urls_skipped()
        await test_scrape_many_preserves_order()
    finally:
        cleanup()
    print("\n🎉 All scrape_many tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
