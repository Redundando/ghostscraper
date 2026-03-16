# Changelog

All notable changes to this project will be documented in this file.

## [0.9.2]

### Fixed
- **`create_stream` kwargs leak** — GhostScraper-specific kwargs (`cache`, `clear_cache`, `ttl`, `lazy`, `markdown_options`) passed to `create_stream` were forwarded unfiltered into the subprocess worker, which passed them straight to `PlaywrightScraper.__init__()`, causing a `TypeError`. The worker now strips these keys and passes them correctly to `GhostScraper` via `scrape_many`.
- **`scrape_many` kwargs leak** — same `cache` and `lazy` keys were also missing from the `playwright_kwargs` exclusion list in `scrape_many`, meaning calling `scrape_many(urls, cache=False)` directly would hit the same `TypeError`.

## [0.9.0]

### Added
- **ScrapeStream** — memory-safe streaming for large URL sets via subprocess isolation. Each chunk runs in a disposable child process; when it exits, the OS reclaims all Chromium memory.
  - `GhostScraper.create_stream(urls, ...)` — create a stream with priority queue, subprocess batching, and progress callbacks
  - `async for scraper in stream` — yields one `GhostScraper` at a time in completion order
  - `GhostScraper.get_stream_status(stream_id)` / `get_all_streams()` — monitor streams
  - `GhostScraper.cancel_stream(stream_id)` — graceful cancellation
  - `await GhostScraper.shutdown()` — drain queue and wait for running subprocesses
- **`ScrapeStream`** and **`StreamStatus`** exports from `ghostscraper`
- **`ScraperDefaults`** stream settings: `MAX_WORKERS`, `SUBPROCESS_BATCH_SIZE`, `MAX_QUEUE_SIZE`, `DEFAULT_PRIORITY`
- **`cache` parameter** on `GhostScraper` — set `cache=False` to disable all cache reads/writes
- **`lazy` parameter** on `GhostScraper` — skip cache restore on init (used internally by ScrapeStream)
- **`ScrapeCache`** class — lightweight cache backend with three modes: local JSON, DynamoDB (via dynamorator with compression), or disabled
- **`save_cache()`**, **`clear_cache_entry()`**, **`cache_stats()`**, **`cache_list_keys()`** — new cache methods on `GhostScraper`

### Changed
- **BREAKING**: Removed `cacherator` dependency. `GhostScraper` no longer inherits from `JSONCache`. Cache is now handled via composition with `ScrapeCache`.
- **Added `dynamorator`** as a dependency (was previously optional)
- Replaced all `asyncio.iscoroutinefunction()` calls with `inspect.iscoroutinefunction()` (deprecated in Python 3.16)

### Deprecated
- `json_cache_save()` → use `save_cache()`
- `json_cache_save_db()` → use `save_cache()`
- `json_cache_clear()` → use `clear_cache_entry()`
- `json_cache_stats()` → use `cache_stats()`
- `json_cache_list_db_keys()` → use `cache_list_keys()`

All deprecated methods still work and emit `DeprecationWarning`.

## [0.7.0]

### Added
- `GhostScraper.fetch_bytes(url)` classmethod — fetches a URL as raw bytes using the Playwright browser context (inherits UA, cookies, and headers). Useful for CDN-protected resources that block plain HTTP clients.
- `PlaywrightScraper.fetch_bytes(url)` — low-level counterpart with the same retry/backoff logic as `fetch_url`
- Optional caching via `cache=True`: bytes are base64-encoded and stored in a standalone cache file keyed to the resource URL. Supports `ttl`, `clear_cache`, and `dynamodb_table`.

## [0.6.1]

### Fixed
- `page_loaded` now fires for cached URLs in `scrape_many`; `completed`/`total` counts continue sequentially from live fetches

## [0.6.0]

### Added
- `fail_fast` parameter on `scrape_many()` — set to `False` to continue the batch on individual URL failures instead of raising; failed scrapers expose `scraper.error`, return `""` from `html()`, and `None` from `response_code()`
- `no_retry_on` parameter on `GhostScraper` and `scrape_many()` — skip retries for terminal status codes like 404
- `page_loaded` progress event now includes a `scraper` field in `scrape_many` batches for immediate per-URL processing
- `response_headers()`, `redirect_chain()`, and `final_url()` methods — all cached alongside HTML

## [0.5.0]

### Changed
- Simplified caching to single-backend model: local JSON by default, DynamoDB when `dynamodb_table` is set (never both simultaneously)

## [0.4.1]

### Added
- `load_strategies` parameter on `PlaywrightScraper` (and via `**kwargs` on `GhostScraper`/`scrape_many()`) to override the loading strategy chain
- `ScraperDefaults.LOAD_STRATEGIES` global default (default: `["load", "networkidle", "domcontentloaded"]`)

## [0.4.0]

### Added
- `on_progress` callback for real-time scraping progress events; supports both sync and async callables
- Callbacks fire at key events: browser ready, loading strategy, retries, page loaded, errors, and batch lifecycle

## [0.3.0]

### Added
- DynamoDB cache: `dynamodb_table` parameter on `GhostScraper` and `scrape_many()` for cross-machine cache sharing
- `ScraperDefaults.DYNAMODB_TABLE` global default

### Changed
- **BREAKING**: Replaced `log_level: LogLevel` with `logging: bool`

## [0.2.0]

### Added
- Three-level logging system with `log_level` parameter
- Type hints support with `py.typed` marker

### Changed
- **BREAKING**: Replaced `verbose: bool` with `log_level: LogLevel`

## [0.1.0]

### Added
- Parallel scraping with `scrape_many()`
- Shared browser instances for efficient batch scraping
- Configurable defaults via `ScraperDefaults`
- Progressive loading strategies: load → networkidle → domcontentloaded
- Retry logic with exponential backoff

## [0.0.3]

Initial release with basic scraping functionality.
