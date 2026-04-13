"""Subprocess worker for scrape_stream.

Invoked as: python -m ghostscraper.stream <temp_file_path>

Reads a JSON config from the temp file, runs GhostScraper.scrape_many with
fail_fast=False, and emits JSON-lines to stderr for the parent to consume.
"""

import asyncio
import json
import sys
import time


def _emit(msg: dict):
    msg.setdefault("ts", time.time())
    sys.stderr.write(json.dumps(msg) + "\n")
    sys.stderr.flush()


async def worker_main(config_path: str):
    with open(config_path, "r") as f:
        config = json.load(f)

    urls = config.pop("urls")
    dynamodb_table = config.pop("dynamodb_table", None)
    max_concurrent = config.pop("max_concurrent", 15)

    # Strip GhostScraper-only keys that PlaywrightScraper doesn't accept
    _GHOST_ONLY = {"cache", "clear_cache", "ttl", "lazy", "markdown_options"}
    ghost_kwargs = {k: config.pop(k) for k in _GHOST_ONLY if k in config}
    # Remove keys that scrape_many accepts as explicit args to avoid duplicates
    _EXPLICIT = {"logging", "fail_fast", "max_concurrent", "on_scraped", "on_progress", "browser_restart_every"}
    for k in _EXPLICIT:
        config.pop(k, None)
    kwargs = config

    from ghostscraper import GhostScraper

    completed_urls = set()

    async def on_scraped(scraper):
        if scraper.error:
            _emit({"type": "failed", "url": scraper.url, "message": str(scraper.error)})
        else:
            _emit({"type": "completed", "url": scraper.url, "response_code": scraper._response_code})
        completed_urls.add(scraper.url)

    def on_progress(event: dict):
        _emit({"type": "progress", **event})

    # Always write to local cache so the parent can read results (IPC).
    # The user's cache=False preference is handled by the parent after reading.
    ghost_kwargs["cache"] = True
    ghost_kwargs.pop("clear_cache", None)

    await GhostScraper.scrape_many(
        urls=urls,
        max_concurrent=max_concurrent,
        logging=False,
        fail_fast=False,
        on_scraped=on_scraped,
        on_progress=on_progress,
        dynamodb_table=dynamodb_table,
        **ghost_kwargs,
        **kwargs,
    )

    # Emit failed for any URLs that weren't reported via on_scraped (edge case)
    for url in urls:
        if url not in completed_urls:
            _emit({"type": "failed", "url": url, "message": "URL not reported by scrape_many"})

    _emit({"type": "subprocess_done"})
