# Ghostscraper

A Playwright-based web scraper with persistent caching, automatic browser installation, and multiple output formats.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## Overview

GhostScraper wraps Playwright with persistent JSON caching (via `cacherator.JSONCache`), retry logic, and multiple output formats. The primary interface is `GhostScraper`. `PlaywrightScraper` is the lower-level browser automation layer used internally.

All scraping methods are async. Results (`html`, `response_code`, `response_headers`, `redirect_chain`) are cached to disk on first fetch and restored on subsequent instantiation with the same URL. Derived outputs (`markdown`, `text`, `authors`, `soup`, `seo`, `article`) are computed in-memory from the cached HTML and are not persisted.

## Installation

```bash
pip install ghostscraper
```

## GhostScraper

### Constructor

```python
GhostScraper(
    url: str = "",
    clear_cache: bool = False,
    ttl: int = 999,
    markdown_options: Optional[Dict[str, Any]] = None,
    logging: bool = True,
    dynamodb_table: Optional[str] = None,
    on_progress: Optional[Callable] = None,
    **kwargs  # passed to PlaywrightScraper
)
```

**Parameters**:
- `url`: The URL to scrape.
- `clear_cache`: Clear existing cache on initialization. Default: `False`.
- `ttl`: Cache time-to-live in days. Default: `999`.
- `markdown_options`: Options forwarded to `html2text.HTML2Text` for Markdown conversion.
- `logging`: Enable/disable logging. Default: `True`.
- `dynamodb_table`: DynamoDB table name for cross-machine caching. Replaces local cache when set. Default: `None`.
- `on_progress`: Callback fired at key scraping events. Accepts sync and async callables. Default: `None`.
- `**kwargs`: Forwarded to `PlaywrightScraper` (see below).

**PlaywrightScraper kwargs**:
- `browser_type`: `"chromium"` | `"firefox"` | `"webkit"`. Default: `"chromium"`.
- `headless`: Run browser headlessly. Default: `True`.
- `browser_args`: Extra args passed to `browser.launch()`.
- `context_args`: Extra args passed to `browser.new_context()`.
- `max_retries`: Retry attempts per URL. Default: `3`.
- `backoff_factor`: Exponential backoff multiplier. Default: `2.0`.
- `network_idle_timeout`: Timeout in ms for the `networkidle` strategy. Default: `3000`.
- `load_timeout`: Timeout in ms for all other strategies. Default: `20000`.
- `wait_for_selectors`: CSS selectors to wait for after page load.
- `load_strategies`: Loading strategy chain. Default: `["load", "networkidle", "domcontentloaded"]`.
- `no_retry_on`: Status codes that abort retries immediately (e.g. `[404, 410]`). Default: `None`.

### Instance Attributes

- `url` (str): The URL this scraper was initialized with.
- `error` (Exception | None): Set when a fetch fails under `fail_fast=False` in `scrape_many`. When set, `html()` returns `""` and `response_code()` returns `None`.

### Methods

All methods trigger a fetch (or cache restore) on first call. Subsequent calls return the cached/computed value.

#### `async html() -> str`
Raw HTML of the page. Returns `""` if `self.error` is set.

#### `async response_code() -> Optional[int]`
HTTP status code. Returns `None` if `self.error` is set.

#### `async response_headers() -> dict`
HTTP response headers from the final response. Cached alongside HTML.

#### `async redirect_chain() -> list`
Full list of responses during navigation. Each entry: `{"url": str, "status": int}`. Cached alongside HTML.

```python
[
    {"url": "https://example.com/old", "status": 301},
    {"url": "https://example.com/new", "status": 200},
]
```

#### `async final_url() -> str`
URL of the last entry in `redirect_chain()`. Falls back to `self.url` if chain is empty.

#### `async markdown() -> str`
Page content converted to Markdown via `html2text`. Respects `markdown_options`.

#### `async text() -> str`
Plain text extracted via `newspaper4k`.

#### `async authors() -> list`
Authors detected by `newspaper4k`.

#### `async article() -> newspaper.Article`
Full `newspaper.Article` object with parsed content.

#### `async soup() -> BeautifulSoup`
`BeautifulSoup` object parsed from the HTML.

#### `async seo() -> dict`
SEO metadata parsed from the HTML. All keys are omitted if the corresponding tag is absent.

```python
{
    "title": str,           # <title>
    "description": str,     # <meta name="description">
    "canonical": str,       # <link rel="canonical">
    "robots": {             # <meta name="robots"> — directives as keys
        "noindex": True,
        "nofollow": True,
    },
    "googlebot": { ... },   # <meta name="googlebot">, same shape as robots
    "og": {                 # <meta property="og:*"> keyed by suffix
        "title": str,
        "description": str,
        "image": str,
        "url": str,
    },
    "twitter": { ... },     # <meta name="twitter:*">, same pattern
    "hreflang": {           # <link rel="alternate" hreflang="..."> — values are lists
        "en-us": ["https://..."],
        "de": ["https://..."],
    }
}
```

