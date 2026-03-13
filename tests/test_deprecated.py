"""Tests for deprecated method shims — old names should work and emit DeprecationWarning."""

import asyncio
import os
import shutil
import warnings

TEST_CACHE_DIR = "data/test_deprecated"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URL = "https://httpbin.org/html"
COMMON = {"load_strategies": ["domcontentloaded"], "max_retries": 1}


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_json_cache_save():
    """json_cache_save() should work and emit DeprecationWarning."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.json_cache_save()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "json_cache_save" in str(w[0].message)
    print("✅ json_cache_save() deprecated")


async def test_json_cache_save_db():
    """json_cache_save_db() should work and emit DeprecationWarning."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.json_cache_save_db()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "json_cache_save_db" in str(w[0].message)
    print("✅ json_cache_save_db() deprecated")


async def test_json_cache_clear():
    """json_cache_clear() should delete cache and emit DeprecationWarning."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()
    assert s._cache.exists()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.json_cache_clear()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "json_cache_clear" in str(w[0].message)

    assert not s._cache.exists()
    print("✅ json_cache_clear() deprecated")


async def test_json_cache_stats():
    """json_cache_stats() should return stats and emit DeprecationWarning."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        stats = s.json_cache_stats()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "json_cache_stats" in str(w[0].message)

    assert "key" in stats
    assert "exists" in stats
    print(f"✅ json_cache_stats() deprecated — {stats}")


async def test_json_cache_list_db_keys():
    """json_cache_list_db_keys() should return keys and emit DeprecationWarning."""
    cleanup()
    s = GhostScraper(url=URL, clear_cache=True, **COMMON)
    await s.html()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = s.json_cache_list_db_keys()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "json_cache_list_db_keys" in str(w[0].message)

    assert "keys" in result
    print(f"✅ json_cache_list_db_keys() deprecated — {len(result['keys'])} keys")


async def main():
    cleanup()
    try:
        await test_json_cache_save()
        await test_json_cache_save_db()
        await test_json_cache_clear()
        await test_json_cache_stats()
        await test_json_cache_list_db_keys()
    finally:
        cleanup()
    print("\n🎉 All deprecated shim tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
