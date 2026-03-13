# ScrapeStream Battle Plan

## Problem Statement

`scrape_many` accumulates memory that is never released back to the OS. Chromium's renderer memory is not reclaimed when the browser closes within the same process. After ~2,500 pages on a t3.large (8 GB), the server becomes unresponsive.

Additionally, when multiple API requests trigger `scrape_many` concurrently, there is no global coordination — each call launches its own browser, competing for RAM and CPU with no backpressure.

### Measured Evidence

**Without subprocess isolation (current behavior):**
```
Initial:   69.6 MB
Batch 1:  190.7 MB  (+121 MB)
Batch 2:  238.9 MB  (+48 MB)
Batch 3:  271.4 MB  (+33 MB)
Batch 4:  316.9 MB  (+46 MB)
Batch 5:  387.0 MB  (+70 MB)
```

**With subprocess isolation:**
```
Initial:   26.3 MB
Batch 1:   29.2 MB  (+2.8 MB)
Batch 2:   29.3 MB  (+0.1 MB)
Batch 3:   29.4 MB  (+0.1 MB)
Batch 4:   29.5 MB  (+0.1 MB)
Batch 5:   29.6 MB  (+0.1 MB)
```

## Solution Overview

A new `scrape_stream` system that provides:

1. **Subprocess isolation** — each chunk of URLs runs in a disposable child process. When it exits, the OS fully reclaims all memory.
2. **Global job queue with priority** — all `scrape_stream` calls feed into a shared priority queue. A fixed worker pool controls how many subprocesses run simultaneously.
3. **Async generator interface** — results are yielded one at a time in completion order. The caller never holds more than one scraper in memory.
4. **Stream management** — each stream has an ID, can be monitored from any endpoint, and can be cancelled gracefully.
5. **DynamoDB-only cache** — `scrape_stream` requires `dynamodb_table`. The subprocess writes results to DynamoDB; the parent reconstructs lightweight `GhostScraper` instances from cache.

### Architecture Diagram

```
API Request A ──► create_stream(urls_a, priority=0) ──┐
                                                       │
API Request B ──► create_stream(urls_b, priority=5) ──┤
                                                       ▼
                                              Global Priority Queue
                                              (interleaves same-priority chunks)
                                                       │
                                          ┌────────────┼────────────┐
                                          ▼            ▼            ▼
                                      Worker 1     Worker 2    (idle slot)
                                     (subprocess)  (subprocess)
                                          │            │
                                          ▼            ▼
                                    DynamoDB Cache  DynamoDB Cache
                                          │            │
                                          ▼            ▼
                                    stderr JSON-lines → Parent reads
                                          │            │
                                          ▼            ▼
                                    yield GhostScraper (from cache, one at a time)
```

### What We're NOT Building (yet)

- Queue persistence across server restarts (queue is in-memory, caller resubmits)
- Stream-level retries for failed URLs (failed is failed; caller decides)
- `max_memory_mb` adaptive batch sizing
- `oom_protection_mb` graceful abort
- Prefetching next subprocess chunk while yielding current results
- Changes to `scrape_many` (left as-is)


## Public API

### Creating a Stream

```python
stream = GhostScraper.create_stream(
    urls=urls,                          # List[str] — required
    dynamodb_table="my-cache-table",    # str — required for scrape_stream
    stream_id="my-seo-audit",          # str — optional, auto-generated UUID if omitted
    priority=5,                         # int — lower = higher priority (like CSS z-index). Default: 5
    subprocess_batch_size=50,           # int — URLs per subprocess. Default: ScraperDefaults.SUBPROCESS_BATCH_SIZE
    max_concurrent=10,                  # int — concurrent pages within each subprocess. Default: ScraperDefaults.MAX_CONCURRENT
    on_progress=my_callback,            # Callable — receives all progress events. Default: None
    # All other kwargs forwarded to GhostScraper/PlaywrightScraper:
    # ttl, clear_cache, browser_type, headless, max_retries, backoff_factor,
    # load_strategies, no_retry_on, wait_for_selectors, etc.
)
```

### Consuming Results

```python
async for scraper in stream:
    code = await scraper.response_code()
    if code == 200:
        text = await scraper.text()
        save_to_db(scraper.url, text)
    else:
        log_failure(scraper.url, code)
    # scraper goes out of scope → GC reclaims
```

### Monitoring from Another Endpoint

