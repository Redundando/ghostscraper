"""Tests for package exports — verify all public API symbols are importable."""


def test_exports():
    """All documented exports should be importable from ghostscraper."""
    from ghostscraper import (
        GhostScraper,
        PlaywrightScraper,
        ScraperDefaults,
        ScrapeStream,
        StreamStatus,
        check_browser_installed,
        install_browser,
    )

    assert GhostScraper is not None
    assert PlaywrightScraper is not None
    assert ScraperDefaults is not None
    assert ScrapeStream is not None
    assert StreamStatus is not None
    assert callable(check_browser_installed)
    assert callable(install_browser)
    print("✅ all exports importable")


def test_version():
    """__version__ should be a string."""
    import ghostscraper
    assert isinstance(ghostscraper.__version__, str)
    assert len(ghostscraper.__version__) > 0
    print(f"✅ version = {ghostscraper.__version__}")


def test_ghostscraper_has_class_methods():
    """GhostScraper should have all documented class methods."""
    from ghostscraper import GhostScraper

    assert hasattr(GhostScraper, "scrape_many")
    assert hasattr(GhostScraper, "fetch_bytes")
    assert hasattr(GhostScraper, "create_stream")
    assert hasattr(GhostScraper, "get_stream_status")
    assert hasattr(GhostScraper, "get_all_streams")
    assert hasattr(GhostScraper, "cancel_stream")
    assert hasattr(GhostScraper, "shutdown")
    assert hasattr(GhostScraper, "set_logging")
    print("✅ all class methods present")


def test_ghostscraper_has_instance_methods():
    """GhostScraper instance should have all documented async methods."""
    from ghostscraper import GhostScraper
    import asyncio

    s = GhostScraper(url="https://example.com", logging=False)
    for method in ("html", "response_code", "response_headers", "redirect_chain",
                   "final_url", "markdown", "text", "authors", "article", "soup", "seo"):
        assert hasattr(s, method), f"Missing method: {method}"
        assert asyncio.iscoroutinefunction(getattr(s, method)), f"{method} should be async"

    # Cache helpers (sync)
    for method in ("save_cache", "clear_cache_entry", "cache_stats", "cache_list_keys"):
        assert hasattr(s, method), f"Missing method: {method}"

    # Deprecated shims
    for method in ("json_cache_save", "json_cache_save_db", "json_cache_clear",
                   "json_cache_stats", "json_cache_list_db_keys"):
        assert hasattr(s, method), f"Missing deprecated shim: {method}"

    print("✅ all instance methods present")


def test_ghostscraper_attributes():
    """GhostScraper instance should have url and error attributes."""
    from ghostscraper import GhostScraper

    s = GhostScraper(url="https://example.com", logging=False)
    assert s.url == "https://example.com"
    assert s.error is None
    print("✅ instance attributes")


def main():
    test_exports()
    test_version()
    test_ghostscraper_has_class_methods()
    test_ghostscraper_has_instance_methods()
    test_ghostscraper_attributes()
    print("\n🎉 All export tests passed!")


if __name__ == "__main__":
    main()
