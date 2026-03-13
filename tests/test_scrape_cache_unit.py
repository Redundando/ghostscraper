"""Tests for ScrapeCache — local JSON mode, disabled mode, bytes, TTL, exists, delete, list_keys."""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

TEST_CACHE_DIR = "data/test_scrape_cache_unit"

from ghostscraper.scrape_cache import ScrapeCache


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


def test_save_and_load():
    """save() writes, load() reads back."""
    cleanup()
    cache = ScrapeCache(key="test-1", directory=TEST_CACHE_DIR, ttl=999)
    data = {"_html": "<html>hello</html>", "_response_code": 200}
    cache.save(data)

    loaded = cache.load()
    assert loaded is not None
    assert loaded["_html"] == "<html>hello</html>"
    assert loaded["_response_code"] == 200
    print("✅ save and load")


def test_exists():
    """exists() returns True after save, False after delete."""
    cleanup()
    cache = ScrapeCache(key="test-exists", directory=TEST_CACHE_DIR, ttl=999)
    assert cache.exists() is False

    cache.save({"foo": "bar"})
    assert cache.exists() is True

    cache.delete()
    assert cache.exists() is False
    print("✅ exists")


def test_delete():
    """delete() removes the cache file."""
    cleanup()
    cache = ScrapeCache(key="test-del", directory=TEST_CACHE_DIR, ttl=999)
    cache.save({"x": 1})
    assert cache.exists()

    cache.delete()
    assert not cache.exists()
    assert cache.load() is None
    print("✅ delete")


def test_ttl_valid():
    """load() returns data when TTL is not expired."""
    cleanup()
    cache = ScrapeCache(key="test-ttl-ok", directory=TEST_CACHE_DIR, ttl=10)
    cache.save({"data": "fresh"})

    loaded = cache.load()
    assert loaded is not None
    assert loaded["data"] == "fresh"
    print("✅ TTL valid")


def test_ttl_expired():
    """load() returns None when TTL is expired."""
    cleanup()
    cache = ScrapeCache(key="test-ttl-exp", directory=TEST_CACHE_DIR, ttl=1)
    cache.save({"data": "old"})

    # Manually backdate
    path = Path(TEST_CACHE_DIR) / "test-ttl-exp.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["_saved_at"] = (datetime.now() - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = cache.load()
    assert loaded is None
    print("✅ TTL expired")


def test_ttl_expired_exists():
    """exists() returns False when TTL is expired."""
    cleanup()
    cache = ScrapeCache(key="test-ttl-exists", directory=TEST_CACHE_DIR, ttl=1)
    cache.save({"data": "old"})

    path = Path(TEST_CACHE_DIR) / "test-ttl-exists.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["_saved_at"] = (datetime.now() - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(raw), encoding="utf-8")

    assert cache.exists() is False
    print("✅ TTL expired → exists() returns False")


def test_list_keys():
    """list_keys() returns saved keys."""
    cleanup()
    ScrapeCache(key="key-a", directory=TEST_CACHE_DIR, ttl=999).save({"a": 1})
    ScrapeCache(key="key-b", directory=TEST_CACHE_DIR, ttl=999).save({"b": 2})
    ScrapeCache(key="key-c", directory=TEST_CACHE_DIR, ttl=999).save({"c": 3})

    cache = ScrapeCache(key="any", directory=TEST_CACHE_DIR, ttl=999)
    result = cache.list_keys()
    assert "keys" in result
    assert len(result["keys"]) == 3
    assert "key-a" in result["keys"]
    assert "key-b" in result["keys"]
    assert "key-c" in result["keys"]
    print(f"✅ list_keys — {result['keys']}")


def test_list_keys_limit():
    """list_keys(limit=2) returns at most 2 keys."""
    cleanup()
    for i in range(5):
        ScrapeCache(key=f"lk-{i}", directory=TEST_CACHE_DIR, ttl=999).save({"i": i})

    cache = ScrapeCache(key="any", directory=TEST_CACHE_DIR, ttl=999)
    result = cache.list_keys(limit=2)
    assert len(result["keys"]) == 2
    print("✅ list_keys with limit")