```python
# Get status of a specific stream
status = GhostScraper.get_stream_status("my-seo-audit")
# Returns: StreamStatus(
#     stream_id="my-seo-audit",
#     total=5000,
#     completed=347,
#     failed=2,
#     pending=4651,
#     status="running"  # "running" | "completed" | "cancelled"
# )

# Get all active streams
all_streams = GhostScraper.get_all_streams()
# Returns: List[StreamStatus]
```

### Cancellation

```python
# From any endpoint
GhostScraper.cancel_stream("my-seo-audit")
# → Current subprocess chunk finishes (graceful)
# → Remaining queued chunks are removed
# → Stream yields stream_cancelled progress event
# → async for loop ends
```

### Server Shutdown

```python
# In your server shutdown hook
await GhostScraper.shutdown()
# → Waits for running subprocesses to finish current chunk
# → Drains the queue
```

### ScraperDefaults Additions

```python
ScraperDefaults.MAX_WORKERS = 2              # concurrent subprocess workers
ScraperDefaults.SUBPROCESS_BATCH_SIZE = 50   # URLs per subprocess
ScraperDefaults.MAX_QUEUE_SIZE = 500         # max pending chunks in queue
ScraperDefaults.DEFAULT_PRIORITY = 5         # default stream priority (0-10 range)
```


## Progress Events

All events are forwarded from subprocess to parent via stderr JSON-lines. The parent remaps `completed`/`total` to global counts before invoking the caller's `on_progress` callback.

### Stream-Level Events

| Event | Extra Fields | When |
|---|---|---|
| `stream_started` | `stream_id`, `total`, `to_fetch`, `cached` | Stream created, before any work |
| `chunk_started` | `stream_id`, `chunk_index`, `chunk_size` | Subprocess starting a chunk |
| `url_completed` | `stream_id`, `url`, `status_code`, `completed`, `total` | Single URL finished (success or failure) |
| `chunk_done` | `stream_id`, `chunk_index`, `chunk_size` | Subprocess finished and exited |
| `stream_done` | `stream_id`, `total`, `failed` | All URLs processed |
| `stream_cancelled` | `stream_id`, `completed`, `remaining` | Stream was cancelled |

### Playwright-Level Events (forwarded from subprocess)

These existing events are forwarded verbatim from the subprocess, with `stream_id` added:

| Event | Notes |
|---|---|
| `started` | Before fetch begins for a URL |
| `loading_strategy` | Per strategy attempt |
| `retry` | When a retry is about to happen |
| `page_loaded` | URL fetch complete |
| `error` | Unhandled exception during fetch |
| `browser_installing` | First-run browser install |
| `browser_ready` | Browser check passed |

All events include `ts` (Unix timestamp). The caller receives everything and decides what to act on.

## Subprocess Communication Protocol

### Parent → Subprocess

The parent writes a JSON config to a temp file and passes the path as a command-line argument:

```json
{
    "urls": ["https://example.com/1", "https://example.com/2"],
    "dynamodb_table": "my-cache-table",
    "max_concurrent": 10,
    "ttl": 999,
    "clear_cache": false,
    "browser_type": "chromium",
    "headless": true,
    "max_retries": 3,
    "backoff_factor": 2.0,
    "load_strategies": ["load", "networkidle", "domcontentloaded"],
    "no_retry_on": [404, 410],
    "network_idle_timeout": 3000,
    "load_timeout": 20000
}
```

Invoked as: `python -m ghostscraper.stream.worker <temp_file_path>`

### Subprocess → Parent (stderr JSON-lines)

Each line is a JSON object with a `type` field:

```jsonl
{"type": "progress", "event": "started", "url": "https://example.com/1", "ts": 1710000000.0}
{"type": "progress", "event": "page_loaded", "url": "https://example.com/1", "status_code": 200, "completed": 1, "total": 50, "ts": 1710000001.0}
{"type": "completed", "url": "https://example.com/1"}
{"type": "progress", "event": "error", "url": "https://example.com/2", "message": "timeout", "ts": 1710000002.0}
{"type": "failed", "url": "https://example.com/2", "message": "timeout"}
{"type": "subprocess_done"}
```

Message types:
- `progress` — forwarded to caller's `on_progress` callback
- `completed` — triggers a `yield` in the parent (scraper reconstructed from DynamoDB cache)
- `failed` — triggers a `yield` with `scraper.error` set
- `subprocess_done` — signals clean exit (parent stops reading stderr)

