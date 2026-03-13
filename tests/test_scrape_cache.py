"""Tests for Phase R1: ScrapeCache local backend."""

import json
import os
import shutil
from datetime import datetime, timedelta

from ghostscraper.scrape_cache import ScrapeCache

TEST_DIR = "data/_test_scrape_cache"


def setup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


def teardown():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)


def test_local_save_load_exists_delete():
    c = ScrapeCache(key="test-key", directory=TEST_DIR, ttl=999)
    assert c.exists() is False
    assert c.load() is None

    c.save({"_html": "<h1>hi</h1>", "_response_code": 200})
    assert c.exists() is True

    data = c.load()
    assert data["_html"] == "<h1>hi</h1>"
    assert data["_response_code"] == 200

    c.delete()
    assert c.exists() is False


def test_ttl_expiry():
    c = ScrapeCache(key="ttl-test", directory=TEST_DIR, ttl=1)
    c.save({"x": 1})

    path = c._local_path()
    raw = json.loads(path.read_text())
    raw["_saved_at"] = (datetime.now() - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(raw))

    assert c.load() is None
    assert c.exists() is False


def test_bytes_round_trip():
    c = ScrapeCache(key="bytes-test", directory=TEST_DIR, ttl=999)
    c.save_bytes(b"hello world", 200, {"content-type": "text/plain"})

    result = c.load_bytes()
    assert result is not None
    body, status, headers = result
    assert body == b"hello world"
    assert status == 200
    assert headers["content-type"] == "text/plain"


def test_cache_disabled():
    c = ScrapeCache(key="disabled", directory=TEST_DIR, ttl=999, cache=False)
    c.save({"x": 1})
    assert c.load() is None
    assert c.exists() is False
    c.delete()
    assert c.list_keys() == {"keys": [], "last_key": None}


def test_list_keys():
    ScrapeCache(key="aaa", directory=TEST_DIR, ttl=999).save({"a": 1})
    ScrapeCache(key="bbb", directory=TEST_DIR, ttl=999).save({"b": 2})

    keys = ScrapeCache(key="any", directory=TEST_DIR, ttl=999).list_keys()
    assert "aaa" in keys["keys"]
    assert "bbb" in keys["keys"]


if __name__ == "__main__":
    setup()
    try:
        test_local_save_load_exists_delete()
        print("test_local_save_load_exists_delete: PASS")

        test_ttl_expiry()
        print("test_ttl_expiry: PASS")

        test_bytes_round_trip()
        print("test_bytes_round_trip: PASS")

        test_cache_disabled()
        print("test_cache_disabled: PASS")

        test_list_keys()
        print("test_list_keys: PASS")

        print("\nAll ScrapeCache R1 tests passed!")
    finally:
        teardown()
