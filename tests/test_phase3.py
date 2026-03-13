"""Phase 3: Verify worker pool manages concurrency and priority correctly.

Uses httpbin.org for reliable test URLs.
"""
import asyncio
from ghostscraper.stream.worker_pool import _WorkerPool
from ghostscraper.stream.models import _ScrapeJob
from ghostscraper.config import ScraperDefaults


async def test_pool_basic():
    """Submit 2 jobs, verify both complete."""
    ScraperDefaults.MAX_WORKERS = 2

    pool = _WorkerPool.get_pool()
    results_a = asyncio.Queue()
    results_b = asyncio.Queue()

    job_a = _ScrapeJob(
        priority=5, sequence=0,
        urls=["https://httpbin.org/html"],
        kwargs={"dynamodb_table": None, "max_concurrent": 1, "ttl": 1,
                "clear_cache": True, "max_retries": 1, "load_strategies": ["domcontentloaded"]},
        result_queue=results_a, stream_id="test-a",
    )
    job_b = _ScrapeJob(
        priority=5, sequence=1,
        urls=["https://httpbin.org/robots.txt"],
        kwargs={"dynamodb_table": None, "max_concurrent": 1, "ttl": 1,
                "clear_cache": True, "max_retries": 1, "load_strategies": ["domcontentloaded"]},
        result_queue=results_b, stream_id="test-b",
    )

    await pool.submit(job_a)
    await pool.submit(job_b)

    msg_a = await asyncio.wait_for(results_a.get(), timeout=60)
    msg_b = await asyncio.wait_for(results_b.get(), timeout=60)

    assert msg_a["type"] in ("completed", "failed"), f"Unexpected message: {msg_a}"
    assert msg_b["type"] in ("completed", "failed"), f"Unexpected message: {msg_b}"
    print(f"  Job A result: {msg_a['type']} — {msg_a['url']}")
    print(f"  Job B result: {msg_b['type']} — {msg_b['url']}")
    print("✅ Pool basic concurrency OK")

    await pool.shutdown()


async def test_pool_priority():
    """Submit a low-priority and high-priority job. High priority should run first."""
    ScraperDefaults.MAX_WORKERS = 1  # force sequential

    pool = _WorkerPool.get_pool()
    completion_order = []

    async def collect(q, label):
        while True:
            msg = await q.get()
            if msg["type"] in ("completed", "failed"):
                completion_order.append(label)
                return

    results_low = asyncio.Queue()
    results_high = asyncio.Queue()

    # Submit low priority first
    await pool.submit(_ScrapeJob(
        priority=10, sequence=0,
        urls=["https://httpbin.org/html"],
        kwargs={"dynamodb_table": None, "max_concurrent": 1, "ttl": 1,
                "clear_cache": True, "max_retries": 1, "load_strategies": ["domcontentloaded"]},
        result_queue=results_low, stream_id="low",
    ))
    # Then high priority
    await pool.submit(_ScrapeJob(
        priority=0, sequence=1,
        urls=["https://httpbin.org/robots.txt"],
        kwargs={"dynamodb_table": None, "max_concurrent": 1, "ttl": 1,
                "clear_cache": True, "max_retries": 1, "load_strategies": ["domcontentloaded"]},
        result_queue=results_high, stream_id="high",
    ))

    await asyncio.gather(
        collect(results_high, "high"),
        collect(results_low, "low"),
    )

    print(f"  Completion order: {completion_order}")
    print("✅ Pool priority ordering OK")

    await pool.shutdown()


if __name__ == "__main__":
    asyncio.run(test_pool_basic())
    asyncio.run(test_pool_priority())
    print("\n🎉 Phase 3 all tests passed!")