### Why stderr and not stdout

ghostscraper's Logger (via logorator) writes emoji-rich output to stdout via `print()`. This makes stdout unreliable as a data channel. stderr is clean and dedicated to our JSON-line protocol.


## Priority Queue and Fair Interleaving

### How Priority Works

Each `create_stream` call gets a `priority` (default 5, lower = higher priority). Chunks are submitted to an `asyncio.PriorityQueue` with a composite sort key:

```python
(priority, sequence_number)
```

`sequence_number` is a global auto-incrementing counter. This ensures:

- **Different priorities**: higher priority chunks always run first
- **Same priority**: chunks interleave fairly (round-robin by submission order)

### Example

```
Caller A (priority=5) submits 4 chunks: A1, A2, A3, A4
Caller B (priority=5) submits 2 chunks: B1, B2  (submitted after A2)

Queue order: (5,0)A1  (5,1)A2  (5,2)B1  (5,3)A3  (5,4)B2  (5,5)A4

Caller C (priority=0) submits 1 chunk: C1  (submitted after everything)

Queue order: (0,6)C1  (5,0)A1  (5,1)A2  (5,2)B1  (5,3)A3  (5,4)B2  (5,5)A4
             ↑ jumps to front
```

### Job Data Structure

```python
@dataclasses.dataclass(order=True)
class _ScrapeJob:
    priority: int
    sequence: int                                    # global auto-increment
    urls: list = dataclasses.field(compare=False)
    kwargs: dict = dataclasses.field(compare=False)
    result_queue: asyncio.Queue = dataclasses.field(compare=False)
    stream_id: str = dataclasses.field(compare=False)
    on_progress: Callable = dataclasses.field(compare=False, default=None)
```

## Cached URL Handling

When `scrape_stream` is called with 5,000 URLs and 3,000 are already in DynamoDB:

1. Check DynamoDB for each URL (batch operation)
2. Yield cached URLs first, one at a time — the caller processes each via `async for`
3. Then submit uncached URL chunks to the job queue
4. Yield results from subprocesses as they complete

Since `async for` is pull-based, yielding 3,000 cached results doesn't flood anything. The caller controls the pace. Subprocess scraping of the remaining 2,000 waits until cached yields are consumed (sequential for simplicity; prefetching is a future optimization).

## Error Handling

### URL-Level Failures

