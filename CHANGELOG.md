# Changelog

All notable changes to this project will be documented in this file.

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
