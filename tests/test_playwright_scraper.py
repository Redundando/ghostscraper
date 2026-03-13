"""Tests for PlaywrightScraper — direct low-level usage."""

import asyncio

from ghostscraper import PlaywrightScraper

URL = "https://httpbin.org/html"
COMMON = {"load_strategies": ["domcontentloaded"], "max_retries": 1, "logging": False}


async def test_fetch():
    """fetch() returns (html, status_code, headers, redirect_chain)."""
    scraper = PlaywrightScraper(url=URL, **COMMON)
    try:
        html, code, headers, chain = await scraper.fetch()
        assert isinstance(html, str)
        assert len(html) > 100
        assert code == 200
        assert isinstance(headers, dict)
        assert isinstance(chain, list)
        print(f"✅ fetch() — {len(html)} chars, status {code}")
    finally:
        await scraper.close()


async def test_fetch_url():
    """fetch_url() fetches a specific URL using shared browser."""
    scraper = PlaywrightScraper(**COMMON)
    try:
        html, code, headers, chain = await scraper.fetch_url(URL)
        assert len(html) > 100
        assert code == 200
        print(f"✅ fetch_url() — status {code}")
    finally:
        await scraper.close()


async def test_fetch_many():
    """fetch_many() fetches multiple URLs in parallel."""
    urls = ["https://httpbin.org/html", "https://httpbin.org/robots.txt"]
    scraper = PlaywrightScraper(**COMMON)
    try:
        results = await scraper.fetch_many(urls, max_concurrent=2)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, tuple)
        print(f"✅ fetch_many() — {len(results)} results")
    finally:
        await scraper.close()


async def test_fetch_and_close():
    """fetch_and_close() fetches and immediately closes browser."""
    scraper = PlaywrightScraper(url=URL, **COMMON)
    html, code, headers, chain = await scraper.fetch_and_close()
    assert len(html) > 100
    assert code == 200
    assert scraper._browser is None, "Browser should be closed"
    assert scraper._playwright is None, "Playwright should be stopped"
    print("✅ fetch_and_close()")


async def test_context_manager():
    """async with PlaywrightScraper(...) as browser should work."""
    async with PlaywrightScraper(**COMMON) as browser:
        html, code, headers, chain = await browser.fetch_url(URL)
        assert len(html) > 100
        assert code == 200
    # After exit, resources should be cleaned up
    assert browser._browser is None
    print("✅ context manager")


async def test_check_and_install_browser():
    """check_and_install_browser() returns True for chromium."""
    scraper = PlaywrightScraper(**COMMON)
    try:
        result = await scraper.check_and_install_browser()
        assert result is True
        print("✅ check_and_install_browser()")
    finally:
        await scraper.close()


async def test_fetch_bytes():
    """PlaywrightScraper.fetch_bytes() returns (bytes, status, headers)."""
    async with PlaywrightScraper(**COMMON) as browser:
        body, status, headers = await browser.fetch_bytes(URL)
        assert isinstance(body, bytes)
        assert len(body) > 0
        assert isinstance(status, int)
        assert isinstance(headers, dict)
        print(f"✅ fetch_bytes() — {len(body)} bytes, status {status}")


async def test_last_status_code():
    """last_status_code is updated after fetch()."""
    scraper = PlaywrightScraper(url=URL, **COMMON)
    try:
        await scraper.fetch()
        assert scraper.last_status_code == 200
        print("✅ last_status_code")
    finally:
        await scraper.close()


async def test_no_url_raises():
    """fetch() without URL should raise ValueError."""
    scraper = PlaywrightScraper(**COMMON)
    try:
        await scraper.fetch()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "No URL" in str(e)
        print("✅ fetch() without URL raises ValueError")
    finally:
        await scraper.close()


async def main():
    await test_fetch()
    await test_fetch_url()
    await test_fetch_many()
    await test_fetch_and_close()
    await test_context_manager()
    await test_check_and_install_browser()
    await test_fetch_bytes()
    await test_last_status_code()
    await test_no_url_raises()
    print("\n🎉 All PlaywrightScraper tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
