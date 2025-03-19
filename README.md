# GhostScraper

GhostScraper is an asynchronous web scraping library built on top of Playwright that makes it easy to fetch and convert web content to Markdown format. It handles browser management, retries, and provides a clean interface for working with web content.

## Features

- Asynchronous web scraping with Playwright
- HTML to Markdown conversion
- Built-in retry mechanism with exponential backoff
- Result caching using JSONCache
- Smart content extraction
- Support for multiple browser types (Chromium, Firefox, WebKit)

## Installation

```bash
pip install ghostscraper
```

GhostScraper will automatically install and manage required browsers during the first run.

## Basic Usage

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    # Create a scraper instance
    scraper = GhostScraper(url="https://example.com")
    
    # Get the HTML content
    html = await scraper.html()
    
    # Get the Markdown converted content
    markdown = await scraper.markdown()
    
    # Get the response code
    status_code = await scraper.response_code()
    
    print(f"Status code: {status_code}")
    print(f"Markdown content:\n{markdown}")

# Run the async function
asyncio.run(main())
```

## API Reference

### GhostScraper

The main class for scraping and converting web content.

#### Constructor

```python
GhostScraper(
    url: str = "",
    clear_cache: bool = False,
    markdown_options: Optional[Dict[str, Any]] = None,
    **kwargs
)
```

- `url`: The URL to scrape
- `clear_cache`: Whether to clear the cache before scraping
- `markdown_options`: Options for the Markdown converter
- `**kwargs`: Additional arguments passed to the PlaywrightScraper

#### Methods

- `async html() -> str`: Get the HTML content of the URL
- `async response_code() -> int`: Get the HTTP response code
- `async markdown() -> str`: Get the content converted to Markdown
- `async soup() -> BeautifulSoup`: Get a BeautifulSoup object for the HTML content

### **kwargs Keywords

The GhostScraper constructor accepts any keyword arguments and passes them directly to the underlying PlaywrightScraper. This allows you to customize the browser behavior without directly interacting with the PlaywrightScraper class.

```python
# GhostScraper accepts all these keyword arguments which are passed to PlaywrightScraper
scraper = GhostScraper(
    url="https://example.com",
    browser_type="chromium",     # Browser to use: "chromium", "firefox", or "webkit"
    headless=True,               # Run browser in headless mode
    browser_args={},             # Arguments for browser launcher
    context_args={},             # Arguments for browser context
    max_retries=3,               # Maximum retry attempts
    backoff_factor=2.0,          # Exponential backoff factor
    network_idle_timeout=10000,  # Network idle timeout (ms)
    load_timeout=30000,          # Page load timeout (ms)
    wait_for_selectors=[]        # CSS selectors to wait for
)
```

These keyword arguments configure how the page is loaded, browser behavior, and retry mechanisms.

## Advanced Usage

### Custom Markdown Options

```python
from ghostscraper import GhostScraper

# Configure the Markdown converter
markdown_options = {
    "strip_tags": ["script", "style", "nav", "footer", "header", "aside"],
    "keep_tags": ["article", "main", "div", "section", "p"],
    "content_selectors": ["article", "main", ".content", "#content"],
    "preserve_images": True,
    "preserve_links": True,
    "preserve_tables": True,
    "include_title": True,
    "compact_output": False
}

# Create a scraper with custom Markdown options
scraper = GhostScraper(
    url="https://example.com",
    markdown_options=markdown_options
)
```

### Custom Browser Configuration

```python
from ghostscraper import GhostScraper

# Create a scraper with custom browser settings
scraper = GhostScraper(
    url="https://example.com",
    # Browser configuration options (passed to PlaywrightScraper)
    browser_type="firefox",                         # Use Firefox instead of Chromium
    headless=False,                                 # Show the browser window
    max_retries=5,                                  # Increase retry attempts
    load_timeout=60000,                             # Increase load timeout to 60 seconds
    wait_for_selectors=[".content", ".main-article"] # Wait for these selectors
)

# You can also pass browser-specific arguments
scraper = GhostScraper(
    url="https://example.com",
    browser_args={
        "proxy": {                                  # Set up a proxy
            "server": "http://myproxy.com:8080",
            "username": "user",
            "password": "pass"
        },
        "slowMo": 50,                               # Slow down browser operations by 50ms
    },
    context_args={
        "userAgent": "Custom User Agent",           # Set custom user agent
        "viewport": {"width": 1920, "height": 1080} # Set viewport size
    }
)
```

### Progressive Loading Strategy

GhostScraper uses a progressive loading strategy that tries different methods to load the page:

1. First tries with `networkidle` - waits until network is idle
2. If that fails, tries with `load` - waits for the load event
3. If that fails, tries with `domcontentloaded` - waits for DOM content loaded

This ensures maximum compatibility with different websites.

### Browser Installation

GhostScraper automatically checks if the required browser is installed and installs it if needed:

```python
# Install browsers manually if needed
from ghostscraper import install_browser

# Install a specific browser type
install_browser("chromium")
install_browser("firefox")
install_browser("webkit")
```

### Using Caching

By default, GhostScraper caches results in the `data/ghostscraper` directory. To clear the cache:

```python
# Clear cache for a specific URL
scraper = GhostScraper(url="https://example.com", clear_cache=True)
```

## License

MIT