"""Phase 4: Verify ScrapeStream end-to-end.

Uses httpbin.org for reliable test URLs.
"""
import asyncio
from ghostscraper.config import ScraperDefaults
from ghostscraper.stream.scrape_stream import ScrapeStream
from ghostscraper.stream.worker_pool import _WorkerPool

ScraperDefaults.MAX_WORKERS = 1
ScraperDefaults.SUBPROCESS_BATCH_SIZE = 2


async def test_basic_stream():
    """Stream 3 URLs, verify all are yielded."""
    urls = [
        "https://httpbin.org/html",
        "https://httpbin.org/robots.txt",
        "https://httpbin.org/links/1",
    ]

    progress_events = []

    stream = ScrapeStream(
        urls=urls,
        dynamodb_table=None,
        stream_id="test-basic",
        max_concurrent=2,
        clear_cache=True,
        max_retries=1,
        load_strategies=["domcontentloaded"],
        on_progress=lambda e: progress_events.append(e),
    )

    assert stream.stream_id == "test-basic"

    results = []
    async for scraper in stream:
        code = await scraper.response_code()
        results.append({"url": scraper.url, "code": code})
        print(f"  📄 {scraper.url[:50]} → {code}")

    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert stream.status.status == "completed"
    print(f"  Progress events: {len(progress_events)}")
    print("✅ Basic stream OK")

    await _WorkerPool.get_pool().shutdown()


async def test_stream_with_cached():
    """Run same URLs twice. Second run should yield from cache."""
    urls = ["https://httpbin.org/html"]

    # First run — fetches from web
    stream1 = ScrapeStream(
        urls=urls, dynamodb_table=None, stream_id="test-cache-1",
        max_retries=1, load_strategies=["domcontentloaded"],
    )
    async for s in stream1:
        assert await s.response_code() is not None

    await _WorkerPool.get_pool().shutdown()

    # Second run — should be cached
    stream2 = ScrapeStream(
        urls=urls, dynamodb_table=None, stream_id="test-cache-2",
        max_retries=1, load_strategies=["domcontentloaded"],
    )
    results = []
    async for s in stream2:
        results.append(s)

    assert len(results) == 1
    assert results[0]._html is not None, "Expected cached HTML"
    print("✅ Cached URL stream OK")

    await _WorkerPool.get_pool().shutdown()


async def test_stream_status():
    """Verify status tracking works."""
    urls = ["https://httpbin.org/html", "https://httpbin.org/robots.txt"]

    stream = ScrapeStream(
        urls=urls, dynamodb_table=None, stream_id="test-status",
        clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )

    # Before iteration
    status = stream.status
    assert status.total == 2
    assert status.status == "running"

    # Check registry
    assert "test-status" in ScrapeStream._streams

    # Consume
    async for _ in stream:
        pass

    print("✅ Stream status OK")

    await _WorkerPool.get_pool().shutdown()


async def test_stream_cancellation():
    """Cancel a stream mid-flight."""
    urls = [f"https://httpbin.org/delay/{i}" for i in range(1, 6)]

    stream = ScrapeStream(
        urls=urls, dynamodb_table=None, stream_id="test-cancel",
        subprocess_batch_size=2, max_concurrent=1,
        clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )

    count = 0
    async for scraper in stream:
        count += 1
        print(f"  Got result {count}: {scraper.url}")
        if count >= 2:
            stream.cancel()

    assert stream.status.status == "cancelled"
    assert count < len(urls), f"Expected early stop, got all {count} results"
    print(f"  Yielded {count}/{len(urls)} before cancel")
    print("✅ Stream cancellation OK")

    await _WorkerPool.get_pool().shutdown()


if __name__ == "__main__":
    asyncio.run(test_basic_stream())
    asyncio.run(test_stream_with_cached())
    asyncio.run(test_stream_status())
    asyncio.run(test_stream_cancellation())
    print("\n🎉 Phase 4 all tests passed!")
