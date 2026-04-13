"""ScrapeStream — async iterator over scraped URLs with subprocess isolation."""

import asyncio
import inspect
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..config import ScraperDefaults
from ..scrape_cache import ScrapeCache
from .models import StreamStatus, _ScrapeJob
from .worker_pool import _WorkerPool


class ScrapeStream:
    _streams: Dict[str, "ScrapeStream"] = {}

    def __init__(
        self,
        urls: List[str],
        dynamodb_table: Optional[str] = None,
        stream_id: Optional[str] = None,
        priority: int = ScraperDefaults.DEFAULT_PRIORITY,
        subprocess_batch_size: int = ScraperDefaults.SUBPROCESS_BATCH_SIZE,
        max_concurrent: int = ScraperDefaults.MAX_CONCURRENT,
        on_progress: Optional[Callable] = None,
        **kwargs,
    ):
        self.stream_id = stream_id or str(uuid.uuid4())
        self._urls = urls
        self._dynamodb_table = dynamodb_table
        self._priority = priority
        self._subprocess_batch_size = subprocess_batch_size
        self._max_concurrent = max_concurrent
        self._on_progress = on_progress
        self._kwargs = kwargs

        self._total = len(urls)
        self._completed = 0
        self._failed = 0
        self._status = "running"
        self._cancelled = False

        self._cached_urls: List[str] = []
        self._uncached_urls: List[str] = []
        self._cache_checked = False

        ScrapeStream._streams[self.stream_id] = self

    @property
    def status(self) -> StreamStatus:
        return StreamStatus(
            stream_id=self.stream_id,
            total=self._total,
            completed=self._completed,
            failed=self._failed,
            pending=self._total - self._completed - self._failed,
            status=self._status,
        )

    def cancel(self):
        self._cancelled = True
        self._status = "cancelled"
        pool = _WorkerPool.get_pool()
        pool.cancel_stream(self.stream_id)

    async def _emit(self, payload: dict):
        if self._on_progress is None:
            return
        try:
            payload.setdefault("ts", time.time())
            if inspect.iscoroutinefunction(self._on_progress):
                await self._on_progress(payload)
            else:
                self._on_progress(payload)
        except Exception:
            pass

    def _check_cache(self):
        if self._cache_checked:
            return
        from slugify import slugify

        use_cache = self._kwargs.get("cache", True)
        clear_cache = self._kwargs.get("clear_cache", False)
        ttl = self._kwargs.get("ttl", ScraperDefaults.CACHE_TTL)

        for url in self._urls:
            if not use_cache or clear_cache:
                self._uncached_urls.append(url)
                continue
            sc = ScrapeCache(
                key=slugify(url),
                directory=ScraperDefaults.CACHE_DIRECTORY,
                ttl=ttl,
                dynamodb_table=self._dynamodb_table,
                logging=False,
            )
            if sc.exists():
                self._cached_urls.append(url)
            else:
                self._uncached_urls.append(url)
        self._cache_checked = True

    def __aiter__(self):
        return self._iterate().__aiter__()

    async def _iterate(self):
        from ..ghost_scraper import GhostScraper

        self._check_cache()

        await self._emit({
            "event": "stream_started",
            "stream_id": self.stream_id,
            "total": self._total,
            "to_fetch": len(self._uncached_urls),
            "cached": len(self._cached_urls),
        })

        # Yield cached URLs first
        for url in self._cached_urls:
            if self._cancelled:
                break
            scraper = GhostScraper(
                url=url,
                dynamodb_table=self._dynamodb_table,
                logging=False,
                lazy=True,
                **{k: v for k, v in self._kwargs.items()
                   if k in ("ttl",)},
            )
            self._completed += 1
            await self._emit({
                "event": "url_completed",
                "stream_id": self.stream_id,
                "url": url,
                "status_code": scraper._response_code,
                "completed": self._completed,
                "total": self._total,
            })
            yield scraper

        if self._cancelled:
            await self._finish_cancelled()
            return

        # Submit uncached chunks and yield results
        chunks = [
            self._uncached_urls[i:i + self._subprocess_batch_size]
            for i in range(0, len(self._uncached_urls), self._subprocess_batch_size)
        ]

        pool = _WorkerPool.get_pool()
        result_queue = asyncio.Queue()

        # Build kwargs for the subprocess
        sub_kwargs = {
            "dynamodb_table": self._dynamodb_table,
            "max_concurrent": self._max_concurrent,
        }
        for k, v in self._kwargs.items():
            if k not in ("on_progress",):
                sub_kwargs[k] = v

        for chunk_index, chunk in enumerate(chunks):
            if self._cancelled:
                break

            await self._emit({
                "event": "chunk_started",
                "stream_id": self.stream_id,
                "chunk_index": chunk_index,
                "chunk_size": len(chunk),
            })

            job = _ScrapeJob(
                priority=self._priority,
                sequence=pool.next_sequence(),
                urls=chunk,
                kwargs=sub_kwargs,
                result_queue=result_queue,
                stream_id=self.stream_id,
                on_progress=self._on_progress,
            )
            await pool.submit(job)

            # Wait for all URLs in this chunk
            received = 0
            while received < len(chunk):
                if self._cancelled:
                    break
                msg = await result_queue.get()
                received += 1

                url = msg["url"]
                if msg["type"] == "completed":
                    scraper = GhostScraper(
                        url=url,
                        dynamodb_table=self._dynamodb_table,
                        logging=False,
                        lazy=True,
                        **{k: v for k, v in self._kwargs.items()
                           if k in ("ttl",)},
                    )
                    self._completed += 1
                else:
                    scraper = GhostScraper(url=url, logging=False)
                    scraper.error = Exception(msg.get("message", "Unknown error"))
                    self._failed += 1

                await self._emit({
                    "event": "url_completed",
                    "stream_id": self.stream_id,
                    "url": url,
                    "status_code": scraper._response_code,
                    "completed": self._completed + self._failed,
                    "total": self._total,
                })
                yield scraper

            await self._emit({
                "event": "chunk_done",
                "stream_id": self.stream_id,
                "chunk_index": chunk_index,
                "chunk_size": len(chunk),
            })

        if self._cancelled:
            await self._finish_cancelled()
        else:
            self._status = "completed"
            await self._emit({
                "event": "stream_done",
                "stream_id": self.stream_id,
                "total": self._total,
                "failed": self._failed,
            })
            ScrapeStream._streams.pop(self.stream_id, None)

    async def _finish_cancelled(self):
        remaining = self._total - self._completed - self._failed
        await self._emit({
            "event": "stream_cancelled",
            "stream_id": self.stream_id,
            "completed": self._completed,
            "remaining": remaining,
        })
        ScrapeStream._streams.pop(self.stream_id, None)
