"""Phase 1: Verify models and config."""
from ghostscraper.config import ScraperDefaults
from ghostscraper.stream.models import StreamStatus, _ScrapeJob
import asyncio

def test_config_defaults():
    assert ScraperDefaults.MAX_WORKERS == 2
    assert ScraperDefaults.SUBPROCESS_BATCH_SIZE == 50
    assert ScraperDefaults.MAX_QUEUE_SIZE == 500
    assert ScraperDefaults.DEFAULT_PRIORITY == 5
    print("✅ Config defaults OK")

def test_stream_status():
    status = StreamStatus(stream_id="test-1", total=100, completed=30, failed=2, pending=68, status="running")
    assert status.stream_id == "test-1"
    assert status.pending == 68
    print("✅ StreamStatus OK")

def test_job_ordering():
    q = asyncio.PriorityQueue()
    job_low = _ScrapeJob(priority=5, sequence=0, urls=[], kwargs={}, result_queue=None, stream_id="a")
    job_high = _ScrapeJob(priority=0, sequence=1, urls=[], kwargs={}, result_queue=None, stream_id="b")
    q.put_nowait(job_low)
    q.put_nowait(job_high)
    first = q.get_nowait()
    assert first.stream_id == "b", "Higher priority (lower number) should come first"
    print("✅ Job ordering OK")

def test_same_priority_interleaving():
    q = asyncio.PriorityQueue()
    q.put_nowait(_ScrapeJob(priority=5, sequence=0, urls=[], kwargs={}, result_queue=None, stream_id="a"))
    q.put_nowait(_ScrapeJob(priority=5, sequence=1, urls=[], kwargs={}, result_queue=None, stream_id="b"))
    q.put_nowait(_ScrapeJob(priority=5, sequence=2, urls=[], kwargs={}, result_queue=None, stream_id="a"))
    order = [q.get_nowait().stream_id for _ in range(3)]
    assert order == ["a", "b", "a"], f"Expected interleaving, got {order}"
    print("✅ Same-priority interleaving OK")

if __name__ == "__main__":
    test_config_defaults()
    test_stream_status()
    test_job_ordering()
    test_same_priority_interleaving()
    print("\n🎉 Phase 1 all tests passed!")
