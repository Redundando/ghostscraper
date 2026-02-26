# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0]

### Added
- `fail_fast` parameter on `scrape_many()` — set to `False` to continue the batch on individual URL failures instead of raising; failed scrapers expose `scraper.error`, return `""` from `html()`, and `None` from `response_code()`
- `no_retry_on` parameter on `GhostScraper` and `scrape_many()` — skip retries for terminal status codes like 404
- `page_loaded` progress event now includes a `scraper` field in `scrape_many` batches for immediate per-URL processing
- `response_headers()`, `redirect_chain()`, and `final_url()` methods — all cached alongside HTML

## [0.5.0]

### Changed
- Simplified caching to single-backend model: local JSON by default, DynamoDB when `dynamodb_table` is set (never both simultaneously)

## [0.4.0]

### Added
- `on_progress` callback for real-time scraping progress events; supports both sync and async callables
- Callbacks fire at key events: browser ready, loading strategy, retries, page loaded, errors, and batch lifecycle

## [0.4.1]

### Added
- `load_strategies` parameter on `PlaywrightScraper` (and via `**kwargs` on `GhostScraper`/`scrape_many()`) to override the loading strategy chain
- `ScraperDefaults.LOAD_STRATEGIES` global default (default: `["load", "networkidle", "domcontentloaded"]`)

## [0.3.0] - 2026-02-21

### Added
- **DynamoDB L2 cache**: `dynamodb_table` parameter on `GhostScraper` and `scrape_many()` for cross-machine cache sharing
- **`ScraperDefaults.DYNAMODB_TABLE`**: Global default for DynamoDB table name

### Changed
- **BREAKING**: Replaced `log_level: LogLevel` ("none"/"normal"/"verbose") with `logging: bool` (True/False)
- `ScraperDefaults.LOG_LEVEL` renamed to `ScraperDefaults.LOGGING`

### Migration Guide
- Replace `log_level="none"` with `logging=False`
- Replace `log_level="normal"` or `log_level="verbose"` with `logging=True`
- Replace `ScraperDefaults.LOG_LEVEL` with `ScraperDefaults.LOGGING`

## [0.2.0] - 2025-02-12

### Added
- **Three-level logging system**: `log_level` parameter with options "none", "normal", "verbose"
- **Type hints support**: Added `py.typed` marker for better IDE integration
- **JSONCache logging control**: Passes logging preference to parent cache class

### Changed
- **BREAKING**: Replaced `verbose: bool` parameter with `log_level: LogLevel` ("none" | "normal" | "verbose")
- Default logging is now "normal" (shows progress without verbose details)
- Cache operations respect log_level setting

### Migration Guide
- Replace `verbose=True` with `log_level="normal"` or `log_level="verbose"`
- Replace `verbose=False` with `log_level="none"`

## [0.1.0] - 2025-02-12

### Added
- **Parallel scraping** with `scrape_many()` class method
- **Shared browser instances** for efficient batch scraping
- **Immediate cache writes** using `json_cache_save()` for crash resistance
- **Configurable defaults** via `ScraperDefaults` class
- **Verbose mode control** for cleaner logging
- **Optimized loading strategies** - tries 'load' first instead of 'networkidle'
- **Better default timeouts** - reduced from 10s/30s to 3s/20s
- **Increased default concurrency** - from 5 to 15 parallel requests
- Progress logging with emojis for better UX
- Multiple example files demonstrating different use cases

### Changed
- Loading strategy order: now tries 'load' → 'networkidle' → 'domcontentloaded'
- Default `network_idle_timeout`: 10000ms → 3000ms
- Default `load_timeout`: 30000ms → 20000ms
- Default `max_concurrent`: 5 → 15
- Reduced cache hit logging noise

### Fixed
- Cache persistence in batch mode - now saves immediately after each fetch
- Memory efficiency with shared browser contexts

## [0.0.3] - Previous Release

Initial release with basic scraping functionality.