#### `@classmethod async fetch_bytes(url, cache=False, clear_cache=False, ttl=999, dynamodb_table=None, logging=True, **kwargs) -> Tuple[bytes, int, dict]`

Fetch a URL as raw bytes using the Playwright browser context (inherits UA, cookies, and headers). Useful for CDN-protected resources that block plain HTTP clients.

**Parameters**:
- `url`: URL to fetch.
- `cache`: Persist result to disk/DynamoDB. Default: `False`.
- `clear_cache`: Force re-fetch even if cached. Default: `False`.
- `ttl`: Cache TTL in days. Default: `999`.
- `dynamodb_table`: DynamoDB table for cross-machine caching. Default: `None`.
- `logging`: Enable logging. Default: `True`.
- `**kwargs`: Forwarded to `PlaywrightScraper` (`max_retries`, `browser_type`, `no_retry_on`, etc.).

**Returns**: `Tuple[bytes, int, dict]` — `(body, status_code, headers)`

#### `@classmethod async scrape_many(urls, max_concurrent=15, logging=True, fail_fast=True, **kwargs) -> List[GhostScraper]`

Scrape multiple URLs in parallel using a single shared browser instance.

**Parameters**:
- `urls`: List of URLs to scrape.
- `max_concurrent`: Max concurrent page loads. Default: `15`.
- `logging`: Enable logging. Default: `True`.
- `fail_fast`: If `True`, any unhandled exception aborts the entire batch. If `False`, failed scrapers have `scraper.error` set, `html()` returns `""`, `response_code()` returns `None`. Default: `True`.
- `on_progress`: Progress callback (sync or async). Default: `None`.
- `**kwargs`: Forwarded to `GhostScraper` and `PlaywrightScraper`.

**Returns**: `List[GhostScraper]` in the same order as `urls`. Already-cached URLs are skipped.

## Caching

- Cached fields: `_html`, `_response_code`, `_response_headers`, `_redirect_chain`.
- Cache key: slugified URL.
- Cache location: `data/ghostscraper/` (configurable via `ScraperDefaults.CACHE_DIRECTORY`).
- DynamoDB cache replaces local cache when `dynamodb_table` is set. Requires AWS credentials.
- `clear_cache=True` forces a fresh fetch and overwrites the cache.

## Loading Strategies

GhostScraper tries Playwright loading strategies in order, falling back on timeout:

1. `load` — waits for the `load` event. Works for most sites.
2. `networkidle` — waits until no network activity for 500ms. Better for JS-heavy pages. Uses `network_idle_timeout`.
3. `domcontentloaded` — waits only for HTML parsing. Fastest, least complete.

If all strategies fail, the attempt is retried up to `max_retries` times with exponential backoff (`backoff_factor ** attempt` seconds).

Override the chain via `load_strategies`:

```python
scrapers = await GhostScraper.scrape_many(urls=urls, load_strategies=["domcontentloaded"])

# Or globally:
from ghostscraper import ScraperDefaults
ScraperDefaults.LOAD_STRATEGIES = ["domcontentloaded"]
```

## Progress Callbacks

Pass `on_progress` to receive real-time events. Accepts sync and async callables.

```python
scraper = GhostScraper(url="https://example.com", on_progress=lambda e: print(e["event"]))
```

Each event is a dict with `event` (str) and `ts` (Unix timestamp). Additional fields:

| event | extra fields | notes |
|---|---|---|
| `started` | `url` | fired before fetch begins |
| `browser_installing` | `browser` | first-run only; sync callback only |
| `browser_ready` | `browser` | browser check passed |
| `loading_strategy` | `url`, `strategy`, `attempt`, `max_retries`, `timeout` | fired per strategy attempt |
| `retry` | `url`, `attempt`, `max_retries` + optional `reason`, `status_code` | only fires when another attempt follows |
| `page_loaded` | `url`, `completed`, `total`, `status_code`, `scraper` | fires on success or error status; `scraper` only in `scrape_many`; fires for cached URLs too |
| `error` | `url`, `message` | unhandled exception during fetch |
| `batch_started` | `total`, `to_fetch`, `cached` | `scrape_many` only |
| `batch_done` | `total` | `scrape_many` only |

## ScraperDefaults

Global defaults, modifiable at runtime before instantiation:

