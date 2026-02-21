# Ghostscraper

A Playwright-based web scraper with persistent caching, automatic browser installation, and multiple output formats.

## Changelog

### v0.3.0 (Latest)
- Added DynamoDB L2 cache support for cross-machine cache sharing
- Simplified logging to boolean (`logging=True/False`)
- Added `dynamodb_table` parameter to `GhostScraper` and `scrape_many()`

### v0.2.1
- Fixed RuntimeError when browser installation check runs within an active event loop
- Improved compatibility with Linux and other Unix-like systems

### v0.2.0
- Initial stable release

## Features

- **Headless Browser Scraping**: Uses Playwright for reliable scraping of JavaScript-heavy websites
- **Parallel Scraping**: Scrape multiple URLs concurrently with shared browser instances
- **Persistent Caching**: Stores scraped data between runs for improved performance
- **DynamoDB L2 Cache**: Optional cross-machine cache sharing via AWS DynamoDB
- **Automatic Browser Installation**: Self-installs required browsers
- **Multiple Output Formats**: HTML, Markdown, Plain Text, BeautifulSoup
- **Boolean Logging**: Enable/disable logging with `logging=True/False`
- **Error Handling**: Robust retry mechanism with exponential backoff
- **Asynchronous API**: Modern async/await interface
- **Type Hints**: Full type annotation support for better IDE integration

## Installation

```bash
pip install ghostscraper
```

## Basic Usage

### Simple Scraping

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    # Initialize the scraper
    scraper = GhostScraper(url="https://example.com")
    
    # Get the HTML content
    html = await scraper.html()
    print(html)
    
    # Get plain text content
    text = await scraper.text()
    print(text)
    
    # Get markdown version
    markdown = await scraper.markdown()
    print(markdown)

# Run the async function
asyncio.run(main())
```

### Batch Scraping (Parallel)

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    urls = [
        "https://example.com",
        "https://www.python.org",
        "https://github.com"
    ]
    
    # Scrape multiple URLs in parallel with a shared browser
    scrapers = await GhostScraper.scrape_many(
        urls=urls,
        max_concurrent=3,
        logging=True
    )
    
    # Access results from each scraper
    for scraper in scrapers:
        text = await scraper.text()
        print(f"{scraper.url}: {len(text)} characters")

asyncio.run(main())
```

### With Custom Options

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    # Initialize with custom options
    scraper = GhostScraper(
        url="https://example.com",
        browser_type="firefox",  # Use Firefox instead of default Chromium
        headless=False,          # Show the browser window
        load_timeout=60000,      # 60 seconds timeout
        clear_cache=True,        # Clear previous cache
        ttl=1,                   # Cache for 1 day
        logging=True             # Enable logging
    )
    
    # Get the HTML content
    html = await scraper.html()
    print(html)

asyncio.run(main())
```

### With DynamoDB Cache

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    # Single scraper with DynamoDB L2 cache
    scraper = GhostScraper(
        url="https://example.com",
        dynamodb_table="my-cache-table"  # Requires AWS credentials
    )
    html = await scraper.html()

    # Batch scraping with DynamoDB
    scrapers = await GhostScraper.scrape_many(
        urls=["https://example.com", "https://python.org"],
        dynamodb_table="my-cache-table"
    )

asyncio.run(main())
```

## API Reference

### GhostScraper

The main class for web scraping with persistent caching.

#### Constructor

```python
GhostScraper(
    url: str = "",
    clear_cache: bool = False,
    ttl: int = 999,
    markdown_options: Optional[Dict[str, Any]] = None,
    logging: bool = True,
    dynamodb_table: Optional[str] = None,
    **kwargs
)
```

**Parameters**:
- `url` (str): The URL to scrape.
- `clear_cache` (bool): Whether to clear existing cache on initialization.
- `ttl` (int): Time-to-live for cached data in days.
- `markdown_options` (Dict[str, Any]): Options for HTML to Markdown conversion.
- `logging` (bool): Enable/disable logging. Default: True.
- `dynamodb_table` (str): DynamoDB table name for cross-machine caching. Default: None.
- `**kwargs`: Additional options passed to PlaywrightScraper.

**Playwright Options (passed via kwargs)**:
- `browser_type` (str): Browser engine to use, one of "chromium", "firefox", or "webkit". Default: "chromium".
- `headless` (bool): Whether to run the browser in headless mode. Default: True.
- `browser_args` (Dict[str, Any]): Additional arguments to pass to the browser.
- `context_args` (Dict[str, Any]): Additional arguments to pass to the browser context.
- `max_retries` (int): Maximum number of retry attempts. Default: 3.
- `backoff_factor` (float): Factor for exponential backoff between retries. Default: 2.0.
- `network_idle_timeout` (int): Milliseconds to wait for network to be idle. Default: 10000 (10 seconds).
- `load_timeout` (int): Milliseconds to wait for page to load. Default: 30000 (30 seconds).
- `wait_for_selectors` (List[str]): CSS selectors to wait for before considering page loaded.

#### Methods

##### `async html() -> str`

Returns the raw HTML content of the page.

##### `async response_code() -> int`

Returns the HTTP response code from the page request.

##### `async markdown() -> str`

Returns the page content converted to Markdown.

##### `async article() -> newspaper.Article`

Returns a newspaper.Article object with parsed content.

