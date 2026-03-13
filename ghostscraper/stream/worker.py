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

    # Remaining keys are forwarded to GhostScraper / PlaywrightScraper
    kwargs = config

    from ghostscraper import GhostScraper

    completed_urls = set()

    async def on_scraped(scraper):
        if scraper.error:
            _emit({"type": "failed", "url": scraper.url, "message": str(scraper.error)})
        else:
            _emit({"type": "completed", "url": scraper.url})
        completed_urls.add(scraper.url)

    def on_progress(event: dict):
        _emit({"type": "progress", **event})

    await GhostScraper.scrape_many(
        urls=urls,
        max_concurrent=max_concurrent,
        logging=False,
        fail_fast=False,
        on_scraped=on_scraped,
        on_progress=on_progress,
        dynamodb_table=dynamodb_table,
        **kwargs,
    )

    # Emit failed for any URLs that weren't reported via on_scraped (edge case)
    for url in urls:
        if url not in completed_urls:
            _emit({"type": "failed", "url": url, "message": "URL not reported by scrape_many"})

    _emit({"type": "subprocess_done"})
