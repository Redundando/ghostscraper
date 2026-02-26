"""GhostScraper - Main scraping class with persistent caching.

This module provides the GhostScraper class, which combines Playwright-based
web scraping with persistent JSON caching for efficient data retrieval.
"""

from logorator import Logger
from typing import Any, Callable, Dict, List, Optional

from bs4 import BeautifulSoup
from cacherator import Cached, JSONCache
from slugify import slugify

from .playwright_scraper import PlaywrightScraper
from .config import ScraperDefaults
import html2text
import newspaper
import asyncio
import time

class GhostScraper(JSONCache):
    """A web scraper with persistent caching and multiple output formats.
    
    GhostScraper uses Playwright for reliable JavaScript-heavy website scraping
    and caches results to disk for improved performance across runs.
    
    Attributes:
        url (str): The URL to scrape.
        logging (bool): Enable/disable logging.
    
    Example:
        >>> scraper = GhostScraper(url="https://example.com")
        >>> html = await scraper.html()
        >>> text = await scraper.text()
    """
    
    def __init__(self, url="", clear_cache=False, ttl=ScraperDefaults.CACHE_TTL, 
                 markdown_options: Optional[Dict[str, Any]] = None, logging: bool = ScraperDefaults.LOGGING, 
                 dynamodb_table: Optional[str] = ScraperDefaults.DYNAMODB_TABLE,
                 on_progress: Optional[Callable] = None, **kwargs):
        """Initialize a GhostScraper instance.
        
        Args:
            url (str): The URL to scrape. Defaults to empty string.
            clear_cache (bool): Whether to clear existing cache. Defaults to False.
            ttl (int): Time-to-live for cached data in days. Defaults to 999.
            markdown_options (Dict[str, Any], optional): Options for HTML to Markdown conversion.
            logging (bool): Enable logging. Defaults to True.
            dynamodb_table (str, optional): DynamoDB table name for cross-machine caching. Defaults to None.
            **kwargs: Additional options passed to PlaywrightScraper (browser_type, headless, etc.).
        """
        self.url = url
        self.kwargs = kwargs
        self.logging = logging
        self._markdown_options = markdown_options or {}
        self._on_progress = on_progress
        
        JSONCache.__init__(self, data_id=f"{slugify(self.url)}", directory=ScraperDefaults.CACHE_DIRECTORY,
                          clear_cache=clear_cache, ttl=ttl, logging=logging,
                          dynamodb_table=dynamodb_table)

        # Persisted fields (restored from cache by JSONCache if available)
        for attr in ("_html", "_response_code", "_response_headers", "_redirect_chain"):
            if not hasattr(self, attr):
                setattr(self, attr, None)

        self.error: Optional[Exception] = None

        # In-memory derived fields (always start as None)
        self._article: newspaper.Article | None = None
        self._soup: BeautifulSoup | None = None
        self._markdown: str | None = None
        self._text: str | None = None
        self._authors: str | None = None
        self._seo: dict | None = None

    async def _emit(self, payload: dict):
        if self._on_progress is None:
            return
        try:
            payload["ts"] = time.time()
            if asyncio.iscoroutinefunction(self._on_progress):
                await self._on_progress(payload)
            else:
                self._on_progress(payload)
        except Exception:
            pass

    def __str__(self):
        return f"{self.url}"

    def __repr__(self):
        return self.__str__()

    @property
    @Cached()
    def _playwright_scraper(self):
        """Lazy-loaded Playwright scraper instance."""
        return PlaywrightScraper(url=self.url, logging=self.logging, on_progress=self._on_progress, **self.kwargs)

    async def _fetch_response(self):
        """Internal method to fetch response from Playwright scraper."""
        if self.logging:
            Logger.note(f"Fetching URL via Playwright: {self.url}")
        return await self._playwright_scraper.fetch_and_close()

    async def get_response(self):
        """Get the cached or fetched response containing HTML and status code.
        
        Returns:
            dict: Dictionary with 'html' and 'response_code' keys.
        """
        if self._response_code is None or self._html is None:
            if self.logging:
                Logger.note(f"📥 Cache miss: {self.url[:60]}... - Fetching from web")
            await self._emit({"event": "started", "url": self.url})
            try:
                (self._html, self._response_code, self._response_headers, self._redirect_chain) = await self._fetch_response()
            except Exception as e:
                await self._emit({"event": "error", "url": self.url, "message": str(e)})
                raise
            self.json_cache_save()
            await self._emit({"event": "page_loaded", "url": self.url, "completed": 1, "total": 1, "status_code": self._response_code})
        return {"html": self._html, "response_code": self._response_code}

    async def html(self) -> str:
        """Return the raw HTML content of the page."""
        if self.error is not None:
            return ""
        return (await self.get_response())["html"]

    async def response_code(self) -> Optional[int]:
        """Return the HTTP response status code, or None if an error occurred."""
        if self.error is not None:
            return None
        return (await self.get_response())["response_code"]

    async def response_headers(self) -> dict:
        """Return the HTTP response headers from the final response."""
        await self.get_response()
        return self._response_headers or {}

    async def redirect_chain(self) -> list:
        """Return the full redirect chain as a list of dicts with 'url' and 'status' keys."""
        await self.get_response()
        return self._redirect_chain or []

    async def final_url(self) -> str:
        """Return the resolved final URL after following all redirects."""
        chain = await self.redirect_chain()
        return chain[-1]["url"] if chain else self.url

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

    async def seo(self) -> dict:
        """Return a dict of SEO metadata parsed from the page (title, description, og, twitter, etc.)."""
        if self._seo is None:
            soup = await self.soup()
            result = {}

            title = soup.find("title")
            if title:
                result["title"] = title.get_text()

            desc = soup.find("meta", attrs={"name": "description"})
            if desc and desc.get("content"):
                result["description"] = desc["content"]

            canonical = soup.find("link", attrs={"rel": "canonical"})
            if canonical and canonical.get("href"):
                result["canonical"] = canonical["href"]

            for meta_name in ("robots", "googlebot"):
                tag = soup.find("meta", attrs={"name": meta_name})
                if tag and tag.get("content"):
                    directives = {d.strip().lower(): True for d in tag["content"].split(",") if d.strip()}
                    if directives:
                        result[meta_name] = directives

            og = {}
            for tag in soup.find_all("meta", property=lambda v: v and v.startswith("og:")):
                og[tag["property"][3:]] = tag.get("content", "")
            if og:
                result["og"] = og

            twitter = {}
            for tag in soup.find_all("meta", attrs={"name": lambda v: v and v.startswith("twitter:")}):
                twitter[tag["name"][8:]] = tag.get("content", "")
            if twitter:
                result["twitter"] = twitter

            hreflang = {}
            for tag in soup.find_all("link", rel="alternate"):
                lang = tag.get("hreflang")
                href = tag.get("href")
                if lang and href:
                    hreflang.setdefault(lang, []).append(href)
            if hreflang:
                result["hreflang"] = hreflang

            self._seo = result
        return self._seo

    @classmethod
    async def scrape_many(cls, urls: List[str], max_concurrent: int = ScraperDefaults.MAX_CONCURRENT, 
                         logging: bool = ScraperDefaults.LOGGING, fail_fast: bool = True, **kwargs) -> List['GhostScraper']:
        """Scrape multiple URLs in parallel using a shared browser instance.
        
        This method efficiently scrapes multiple URLs by sharing a single browser
        instance and controlling concurrency. Results are cached immediately as
        they complete.
        
        Args:
            urls (List[str]): List of URLs to scrape.
            max_concurrent (int): Maximum number of concurrent page loads. Defaults to 15.
            logging (bool): Enable logging. Defaults to True.
            fail_fast (bool): If True, any exception aborts the batch. If False, failures are captured per-scraper. Defaults to True.
            **kwargs: Additional arguments for GhostScraper (clear_cache, ttl, dynamodb_table) 
                     and PlaywrightScraper (browser_type, headless, etc.).
            
        Returns:
            List[GhostScraper]: List of GhostScraper instances with cached results.
            
        Example:
            >>> urls = ["https://example.com", "https://python.org"]
            >>> scrapers = await GhostScraper.scrape_many(urls, max_concurrent=5)
            >>> for scraper in scrapers:
            ...     text = await scraper.text()
        """
        if logging:
            Logger.note(f"\n🚀 Starting batch scrape: {len(urls)} URLs | Concurrency: {max_concurrent}")
        
        on_progress = kwargs.pop("on_progress", None)

        # Separate GhostScraper kwargs from PlaywrightScraper kwargs
        playwright_kwargs = {k: v for k, v in kwargs.items() 
                            if k not in ['clear_cache', 'ttl', 'dynamodb_table', 'markdown_options']}
        
        # Create scraper instances
        scrapers = [cls(url=url, logging=logging, on_progress=on_progress, **kwargs) for url in urls]
        
        # Separate cached and non-cached scrapers
        scrapers_to_fetch = [s for s in scrapers if s._html is None]
        cached_count = len(scrapers) - len(scrapers_to_fetch)
        
        if logging:
            Logger.note(f"💾 Cache status: {cached_count} cached | {len(scrapers_to_fetch)} to fetch")

        if on_progress:
            await scrapers[0]._emit({"event": "batch_started", "total": len(urls), "to_fetch": len(scrapers_to_fetch), "cached": cached_count})
        
        # Fetch and save each URL as it completes
        if scrapers_to_fetch:
            if logging:
                Logger.note(f"🌐 Fetching {len(scrapers_to_fetch)} URLs from web...")
            
            total = len(scrapers_to_fetch)
            completed = 0

            async with PlaywrightScraper(logging=logging, on_progress=on_progress, **playwright_kwargs) as browser:
                semaphore = asyncio.Semaphore(max_concurrent)
                
                async def fetch_and_save(scraper: 'GhostScraper'):
                    nonlocal completed
                    await scraper._emit({"event": "started", "url": scraper.url})
                    async with semaphore:
                        try:
                            html, status_code, headers, redirect_chain = await browser.fetch_url(scraper.url)
                        except Exception as e:
                            await scraper._emit({"event": "error", "url": scraper.url, "message": str(e)})
                            if fail_fast:
                                raise
                            scraper.error = e
                            scraper._html = ""
                            scraper._response_code = None
                            completed += 1
                            return scraper
                        scraper._html = html
                        scraper._response_code = status_code
                        scraper._response_headers = headers
                        scraper._redirect_chain = redirect_chain
                        scraper.json_cache_save()
                        completed += 1
                        await scraper._emit({"event": "page_loaded", "url": scraper.url, "completed": completed, "total": total, "status_code": status_code, "scraper": scraper})
                        return scraper
                
                await asyncio.gather(*[fetch_and_save(s) for s in scrapers_to_fetch], return_exceptions=True)
        else:
            if logging:
                Logger.note(f"✅ All URLs found in cache - No fetching needed")

        if on_progress:
            cached_scrapers = [s for s in scrapers if s not in scrapers_to_fetch]
            total = len(scrapers)
            for i, scraper in enumerate(cached_scrapers, start=len(scrapers_to_fetch) + 1):
                await scraper._emit({"event": "page_loaded", "url": scraper.url, "completed": i, "total": total, "status_code": scraper._response_code, "scraper": scraper})
        
        if logging:
            Logger.note(f"✓ Batch scrape completed: {len(urls)} URLs processed\n")

        if on_progress:
            await scrapers[0]._emit({"event": "batch_done", "total": len(urls)})

        return scrapers
