"""GhostScraper - A Playwright-based web scraper with persistent caching.

GhostScraper provides an easy-to-use interface for scraping JavaScript-heavy
websites with automatic caching, parallel scraping, and multiple output formats.

Example:
    >>> import asyncio
    >>> from ghostscraper import GhostScraper
    >>> 
    >>> async def main():
    ...     scraper = GhostScraper(url="https://example.com")
    ...     html = await scraper.html()
    ...     text = await scraper.text()
    >>> 
    >>> asyncio.run(main())
"""

from .playwright_scraper import PlaywrightScraper
from .ghost_scraper import GhostScraper
from .playwright_installer import check_browser_installed, install_browser
from .config import ScraperDefaults

__version__ = "0.6.0"
__all__ = [
    "GhostScraper",
    "PlaywrightScraper",
    "ScraperDefaults",
    "check_browser_installed",
    "install_browser",
]