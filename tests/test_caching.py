"""Tests for caching behavior — cache hit, clear_cache, ttl, cache=False."""

import asyncio
import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta

TEST_CACHE_DIR = "data/test_caching"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URL = "https://httpbin.org/html"
COMMON = {"load_strategies": ["domcontentloaded"], "max_retries": 1}


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_cache_hit_on_second_init():
    """Second GhostScraper with same URL should restore from cache without fetching."""
    cleanup()
    s1 = GhostScraper(url=URL, clear_cache=True, **COMMON)
    html1 = await s1.html()
    assert len(html1) > 100

    # Second instance — should load from cache (no Playwright needed)
    s2 = GhostScraper(url=URL, **COMMON)
    assert s2._html is not None, "Expected cache restore on init"
    assert s2._html == html1
    print("✅ cache hit on second init")


async def test_clear_cache_forces_refetch():
    """clear_cache=True should delete existing cache."""
    cleanup()
    s1 = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s1.html()

    # Verify cache file exists
    assert s1._cache.exists()

    # clear_cache=True should wipe it
    s2 = GhostScraper(url=URL, clear_cache=True, **COMMON)
    assert s2._html is None, "clear_cache should have deleted cache"
    print("✅ clear_cache forces re-fetch")


async def test_cache_disabled():
    """cache=False should never read or write cache."""
    cleanup()
    s1 = GhostScraper(url=URL, cache=False, clear_cache=True, **COMMON)
    await s1.html()

    # No cache file should exist
    cache_dir = Path(TEST_CACHE_DIR)
    json_files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
    assert len(json_files) == 0, f"Expected no cache files, found {json_files}"

    # Second instance should NOT have cached data
    s2 = GhostScraper(url=URL, cache=False, **COMMON)
    assert s2._html is None
    print("✅ cache=False disables caching")


async def test_ttl_expiry():
    """Expired TTL should cause cache miss."""
    cleanup()
    s1 = GhostScraper(url=URL, clear_cache=True, ttl=1, **COMMON)
    await s1.html()

    # Manually backdate the cache file
    from slugify import slugify
    cache_path = Path(TEST_CACHE_DIR) / f"{slugify(URL)}.json"
    assert cache_path.exists()

    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    raw["_saved_at"] = (datetime.now() - timedelta(days=2)).isoformat()
    cache_path.write_text(json.dumps(raw), encoding="utf-8")

    # New instance should see expired cache
    s2 = GhostScraper(url=URL, ttl=1, **COMMON)
    assert s2._html is None, "Expected cache miss due to TTL expiry"
    print("✅ TTL expiry causes cache miss")


async def test_cache_persists_all_four_fields():
    """Cache should persist _html, _response_code, _response_headers, _redirect_chain."""
    cleanup()
    s1 = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s1.html()

    s2 = GhostScraper(url=URL, **COMMON)
    assert s2._html is not None
    assert s2._response_code is not None
    assert s2._response_headers is not None
    assert s2._redirect_chain is not None
    print("✅ cache persists all four fields")


async def test_save_cache_and_clear_cache_entry():
    """save_cache() writes, clear_cache_entry() deletes."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()
    assert s._cache.exists()

    s.clear_cache_entry()
    assert not s._cache.exists()
    print("✅ save_cache / clear_cache_entry")


async def test_cache_stats():
    """cache_stats() returns key and exists flag."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()
    stats = s.cache_stats()
    assert "key" in stats
    assert stats["exists"] is True
    print(f"✅ cache_stats() — {stats}")


async def test_cache_list_keys():
    """cache_list_keys() lists cached entries."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()
    result = s.cache_list_keys()
    assert "keys" in result
    assert len(result["keys"]) >= 1
    print(f"✅ cache_list_keys() — {len(result['keys'])} keys")


async def main():
    cleanup()
    try:
        await test_cache_hit_on_second_init()
        await test_clear_cache_forces_refetch()
        await test_cache_disabled()
        await test_ttl_expiry()
        await test_cache_persists_all_four_fields()
        await test_save_cache_and_clear_cache_entry()
        await test_cache_stats()
        await test_cache_list_keys()
    finally:
        cleanup()
    print("\n🎉 All caching tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
