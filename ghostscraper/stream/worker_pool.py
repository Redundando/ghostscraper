"""Worker pool for scrape_stream.

Manages a priority queue of _ScrapeJob items and a fixed number of worker
loops that spawn subprocesses to process each job.
"""

import asyncio
import inspect
import itertools
import json
import os
import sys
import tempfile
import time

from .models import _ScrapeJob
from ..config import ScraperDefaults

_SENTINEL = _ScrapeJob(priority=999999, sequence=999999, urls=[], kwargs={}, result_queue=None, stream_id="__shutdown__")


class _WorkerPool:
    _instance: "_WorkerPool | None" = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._queue: asyncio.PriorityQueue = None
        self._workers: list[asyncio.Task] = []
        self._sequence = itertools.count()
        self._stopping = False
        self._started = False
        self._cancelled_streams: set[str] = set()

    @classmethod
    def get_pool(cls) -> "_WorkerPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_started(self):
        if self._started:
            return
        self._queue = asyncio.PriorityQueue(maxsize=ScraperDefaults.MAX_QUEUE_SIZE)
        self._stopping = False
        self._cancelled_streams = set()
        for _ in range(ScraperDefaults.MAX_WORKERS):
            self._workers.append(asyncio.get_event_loop().create_task(self._worker_loop()))
        self._started = True

    async def submit(self, job: _ScrapeJob):
        self._ensure_started()
        await self._queue.put(job)

    def next_sequence(self) -> int:
        return next(self._sequence)

    def cancel_stream(self, stream_id: str):
        self._cancelled_streams.add(stream_id)
        # Drain queued jobs for this stream
        remaining = []
        while not self._queue.empty():
            try:
                job = self._queue.get_nowait()
                if job.stream_id != stream_id:
                    remaining.append(job)
            except asyncio.QueueEmpty:
                break
        for job in remaining:
            self._queue.put_nowait(job)

    def is_cancelled(self, stream_id: str) -> bool:
        return stream_id in self._cancelled_streams

    async def shutdown(self):
        self._stopping = True
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False
        _WorkerPool._instance = None

    async def _worker_loop(self):
        while not self._stopping:
            try:
                job = await self._queue.get()
            except asyncio.CancelledError:
                return

            if job.stream_id == "__shutdown__":  # sentinel for shutdown
                return

            if job.stream_id in self._cancelled_streams:
                self._queue.task_done()
                continue

            try:
                await self._run_subprocess(job)
            except Exception as e:
                # Report all URLs in the chunk as failed
                for url in job.urls:
                    await job.result_queue.put({
                        "type": "failed", "url": url,
                        "message": f"Subprocess crash: {e}",
                    })
            finally:
                self._queue.task_done()

    async def _run_subprocess(self, job: _ScrapeJob):
        config = {"urls": job.urls, **job.kwargs}

        fd, temp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(config, f)

            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "ghostscraper.stream", temp_path,
                stderr=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )

            reported_urls = set()

            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode().strip()
                if not text:
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type in ("completed", "failed"):
                    reported_urls.add(msg.get("url"))
                    await job.result_queue.put(msg)
                elif msg_type == "progress" and job.on_progress:
                    try:
                        if inspect.iscoroutinefunction(job.on_progress):
                            await job.on_progress(msg)
                        else:
                            job.on_progress(msg)
                    except Exception:
                        pass
                elif msg_type == "subprocess_done":
                    break

            await proc.wait()

            if proc.returncode != 0:
                for url in job.urls:
                    if url not in reported_urls:
                        await job.result_queue.put({
                            "type": "failed", "url": url,
                            "message": f"Subprocess exited with code {proc.returncode}",
                        })

        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
