"""Phase 5: Verify GhostScraper class methods work as public API."""
import asyncio
from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.MAX_WORKERS = 1
ScraperDefaults.SUBPROCESS_BATCH_SIZE = 2


async def test_full_api():
    """End-to-end test through the public GhostScraper API."""
    urls = ["https://httpbin.org/html", "https://httpbin.org/robots.txt"]

    # Create stream via GhostScraper
    stream = GhostScraper.create_stream(
        urls=urls,
        dynamodb_table=None,
        stream_id="api-test",
        clear_cache=True,
        max_retries=1,
        load_strategies=["domcontentloaded"],
    )

    # Check status via GhostScraper
    status = GhostScraper.get_stream_status("api-test")
    assert status is not None
    assert status.stream_id == "api-test"
    print(f"  Status before: {status.status}, {status.pending} pending")

    # Check all streams
    all_streams = GhostScraper.get_all_streams()
    assert len(all_streams) >= 1
    print(f"  Active streams: {len(all_streams)}")

    # Consume
    async for scraper in stream:
        code = await scraper.response_code()
        print(f"  📄 {scraper.url[:50]} → {code}")

    # After completion
    print("✅ Full API test OK")

    await GhostScraper.shutdown()


async def test_exports():
    """Verify ScrapeStream and StreamStatus are importable from ghostscraper."""
    from ghostscraper import ScrapeStream, StreamStatus
    assert ScrapeStream is not None
    assert StreamStatus is not None
    print("✅ Exports OK")


if __name__ == "__main__":
    asyncio.run(test_full_api())
    asyncio.run(test_exports())
    print("\n🎉 Phase 5 all tests passed!")