##### `async text() -> str`

Returns the plain text content of the page.

##### `async authors() -> str`

Returns the detected authors of the content.

##### `async soup() -> BeautifulSoup`

Returns a BeautifulSoup object for the page.

##### `@classmethod async scrape_many(urls: List[str], max_concurrent: int = 5, logging: bool = True, **kwargs) -> List[GhostScraper]`

Scrape multiple URLs in parallel using a shared browser instance.

**Parameters**:
- `urls` (List[str]): List of URLs to scrape.
- `max_concurrent` (int): Maximum number of concurrent page loads. Default: 5.
- `logging` (bool): Enable/disable logging. Default: True.
- `**kwargs`: Additional options passed to GhostScraper and PlaywrightScraper.

**Returns**: List of GhostScraper instances with cached results.

### PlaywrightScraper

Low-level browser automation class used by GhostScraper.

#### Constructor

```python
PlaywrightScraper(
    url: str = "",
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    headless: bool = True,
    browser_args: Optional[Dict[str, Any]] = None,
    context_args: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    network_idle_timeout: int = 10000,
    load_timeout: int = 30000,
    wait_for_selectors: Optional[List[str]] = None,
    logging: bool = True
)
```

**Parameters**: Same as listed in GhostScraper kwargs above.

#### Methods

##### `async fetch() -> Tuple[str, int]`

Fetches the page and returns a tuple of (html_content, status_code).

##### `async fetch_url(url: str) -> Tuple[str, int]`

Fetches a specific URL using the shared browser instance.

##### `async fetch_many(urls: List[str], max_concurrent: int = 5) -> List[Tuple[str, int]]`

Fetches multiple URLs in parallel using a shared browser instance with concurrency control.

##### `async fetch_and_close() -> Tuple[str, int]`

Fetches the page, closes the browser, and returns a tuple of (html_content, status_code).

##### `async close() -> None`

Closes the browser and playwright resources.

##### `async check_and_install_browser() -> bool`

Checks if the required browser is installed, and installs it if not. Returns True if successful.

## Advanced Usage

### Configuring Global Defaults

```python
from ghostscraper import ScraperDefaults

# Modify defaults for all future scraper instances
ScraperDefaults.MAX_CONCURRENT = 20
ScraperDefaults.LOGGING = False
ScraperDefaults.HEADLESS = False
ScraperDefaults.LOAD_TIMEOUT = 30000
ScraperDefaults.DYNAMODB_TABLE = "my-cache-table"
```

### Batch Scraping with Options

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    urls = [f"https://example.com/page{i}" for i in range(1, 11)]
    
    # Scrape with custom options
    scrapers = await GhostScraper.scrape_many(
        urls=urls,
        max_concurrent=5,
        browser_type="chromium",
        headless=True,
        load_timeout=60000,
        ttl=7,  # Cache for 7 days
        logging=True
    )
    
    # Process results
    for scraper in scrapers:
        markdown = await scraper.markdown()
        print(f"Scraped {scraper.url}")

asyncio.run(main())
```

### Custom Browser Configurations

```python
from ghostscraper import GhostScraper

# Set up a browser with custom viewport size and user agent
browser_context_args = {
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

scraper = GhostScraper(
    url="https://example.com",
    context_args=browser_context_args
)
```

### Waiting for Dynamic Content

```python
from ghostscraper import GhostScraper

# Wait for specific elements to load before considering the page ready
scraper = GhostScraper(
    url="https://example.com/dynamic-page",
    wait_for_selectors=["#content", ".product-list", "button.load-more"]
)
```

### Custom Markdown Options

```python
from ghostscraper import GhostScraper

# Customize the markdown conversion
markdown_options = {
    "ignore_links": True,
    "ignore_images": True,
    "bullet_character": "*"
}

scraper = GhostScraper(
    url="https://example.com",
    markdown_options=markdown_options
)
```

### Browser Management

```python
from ghostscraper import check_browser_installed, install_browser
import asyncio

async def setup_browsers():
    # Check if browsers are installed
    chromium_installed = await check_browser_installed("chromium")
    firefox_installed = await check_browser_installed("firefox")
    
    # Install browsers if needed
    if not chromium_installed:
        install_browser("chromium")
    
    if not firefox_installed:
        install_browser("firefox")

asyncio.run(setup_browsers())
```

## Performance Considerations

- Use caching effectively by setting appropriate TTL values
- Use `scrape_many()` for batch scraping to share browser instances and reduce memory usage
- Adjust `max_concurrent` based on your system resources and target website rate limits
- Consider browser memory usage when scraping multiple pages
- For best performance, use "chromium" as it's generally the fastest engine
- Use `logging=False` for production to minimize overhead

## Error Handling

GhostScraper uses a progressive loading strategy:
1. First attempts with "networkidle" (most reliable)
2. Falls back to "load" event if timeout occurs
3. Finally tries "domcontentloaded" (fastest but least complete)

If all strategies fail, it will retry up to `max_retries` with exponential backoff.

## License

This project is licensed under the MIT License.

## Dependencies

- playwright
- beautifulsoup4
- html2text
- newspaper4k
- python-slugify
- logorator
- cacherator
- lxml_html_clean

## Contributing

Contributions are welcome! Visit the GitHub repository: https://github.com/Redundando/ghostscraper