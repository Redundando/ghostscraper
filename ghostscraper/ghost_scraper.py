"""GhostScraper - Main scraping class with persistent caching.

This module provides the GhostScraper class, which combines Playwright-based
web scraping with persistent JSON caching for efficient data retrieval.
"""

from logorator import Logger
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from cacherator import Cached, JSONCache
from slugify import slugify

from .playwright_scraper import PlaywrightScraper
from .config import ScraperDefaults, LogLevel
import html2text
import newspaper
import asyncio

class GhostScraper(JSONCache):
    """A web scraper with persistent caching and multiple output formats.
    
    GhostScraper uses Playwright for reliable JavaScript-heavy website scraping
    and caches results to disk for improved performance across runs.
    
    Attributes:
        url (str): The URL to scrape.
        log_level (LogLevel): Logging verbosity - "none", "normal", or "verbose".
    
    Example:
        >>> scraper = GhostScraper(url="https://example.com")
        >>> html = await scraper.html()
        >>> text = await scraper.text()
    """
    
    def __init__(self, url="", clear_cache=False, ttl=ScraperDefaults.CACHE_TTL, 
                 markdown_options: Optional[Dict[str, Any]] = None, log_level: LogLevel = ScraperDefaults.LOG_LEVEL, **kwargs):
        """Initialize a GhostScraper instance.
        
        Args:
            url (str): The URL to scrape. Defaults to empty string.
            clear_cache (bool): Whether to clear existing cache. Defaults to False.
            ttl (int): Time-to-live for cached data in days. Defaults to 999.
            markdown_options (Dict[str, Any], optional): Options for HTML to Markdown conversion.
            log_level (LogLevel): Logging level - "none", "normal", or "verbose". Defaults to "normal".
            **kwargs: Additional options passed to PlaywrightScraper (browser_type, headless, etc.).
        """
        self._text: str|None = None
        self._authors: str|None = None
        self._article: newspaper.Article | None = None
        self.url = url
        self._html: str | None = None
        self._soup: BeautifulSoup | None = None
        self._markdown: str | None = None
        self._response_code: int | None = None
        self.kwargs = kwargs
        self.log_level = log_level
        self._markdown_options = markdown_options or {}

        JSONCache.__init__(self, data_id=f"{slugify(self.url)}", directory=ScraperDefaults.CACHE_DIRECTORY, 
                          clear_cache=clear_cache, ttl=ttl, logging=(log_level == "verbose"))

    def __str__(self):
        return f"{self.url}"

    def __repr__(self):
        return self.__str__()

    @property
    @Cached()
    def _playwright_scraper(self):
        """Lazy-loaded Playwright scraper instance."""
        return PlaywrightScraper(url=self.url, **self.kwargs)

    @Logger(override_function_name="Fetching URL via Playwright")
    async def _fetch_response(self):
        """Internal method to fetch response from Playwright scraper."""
        return await self._playwright_scraper.fetch_and_close()

    async def get_response(self):
        """Get the cached or fetched response containing HTML and status code.
        
        Returns:
            dict: Dictionary with 'html' and 'response_code' keys.
        """
        if self._response_code is None or self._html is None:
            if self.log_level in ["normal", "verbose"]:
                Logger.note(f"📥 Cache miss: {self.url[:60]}... - Fetching from web")
            (self._html, self._response_code) = await self._fetch_response()
        return {"html": self._html, "response_code": self._response_code}

    async def html(self) -> str:
        """Get the raw HTML content of the page.
        
        Returns:
            str: The HTML content as a string.
        """
        return (await self.get_response())["html"]

    async def response_code(self) -> int:
        """Get the HTTP response status code.
        
        Returns:
            int: HTTP status code (e.g., 200, 404, 500).
        """
        return (await self.get_response())["response_code"]

    async def markdown(self) -> str:
        """Convert the HTML content to Markdown format.
        
        Returns:
            str: The page content as Markdown.
        """
        if self._markdown is None:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.body_width = 0
            h.ignore_images = False
            self._markdown = h.handle(await self.html())
        return self._markdown

    async def article(self) -> newspaper.Article:
        """Parse the page as a newspaper article.
        
        Returns:
            newspaper.Article: Parsed article object with text, authors, etc.
        """
        if self._article is None:
            article = newspaper.Article(self.url)
            article.download(input_html=await self.html())
            article.parse()
            self._article = article
        return self._article

    async def text(self) -> str:
        """Extract plain text content from the page.
        
        Returns:
            str: The plain text content.
        """
        if self._text is None:
            self._text = (await self.article()).text
        return self._text

    async def authors(self) -> str:
        """Extract detected authors from the page.
        
        Returns:
            str: The detected authors.
        """
        if self._authors is None:
            self._authors = (await self.article()).authors
        return self._authors


    async def soup(self) -> BeautifulSoup:
        """Get a BeautifulSoup object for HTML parsing.
        
        Returns:
            BeautifulSoup: Parsed HTML as a BeautifulSoup object.
        """
        if self._soup is None:
            self._soup = BeautifulSoup(await self.html(), "html.parser")
        return self._soup

    @classmethod
    async def scrape_many(cls, urls: List[str], max_concurrent: int = ScraperDefaults.MAX_CONCURRENT, 
                         log_level: LogLevel = ScraperDefaults.LOG_LEVEL, **kwargs) -> List['GhostScraper']:
        """Scrape multiple URLs in parallel using a shared browser instance.
        
        This method efficiently scrapes multiple URLs by sharing a single browser
        instance and controlling concurrency. Results are cached immediately as
        they complete.
        
        Args:
            urls (List[str]): List of URLs to scrape.
            max_concurrent (int): Maximum number of concurrent page loads. Defaults to 15.
            log_level (LogLevel): Logging level - "none", "normal", or "verbose". Defaults to "normal".
            **kwargs: Additional arguments passed to PlaywrightScraper (browser_type, headless, etc.).
            
        Returns:
            List[GhostScraper]: List of GhostScraper instances with cached results.
            
        Example:
            >>> urls = ["https://example.com", "https://python.org"]
            >>> scrapers = await GhostScraper.scrape_many(urls, max_concurrent=5)
            >>> for scraper in scrapers:
            ...     text = await scraper.text()
        """
        if log_level in ["normal", "verbose"]:
            Logger.note(f"\n🚀 Starting batch scrape: {len(urls)} URLs | Concurrency: {max_concurrent}")
        
        # Create scraper instances
        scrapers = [cls(url=url, log_level=log_level, **kwargs) for url in urls]
        
        # Separate cached and non-cached scrapers
        scrapers_to_fetch = []
        cached_count = 0
        for scraper in scrapers:
            if scraper._html is None or scraper._response_code is None:
                scrapers_to_fetch.append(scraper)
            else:
                cached_count += 1
        
        if log_level in ["normal", "verbose"]:
            Logger.note(f"💾 Cache status: {cached_count} cached | {len(scrapers_to_fetch)} to fetch")
        
        # Fetch and save each URL as it completes
        if scrapers_to_fetch:
            if log_level in ["normal", "verbose"]:
                Logger.note(f"🌐 Fetching {len(scrapers_to_fetch)} URLs from web...")
            
            async with PlaywrightScraper(log_level=log_level, **kwargs) as browser:
                semaphore = asyncio.Semaphore(max_concurrent)
                
                async def fetch_and_save(scraper: 'GhostScraper'):
                    async with semaphore:
                        html, status_code = await browser.fetch_url(scraper.url)
                        scraper._html = html
                        scraper._response_code = status_code
                        scraper.json_cache_save()  # Immediate write to disk
                        if log_level == "verbose":
                            Logger.note(f"💾 Saved: {scraper.url[:60]}...")
                        return scraper
                
                await asyncio.gather(*[fetch_and_save(s) for s in scrapers_to_fetch], return_exceptions=True)
        else:
            if log_level in ["normal", "verbose"]:
                Logger.note(f"✅ All URLs found in cache - No fetching needed")
        
        if log_level in ["normal", "verbose"]:
            Logger.note(f"✓ Batch scrape completed: {len(urls)} URLs processed\n")
        return scrapers