```python
from ghostscraper import ScraperDefaults

ScraperDefaults.BROWSER_TYPE = "chromium"       # default browser
ScraperDefaults.HEADLESS = True
ScraperDefaults.LOAD_TIMEOUT = 20000            # ms
ScraperDefaults.NETWORK_IDLE_TIMEOUT = 3000     # ms
ScraperDefaults.LOAD_STRATEGIES = ["load", "networkidle", "domcontentloaded"]
ScraperDefaults.MAX_RETRIES = 3
ScraperDefaults.BACKOFF_FACTOR = 2.0
ScraperDefaults.MAX_CONCURRENT = 15
ScraperDefaults.CACHE_TTL = 999                 # days
ScraperDefaults.CACHE_DIRECTORY = "data/ghostscraper"
ScraperDefaults.DYNAMODB_TABLE = None
ScraperDefaults.LOGGING = True
```

## PlaywrightScraper

Low-level browser automation used internally by `GhostScraper`. Use directly only if you need raw browser control.

### Constructor

```python
PlaywrightScraper(
    url: str = "",
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    headless: bool = True,
    browser_args: Optional[Dict[str, Any]] = None,
    context_args: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    network_idle_timeout: int = 3000,
    load_timeout: int = 20000,
    wait_for_selectors: Optional[List[str]] = None,
    logging: bool = True,
    on_progress: Optional[Callable] = None,
    load_strategies: Optional[List[str]] = None,
    no_retry_on: Optional[List[int]] = None
)
```

### Methods

#### `async fetch() -> Tuple[str, int, dict, list]`
Fetch `self.url`. Returns `(html, status_code, headers, redirect_chain)`.

#### `async fetch_url(url: str) -> Tuple[str, int, dict, list]`
Fetch a specific URL using the shared browser instance.

#### `async fetch_many(urls: List[str], max_concurrent: int = 5) -> List[Tuple[str, int, dict, list]]`
Fetch multiple URLs in parallel.

#### `async fetch_and_close() -> Tuple[str, int, dict, list]`
Fetch and immediately close the browser.

#### `async close() -> None`
Close browser and release Playwright resources.

#### `async check_and_install_browser() -> bool`
Check if the configured browser is installed; install it if not. Result is cached per process.

Supports async context manager (`async with PlaywrightScraper(...) as browser`).

## Browser Installation Utilities

```python
from ghostscraper import check_browser_installed, install_browser

installed = await check_browser_installed("chromium")  # bool
install_browser("chromium")                            # sync, runs playwright install
```

## Usage Examples

### Single URL

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    scraper = GhostScraper(url="https://example.com")
    html = await scraper.html()
    text = await scraper.text()
    markdown = await scraper.markdown()
    code = await scraper.response_code()
    headers = await scraper.response_headers()
    seo = await scraper.seo()

asyncio.run(main())
```

### Batch Scraping

```python
scrapers = await GhostScraper.scrape_many(
    urls=["https://example.com", "https://python.org"],
    max_concurrent=5,
    ttl=7,
    load_strategies=["domcontentloaded"],
)
for scraper in scrapers:
    print(await scraper.text())
```

### Partial Failure Handling

```python
scrapers = await GhostScraper.scrape_many(urls=urls, fail_fast=False)
for s in scrapers:
    if s.error:
        print(f"FAILED {s.url}: {s.error}")
    else:
        print(f"OK {s.url}: {await s.response_code()}")
```

### Redirect Chain

```python
scraper = GhostScraper(url="https://example.com/redirect")
print(await scraper.final_url())
for hop in await scraper.redirect_chain():
    print(hop["status"], hop["url"])
```

### Fetch Raw Bytes (CDN-protected resources)

```python
body, status_code, headers = await GhostScraper.fetch_bytes(
    "https://example.com/image.jpg",
    cache=True,
)
```

### Skip Retries on Terminal Status Codes

```python
scraper = GhostScraper(url="https://example.com/missing", no_retry_on=[404, 410, 403])
print(await scraper.response_code())
```

### DynamoDB Cache

```python
scraper = GhostScraper(url="https://example.com", dynamodb_table="my-cache-table")
scrapers = await GhostScraper.scrape_many(urls=urls, dynamodb_table="my-cache-table")
```

### Custom Browser Context

```python
scraper = GhostScraper(
    url="https://example.com",
    context_args={"viewport": {"width": 1920, "height": 1080}, "user_agent": "..."},
    wait_for_selectors=["#content", ".product-list"],
)
```

## Dependencies

- playwright
- beautifulsoup4
- html2text
- newspaper4k
- python-slugify
- logorator
- cacherator
- lxml_html_clean

## License

MIT. Contributions welcome: https://github.com/Redundando/ghostscraper