def test_save_bytes_and_load_bytes():
    """save_bytes() and load_bytes() round-trip binary data."""
    cleanup()
    cache = ScrapeCache(key="test-bytes", directory=TEST_CACHE_DIR, ttl=999)
    original = b"\x89PNG\r\n\x1a\nfake image data"
    cache.save_bytes(original, status_code=200, headers={"content-type": "image/png"})

    result = cache.load_bytes()
    assert result is not None
    body, status, headers = result
    assert body == original
    assert status == 200
    assert headers["content-type"] == "image/png"
    print("✅ save_bytes / load_bytes round-trip")


def test_load_bytes_missing():
    """load_bytes() returns None when no cache exists."""
    cleanup()
    cache = ScrapeCache(key="no-bytes", directory=TEST_CACHE_DIR, ttl=999)
    assert cache.load_bytes() is None
    print("✅ load_bytes missing → None")


# --- Disabled mode ---

def test_disabled_save_noop():
    """cache=False: save() is a no-op."""
    cleanup()
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    cache.save({"x": 1})
    assert not Path(TEST_CACHE_DIR).exists() or len(list(Path(TEST_CACHE_DIR).glob("*.json"))) == 0
    print("✅ disabled: save is no-op")


def test_disabled_load_none():
    """cache=False: load() returns None."""
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    assert cache.load() is None
    print("✅ disabled: load returns None")


def test_disabled_exists_false():
    """cache=False: exists() returns False."""
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    assert cache.exists() is False
    print("✅ disabled: exists returns False")


def test_disabled_delete_noop():
    """cache=False: delete() is a no-op."""
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    cache.delete()  # should not raise
    print("✅ disabled: delete is no-op")


def test_disabled_list_keys_empty():
    """cache=False: list_keys() returns empty."""
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    result = cache.list_keys()
    assert result == {"keys": [], "last_key": None}
    print("✅ disabled: list_keys returns empty")


def test_disabled_bytes_noop():
    """cache=False: save_bytes/load_bytes are no-ops."""
    cache = ScrapeCache(key="disabled", directory=TEST_CACHE_DIR, ttl=999, cache=False)
    cache.save_bytes(b"data", 200, {})
    assert cache.load_bytes() is None
    print("✅ disabled: bytes are no-ops")


# --- Edge cases ---

def test_corrupted_json():
    """load() returns None for corrupted JSON files."""
    cleanup()
    path = Path(TEST_CACHE_DIR) / "corrupted.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json {{{", encoding="utf-8")

    cache = ScrapeCache(key="corrupted", directory=TEST_CACHE_DIR, ttl=999)
    assert cache.load() is None
    print("✅ corrupted JSON → load returns None")


def test_corrupted_json_exists():
    """exists() returns False for corrupted JSON files."""
    cleanup()
    path = Path(TEST_CACHE_DIR) / "bad-exists.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json", encoding="utf-8")

    cache = ScrapeCache(key="bad-exists", directory=TEST_CACHE_DIR, ttl=999)
    assert cache.exists() is False
    print("✅ corrupted JSON → exists returns False")


def test_overwrite():
    """save() overwrites existing cache."""
    cleanup()
    cache = ScrapeCache(key="overwrite", directory=TEST_CACHE_DIR, ttl=999)
    cache.save({"v": 1})
    assert cache.load()["v"] == 1

    cache.save({"v": 2})
    assert cache.load()["v"] == 2
    print("✅ overwrite existing cache")


def main():
    cleanup()
    try:
        test_save_and_load()
        test_exists()
        test_delete()
        test_ttl_valid()
        test_ttl_expired()
        test_ttl_expired_exists()
        test_list_keys()
        test_list_keys_limit()
        test_save_bytes_and_load_bytes()
        test_load_bytes_missing()
        test_disabled_save_noop()
        test_disabled_load_none()
        test_disabled_exists_false()
        test_disabled_delete_noop()
        test_disabled_list_keys_empty()
        test_disabled_bytes_noop()
        test_corrupted_json()
        test_corrupted_json_exists()
        test_overwrite()
    finally:
        cleanup()
    print("\n🎉 All ScrapeCache unit tests passed!")


if __name__ == "__main__":
    main()
