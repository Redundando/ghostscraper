"""Tests for single-URL GhostScraper usage — all output methods from the README."""

import asyncio
import os
import shutil

from bs4 import BeautifulSoup
import newspaper

# Use a temp cache directory so tests don't pollute real cache
TEST_CACHE_DIR = "data/test_single_url"

from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.CACHE_DIRECTORY = TEST_CACHE_DIR
ScraperDefaults.LOGGING = False

URL = "https://httpbin.org/html"


def cleanup():
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)


async def test_html():
    """html() returns non-empty string."""
    scraper = GhostScraper(url=URL, clear_cache=True, load_strategies=["domcontentloaded"], max_retries=1)
    html = await scraper.html()
    assert isinstance(html, str)
    assert len(html) > 100
    assert "<html" in html.lower() or "<body" in html.lower()
    print("✅ html()")


async def test_response_code():
    """response_code() returns 200 for a valid page."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    code = await scraper.response_code()
    assert code == 200
    print("✅ response_code()")


async def test_response_headers():
    """response_headers() returns a dict with typical HTTP headers."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    headers = await scraper.response_headers()
    assert isinstance(headers, dict)
    assert len(headers) > 0
    print(f"✅ response_headers() — {len(headers)} headers")


async def test_redirect_chain():
    """redirect_chain() returns a list (may be empty for non-redirect URLs)."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    chain = await scraper.redirect_chain()
    assert isinstance(chain, list)
    # httpbin.org/html doesn't redirect, but the chain should contain at least the final response
    print(f"✅ redirect_chain() — {len(chain)} entries")


async def test_final_url():
    """final_url() returns a string URL."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    final = await scraper.final_url()
    assert isinstance(final, str)
    assert final.startswith("http")
    print(f"✅ final_url() → {final[:60]}")


async def test_markdown():
    """markdown() returns non-empty Markdown string."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    md = await scraper.markdown()
    assert isinstance(md, str)
    assert len(md) > 10
    print(f"✅ markdown() — {len(md)} chars")


async def test_text():
    """text() returns plain text via newspaper4k."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    txt = await scraper.text()
    assert isinstance(txt, str)
    print(f"✅ text() — {len(txt)} chars")


async def test_authors():
    """authors() returns a list."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    authors = await scraper.authors()
    assert isinstance(authors, list)
    print(f"✅ authors() — {authors}")


async def test_article():
    """article() returns a newspaper.Article object."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    art = await scraper.article()
    assert isinstance(art, newspaper.Article)
    print(f"✅ article()")


async def test_soup():
    """soup() returns a BeautifulSoup object."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    s = await scraper.soup()
    assert isinstance(s, BeautifulSoup)
    print(f"✅ soup()")


async def test_seo():
    """seo() returns a dict. httpbin/html has a <title> at minimum."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    seo = await scraper.seo()
    assert isinstance(seo, dict)
    # httpbin.org/html has <title>Herman Melville - Moby Dick</title>
    if "title" in seo:
        assert isinstance(seo["title"], str)
    print(f"✅ seo() — keys: {list(seo.keys())}")


async def test_subsequent_calls_return_cached():
    """Calling html() twice returns the same result without re-fetching."""
    scraper = GhostScraper(url=URL, load_strategies=["domcontentloaded"], max_retries=1)
    html1 = await scraper.html()
    html2 = await scraper.html()
    assert html1 == html2
    print("✅ subsequent calls return cached value")


async def main():
    cleanup()
    try:
        await test_html()
        await test_response_code()
        await test_response_headers()
        await test_redirect_chain()
        await test_final_url()
        await test_markdown()
        await test_text()
        await test_authors()
        await test_article()
        await test_soup()
        await test_seo()
        await test_subsequent_calls_return_cached()
    finally:
        cleanup()
    print("\n🎉 All single-URL tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