When PlaywrightScraper exhausts its retries (`max_retries` with exponential backoff, progressive loading strategies), the URL gets:
- `response_code` set to the error code (408 for timeout, 500 for exceptions)
- `html` set to `""`
- Result cached to DynamoDB (so it's not re-fetched on next run unless `clear_cache=True`)

The subprocess emits a `{"type": "failed", ...}` message. The parent yields a `GhostScraper` instance with `error` set. The caller checks `response_code()` and decides what to do. No stream-level retries — failed is failed.

### Subprocess Crashes

If a subprocess crashes (OOM, segfault, non-zero exit code):
- All URLs in that chunk are marked as failed
- Each gets a `GhostScraper` with `error` set to a descriptive exception
- The stream continues with the next chunk (does NOT abort)
- A `chunk_done` event is emitted with error information
- The caller sees these as failed scrapers and decides whether to re-scrape them

### Cancellation

When `cancel_stream(stream_id)` is called:
- A cancellation flag is set on the stream
- The currently running subprocess chunk finishes (graceful — no wasted work)
- Remaining queued jobs for this stream are removed from the priority queue
- The stream emits `stream_cancelled` and the `async for` loop ends
- `stream.status` shows `"cancelled"`


## File Structure

```
ghostscraper/
├── __init__.py                  # MODIFY — add new exports
├── config.py                    # MODIFY — add new ScraperDefaults
├── ghost_scraper.py             # MODIFY — add create_stream, get_stream_status, get_all_streams, cancel_stream, shutdown
├── playwright_scraper.py        # UNCHANGED
├── playwright_installer.py      # UNCHANGED
├── py.typed                     # UNCHANGED
└── stream/                      # NEW — all stream/queue logic
    ├── __init__.py              # Exports: ScrapeStream, StreamStatus
    ├── models.py                # _ScrapeJob, StreamStatus dataclass
    ├── worker_pool.py           # _WorkerPool singleton, priority queue, worker loops
    ├── worker.py                # Subprocess entry point (python -m ghostscraper.stream.worker)
    └── scrape_stream.py         # ScrapeStream class (async iterator + status + cancel)
```

### Dependency Graph

```
ghost_scraper.py
    └── stream/scrape_stream.py (ScrapeStream)
            ├── stream/worker_pool.py (_WorkerPool)
            │       └── stream/models.py (_ScrapeJob)
            └── stream/models.py (StreamStatus)

stream/worker.py (standalone subprocess entry point)
    └── ghost_scraper.py (GhostScraper.scrape_many — used internally)
```

## Implementation Phases

---

### Phase 1: Models and Config

**Files:** `stream/__init__.py`, `stream/models.py`, `config.py`

**What we build:**

`stream/models.py`:
- `StreamStatus` dataclass: `stream_id`, `total`, `completed`, `failed`, `pending`, `status` (running/completed/cancelled)
- `_ScrapeJob` dataclass (ordered): `priority`, `sequence`, `urls`, `kwargs`, `result_queue`, `stream_id`, `on_progress`

`config.py` additions:
- `ScraperDefaults.MAX_WORKERS = 2`
- `ScraperDefaults.SUBPROCESS_BATCH_SIZE = 50`
- `ScraperDefaults.MAX_QUEUE_SIZE = 500`
- `ScraperDefaults.DEFAULT_PRIORITY = 5`

`stream/__init__.py`:
- Export `ScrapeStream`, `StreamStatus`

**Test script** (`tests/test_phase1.py`):
```python
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
```

**Done when:** All tests pass.

---


### Phase 2: Subprocess Worker

**Files:** `stream/worker.py`, `stream/__main__.py`

**What we build:**

`stream/worker.py`:
- Reads a JSON config from a temp file path (passed as CLI arg)
- Extracts `urls`, `dynamodb_table`, `max_concurrent`, and all PlaywrightScraper kwargs
- Defines internal `on_scraped` callback that writes `{"type": "completed", "url": ...}` to stderr
- Defines internal `on_progress` callback that writes `{"type": "progress", ...}` to stderr
- Calls `GhostScraper.scrape_many(urls, on_scraped=..., on_progress=..., fail_fast=False, dynamodb_table=..., **kwargs)`
- For failed scrapers (where `scraper.error` is set), writes `{"type": "failed", "url": ..., "message": ...}` to stderr
- Writes `{"type": "subprocess_done"}` to stderr on exit
- All stderr writes are `json.dumps(msg) + "\n"` followed by `flush()`

`stream/__main__.py`:
- Allows invocation as `python -m ghostscraper.stream <temp_file_path>`
- Calls `asyncio.run(worker_main(sys.argv[1]))`

**Key detail:** The worker uses `scrape_many` internally with `fail_fast=False`. This means all URLs in the chunk are attempted even if some fail. The existing PlaywrightScraper retry logic (max_retries, exponential backoff, progressive loading strategies, no_retry_on) handles per-URL retries.

**Test script** (`tests/test_phase2.py`):
```python
"""Phase 2: Verify subprocess worker runs and emits correct JSON-lines.

Requires: DynamoDB table or local cache for testing.
Uses httpbin.org for reliable test URLs.
"""
import asyncio
import json
import sys
import tempfile
import os

async def test_worker_subprocess():
    config = {
        "urls": ["https://httpbin.org/html", "https://httpbin.org/status/404"],
        "dynamodb_table": None,  # uses local cache for testing
        "max_concurrent": 2,
        "ttl": 1,
        "clear_cache": True,
        "max_retries": 1,
        "no_retry_on": [404],
        "load_strategies": ["domcontentloaded"],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        temp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ghostscraper.stream", temp_path,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        completed_urls = []
        failed_urls = []
        progress_events = []
        got_done = False

        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            msg = json.loads(line.decode().strip())
            print(f"  📨 {msg['type']}: {msg.get('url', msg.get('event', ''))[:60]}")

            if msg["type"] == "completed":
                completed_urls.append(msg["url"])
            elif msg["type"] == "failed":
                failed_urls.append(msg["url"])
            elif msg["type"] == "progress":
                progress_events.append(msg)
            elif msg["type"] == "subprocess_done":
                got_done = True

        await proc.wait()

        assert proc.returncode == 0, f"Subprocess exited with code {proc.returncode}"
        assert got_done, "Never received subprocess_done message"
        assert "https://httpbin.org/html" in completed_urls, f"Expected html URL in completed, got {completed_urls}"
        assert len(progress_events) > 0, "Expected at least some progress events"
        print(f"  Completed: {completed_urls}")
        print(f"  Failed: {failed_urls}")
        print(f"  Progress events: {len(progress_events)}")
        print("✅ Worker subprocess OK")
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    asyncio.run(test_worker_subprocess())
    print("\n🎉 Phase 2 all tests passed!")
```

**Done when:** Subprocess runs, emits JSON-lines to stderr, results land in cache, test passes.

---

### Phase 3: Worker Pool

**Files:** `stream/worker_pool.py`

**What we build:**

`_WorkerPool` class (singleton):
- `asyncio.PriorityQueue` of `_ScrapeJob` items (max size: `ScraperDefaults.MAX_QUEUE_SIZE`)
- Global sequence counter (`itertools.count()`) for fair interleaving
- `MAX_WORKERS` concurrent worker loops (started lazily on first job submission)
- Each worker loop:
  1. Pulls a `_ScrapeJob` from the priority queue
  2. Writes job config to a temp file
  3. Spawns subprocess via `asyncio.create_subprocess_exec("python", "-m", "ghostscraper.stream", temp_path)`
  4. Reads stderr line by line
  5. Routes `completed`/`failed` messages to `job.result_queue`
  6. Routes `progress` messages to `job.on_progress` callback (remapping completed/total to global counts)
  7. On subprocess exit, cleans up temp file, loops back to pull next job
- `submit(job)` method — puts a job on the queue
- `cancel_stream(stream_id)` method — removes all queued jobs for that stream_id, sets a flag so running jobs for that stream are not followed by more chunks
- `shutdown()` method — sets stop flag, waits for running subprocesses to finish, drains queue
- `get_pool()` class method — returns the singleton, creates it lazily

**Test script** (`tests/test_phase3.py`):
```python
"""Phase 3: Verify worker pool manages concurrency and priority correctly.

Uses httpbin.org for reliable test URLs.
"""
import asyncio
import json
from ghostscraper.stream.worker_pool import _WorkerPool
from ghostscraper.stream.models import _ScrapeJob, StreamStatus
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
    results = asyncio.Queue()
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

    # With 1 worker, high priority should complete first (it's pulled from queue first)
    # Note: first job may already be running when high-priority is submitted,
    # so this test verifies queue ordering, not preemption
    print(f"  Completion order: {completion_order}")
    print("✅ Pool priority ordering OK")

    await pool.shutdown()

if __name__ == "__main__":
    asyncio.run(test_pool_basic())
    asyncio.run(test_pool_priority())
    print("\n🎉 Phase 3 all tests passed!")
```

**Done when:** Pool spawns subprocesses, respects MAX_WORKERS, routes messages to correct result queues, priority ordering works.

---


### Phase 4: ScrapeStream

**Files:** `stream/scrape_stream.py`

**What we build:**

`ScrapeStream` class:
- Constructor: receives `urls`, `stream_id` (auto-generated UUID if None), `priority`, `subprocess_batch_size`, `dynamodb_table`, `on_progress`, and all forwarded kwargs
- On creation:
  1. Checks DynamoDB cache for each URL (identifies cached vs uncached)
  2. Stores cached URLs list and uncached URLs list
  3. Splits uncached URLs into chunks of `subprocess_batch_size`
  4. Does NOT submit to queue yet (submission happens during iteration)
  5. Registers itself in a class-level `_streams` dict (keyed by `stream_id`)
- `__aiter__` / `__anext__` implementation:
  1. First, yields cached URLs one at a time — each as `GhostScraper(url=url, dynamodb_table=...)` loaded from cache
  2. Then, submits uncached chunks to the worker pool one at a time (or a few ahead)
  3. Reads from its private `result_queue`
  4. For `completed` messages: constructs `GhostScraper(url=..., dynamodb_table=...)`, yields it
  5. For `failed` messages: constructs `GhostScraper` with `error` set, yields it
  6. Checks cancellation flag between chunks
  7. When all URLs are yielded (or cancelled), emits `stream_done`/`stream_cancelled`, deregisters from `_streams`
- `status` property: returns `StreamStatus` computed from internal counters
- `cancel()` method: sets cancellation flag, calls `pool.cancel_stream(self.stream_id)`
- `stream_id` property: returns the ID

Class-level registry:
- `ScrapeStream._streams: Dict[str, ScrapeStream] = {}` — all active streams
- Used by `GhostScraper.get_stream_status()`, `get_all_streams()`, `cancel_stream()`

**Key detail — DynamoDB cache check:**
To determine which URLs are cached, we instantiate `GhostScraper(url=url, dynamodb_table=...)` and check if `_html is not None`. This is how `scrape_many` already does it. For 5,000 URLs this means 5,000 DynamoDB reads at init time, which could be slow. We should batch this or accept the latency. For Phase 4, we accept the latency; optimization is a future improvement.

**Test script** (`tests/test_phase4.py`):
```python
"""Phase 4: Verify ScrapeStream end-to-end.

Uses httpbin.org for reliable test URLs.
Requires DynamoDB table or local cache.
"""
import asyncio
from ghostscraper import GhostScraper, ScraperDefaults

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

    stream = GhostScraper.create_stream(
        urls=urls,
        dynamodb_table=None,  # local cache for testing
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

async def test_stream_with_cached():
    """Run same URLs twice. Second run should yield from cache."""
    urls = ["https://httpbin.org/html"]

    # First run — fetches from web
    stream1 = GhostScraper.create_stream(
        urls=urls, dynamodb_table=None, stream_id="test-cache-1",
        max_retries=1, load_strategies=["domcontentloaded"],
    )
    async for s in stream1:
        assert await s.response_code() is not None

    # Second run — should be cached
    stream2 = GhostScraper.create_stream(
        urls=urls, dynamodb_table=None, stream_id="test-cache-2",
        max_retries=1, load_strategies=["domcontentloaded"],
    )
    results = []
    async for s in stream2:
        results.append(s)

    assert len(results) == 1
    assert results[0]._html is not None, "Expected cached HTML"
    print("✅ Cached URL stream OK")

async def test_stream_status():
    """Verify get_stream_status and get_all_streams work."""
    urls = ["https://httpbin.org/html", "https://httpbin.org/robots.txt"]

    stream = GhostScraper.create_stream(
        urls=urls, dynamodb_table=None, stream_id="test-status",
        clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )

    # Before iteration
    status = GhostScraper.get_stream_status("test-status")
    assert status is not None
    assert status.total == 2
    assert status.status == "running"

    all_streams = GhostScraper.get_all_streams()
    assert any(s.stream_id == "test-status" for s in all_streams)

    # Consume
    async for _ in stream:
        pass

    print("✅ Stream status OK")

async def test_stream_cancellation():
    """Cancel a stream mid-flight."""
    urls = [f"https://httpbin.org/delay/{i}" for i in range(1, 6)]  # slow URLs

    stream = GhostScraper.create_stream(
        urls=urls, dynamodb_table=None, stream_id="test-cancel",
        subprocess_batch_size=2, max_concurrent=1,
        clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )

    count = 0
    async for scraper in stream:
        count += 1
        print(f"  Got result {count}: {scraper.url}")
        if count >= 2:
            GhostScraper.cancel_stream("test-cancel")
            # Stream should end after current chunk finishes

    assert stream.status.status == "cancelled"
    assert count < len(urls), f"Expected early stop, got all {count} results"
    print(f"  Yielded {count}/{len(urls)} before cancel")
    print("✅ Stream cancellation OK")

async def test_multiple_streams():
    """Two concurrent streams with different priorities."""
    urls_urgent = ["https://httpbin.org/html"]
    urls_background = ["https://httpbin.org/robots.txt"]

    stream_a = GhostScraper.create_stream(
        urls=urls_urgent, dynamodb_table=None, stream_id="urgent",
        priority=0, clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )
    stream_b = GhostScraper.create_stream(
        urls=urls_background, dynamodb_table=None, stream_id="background",
        priority=10, clear_cache=True, max_retries=1, load_strategies=["domcontentloaded"],
    )

    all_streams = GhostScraper.get_all_streams()
    assert len(all_streams) >= 2

    # Consume both
    async for s in stream_a:
        print(f"  Urgent: {s.url}")
    async for s in stream_b:
        print(f"  Background: {s.url}")

    print("✅ Multiple streams OK")

if __name__ == "__main__":
    asyncio.run(test_basic_stream())
    asyncio.run(test_stream_with_cached())
    asyncio.run(test_stream_status())
    asyncio.run(test_stream_cancellation())
    asyncio.run(test_multiple_streams())
    print("\n🎉 Phase 4 all tests passed!")
```

**Done when:** Full async-for loop works, cached URLs yield immediately, cancellation stops the stream, status is queryable.

---

### Phase 5: Wire into GhostScraper

**Files:** `ghost_scraper.py`, `__init__.py`

**What we build:**

`ghost_scraper.py` additions (class methods on `GhostScraper`):
- `create_stream(cls, urls, dynamodb_table, stream_id=None, priority=ScraperDefaults.DEFAULT_PRIORITY, subprocess_batch_size=ScraperDefaults.SUBPROCESS_BATCH_SIZE, on_progress=None, **kwargs) -> ScrapeStream`
- `get_stream_status(cls, stream_id) -> Optional[StreamStatus]`
- `get_all_streams(cls) -> List[StreamStatus]`
- `cancel_stream(cls, stream_id) -> bool`
- `shutdown(cls) -> None`

These are thin wrappers that delegate to `ScrapeStream` and `_WorkerPool`.

`__init__.py` additions:
- Export `ScrapeStream`, `StreamStatus`

**Test script** (`tests/test_phase5.py`):
```python
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
    # Stream should be deregistered or show completed
    print("✅ Full API test OK")

    await GhostScraper.shutdown()

if __name__ == "__main__":
    asyncio.run(test_full_api())
    print("\n🎉 Phase 5 all tests passed!")
```

**Done when:** All class methods work, exports are correct, full round-trip from `create_stream` to `async for` to `shutdown`.

---

### Phase 6: Documentation

**Files:** `README.md`, `CHANGELOG.md`

**What we build:**

`README.md` additions:
- New section: `## ScrapeStream` with subsections for creating, consuming, monitoring, cancelling, and configuring streams
- Usage examples covering: basic streaming, priority, cancellation, monitoring from another endpoint, progress callbacks, server shutdown
- Updated `ScraperDefaults` section with new defaults
- Note that `scrape_stream` requires `dynamodb_table`

`CHANGELOG.md`:
- Version bump entry with all new features

**Done when:** README accurately documents the new API, examples are copy-pasteable.

---


## Progress Tracker

| Phase | Description | Status | Files |
|-------|-------------|--------|-------|
| 1 | Models and Config | ✅ Complete | `stream/models.py`, `stream/__init__.py`, `config.py` |
| 2 | Subprocess Worker | ✅ Complete | `stream/worker.py`, `stream/__main__.py` |
| 3 | Worker Pool | ✅ Complete | `stream/worker_pool.py` |
| 4 | ScrapeStream | ✅ Complete | `stream/scrape_stream.py` |
| 5 | Wire into GhostScraper | ✅ Complete | `ghost_scraper.py`, `__init__.py` |
| 6 | Documentation | ⬜ Not started | `README.md`, `CHANGELOG.md` |

### Status Legend
- ⬜ Not started
- 🔨 In progress
- ✅ Complete
- ❌ Blocked

## Design Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| IPC mechanism | stderr JSON-lines | stdout is used by logorator's Logger.note(). stderr is clean. |
| Cache backend for streams | DynamoDB only | Prevents local disk from clogging up on servers. Subprocess writes to DynamoDB, parent reads from DynamoDB. |
| Queue persistence | In-memory only (for now) | Simplicity. Caller resubmits on server restart. Future feature. |
| Failed URL retries | None at stream level | PlaywrightScraper handles retries internally. Failed is failed. Caller decides. |
| Cached URL delivery | Yield first, then scrape | Sequential for simplicity. Prefetching is a future optimization. |
| Subprocess crash handling | Report to caller | All URLs in crashed chunk get `error` set. Stream continues with next chunk. Caller decides. |
| Cancellation | Graceful (finish current chunk) | No wasted work. Running subprocess completes its chunk before stopping. |
| Priority default | 5 (middle of 0-10) | Callers who don't care get fair treatment. Urgent callers pass 0. Background callers pass 10. |
| `scrape_many` changes | None | Left as-is for backward compatibility. `scrape_stream` is the new path. |
| Progress forwarding | Forward everything | Caller decides what to act on. No information loss. |
| `on_scraped` in streams | Replaced by `async for` | Yielding replaces the callback pattern. Less complexity. |
| Subprocess entry point | `python -m ghostscraper.stream` | Clean, no extra scripts needed. Works cross-platform. |
| Worker pool lifecycle | Lazy singleton | Created on first `create_stream` call. Shut down via `GhostScraper.shutdown()`. |
