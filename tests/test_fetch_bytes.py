"""Tests for GhostScraper.fetch_bytes — basic fetch, caching, clear_cache."""

import asyncio
import os
import shutil

TEST_CACHE_DIR = "data/test_fetch_bytes"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URL = "https://httpbin.org/html"


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_fetch_bytes_basic():
    """fetch_bytes returns (bytes, int, dict)."""
    body, status, headers = await GhostScraper.fetch_bytes(URL, max_retries=1)
    assert isinstance(body, bytes)
    assert len(body) > 0
    assert isinstance(status, int)
    assert isinstance(headers, dict)
    print(f"✅ fetch_bytes basic — {len(body)} bytes, status {status}")


async def test_fetch_bytes_with_cache():
    """fetch_bytes with cache=True persists and restores."""
    cleanup()
    body1, status1, _ = await GhostScraper.fetch_bytes(URL, cache=True, clear_cache=True, max_retries=1)
    assert len(body1) > 0

    # Second call should hit cache
    body2, status2, _ = await GhostScraper.fetch_bytes(URL, cache=True, max_retries=1)
    assert body1 == body2
    assert status1 == status2
    print("✅ fetch_bytes with cache")


async def test_fetch_bytes_clear_cache():
    """fetch_bytes with clear_cache=True forces re-fetch."""
    cleanup()
    await GhostScraper.fetch_bytes(URL, cache=True, clear_cache=True, max_retries=1)

    # clear_cache should re-fetch
    body, status, _ = await GhostScraper.fetch_bytes(URL, cache=True, clear_cache=True, max_retries=1)
    assert len(body) > 0
    assert isinstance(status, int)
    print("✅ fetch_bytes clear_cache")


async def test_fetch_bytes_no_cache():
    """fetch_bytes with cache=False (default) doesn't write files."""
    cleanup()
    await GhostScraper.fetch_bytes(URL, cache=False, max_retries=1)
    from pathlib import Path
    cache_dir = Path(TEST_CACHE_DIR)
    files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
    assert len(files) == 0
    print("✅ fetch_bytes no cache")


async def main():
    cleanup()
    try:
        await test_fetch_bytes_basic()
        await test_fetch_bytes_with_cache()
        await test_fetch_bytes_clear_cache()
        await test_fetch_bytes_no_cache()
    finally:
        cleanup()
    print("\n🎉 All fetch_bytes tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
