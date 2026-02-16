"""Playwright-based web scraper with retry logic and progressive loading.

This module provides low-level browser automation using Playwright with
automatic browser installation, retry mechanisms, and multiple loading strategies.
"""

import asyncio
from typing import Any, Dict, List, Literal, Optional, Tuple

from logorator import Logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError

from .playwright_installer import check_browser_installed, install_browser
from .config import ScraperDefaults, LogLevel


class PlaywrightScraper:
    """Low-level browser automation class using Playwright.
    
    Handles browser lifecycle, page loading with multiple strategies,
    retry logic with exponential backoff, and concurrent scraping.
    
    Attributes:
        url (str): The URL to scrape.
        browser_type (str): Browser engine - "chromium", "firefox", or "webkit".
        headless (bool): Whether to run browser in headless mode.
        log_level (LogLevel): Logging verbosity level.
    """
    
    BROWSERS_CHECKED = {}

    def __init__(self, url: str = "", browser_type: Literal["chromium", "firefox", "webkit"] = ScraperDefaults.BROWSER_TYPE, 
                 headless: bool = ScraperDefaults.HEADLESS, browser_args: Optional[Dict[str, Any]] = None,
                 context_args: Optional[Dict[str, Any]] = None, max_retries: int = ScraperDefaults.MAX_RETRIES, 
                 backoff_factor: float = ScraperDefaults.BACKOFF_FACTOR, 
                 network_idle_timeout: int = ScraperDefaults.NETWORK_IDLE_TIMEOUT,
                 load_timeout: int = ScraperDefaults.LOAD_TIMEOUT,
                 wait_for_selectors: Optional[List[str]] = None,
                 log_level: LogLevel = ScraperDefaults.LOG_LEVEL
    ):
        """Initialize a PlaywrightScraper instance.
        
        Args:
            url (str): The URL to scrape. Defaults to empty string.
            browser_type (Literal): Browser engine - "chromium", "firefox", or "webkit". Defaults to "chromium".
            headless (bool): Run browser in headless mode. Defaults to True.
            browser_args (Dict[str, Any], optional): Additional browser launch arguments.
            context_args (Dict[str, Any], optional): Additional browser context arguments.
            max_retries (int): Maximum retry attempts. Defaults to 3.
            backoff_factor (float): Exponential backoff multiplier. Defaults to 2.0.
            network_idle_timeout (int): Network idle timeout in milliseconds. Defaults to 3000.
            load_timeout (int): Page load timeout in milliseconds. Defaults to 20000.
            wait_for_selectors (List[str], optional): CSS selectors to wait for before considering page loaded.
            log_level (LogLevel): Logging level - "none", "normal", or "verbose". Defaults to "normal".
        """
        self.url = url
        self.browser_type: str = browser_type
        self.headless: bool = headless
        self.browser_args: Dict[str, Any] = browser_args or {}
        self.context_args: Dict[str, Any] = context_args or {}
        self.max_retries: int = max_retries
        self.backoff_factor: float = backoff_factor
        self.network_idle_timeout: int = network_idle_timeout
        self.load_timeout: int = load_timeout
        self.wait_for_selectors: List[str] = wait_for_selectors or []
        self.log_level: LogLevel = log_level
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.last_status_code: int = 200

    def __str__(self):
        return self.url

    def __repr__(self):
        return self.__str__()

    async def check_and_install_browser(self) -> bool:
        """Check if browser is installed and install if needed.
        
        Returns:
            bool: True if browser is available, False otherwise.
        """
        if PlaywrightScraper.BROWSERS_CHECKED.get(self.browser_type) is not None:
            return PlaywrightScraper.BROWSERS_CHECKED.get(self.browser_type)
        if await check_browser_installed(self.browser_type):
            PlaywrightScraper.BROWSERS_CHECKED[self.browser_type] = True
            return True
        else:
            install_browser(self.browser_type)
            PlaywrightScraper.BROWSERS_CHECKED[self.browser_type] = asyncio.run(check_browser_installed(self.browser_type))
            return PlaywrightScraper.BROWSERS_CHECKED[self.browser_type]

    async def _ensure_browser(self) -> None:
        """Ensure browser is launched and ready.
        
        Raises:
            ValueError: If browser_type is not recognized.
        """
        await self.check_and_install_browser()
        if self._playwright is None:
            self._playwright = await async_playwright().start()

            if self.browser_type == "chromium":
                browser_launcher = self._playwright.chromium
            elif self.browser_type == "firefox":
                browser_launcher = self._playwright.firefox
            elif self.browser_type == "webkit":
                browser_launcher = self._playwright.webkit
            else:
                raise ValueError(f"Unknown browser type: {self.browser_type}")

            self._browser = await browser_launcher.launch(headless=self.headless, **self.browser_args)

            self._context = await self._browser.new_context(**self.context_args)

    async def _try_progressive_load(self, page: Page, url: str) -> Tuple[bool, int]:
        """Try multiple loading strategies progressively.
        
        Attempts 'load' -> 'networkidle' -> 'domcontentloaded' strategies.
        
        Args:
            page (Page): Playwright page object.
            url (str): URL to load.
            
        Returns:
            Tuple[bool, int]: (success, status_code)
        """
        # Strategy 1: Try with 'load' first (fast and reliable for most sites)
        try:
            if self.log_level == "verbose":
                Logger.note(f"  ⏳ Loading strategy: load (timeout: {self.load_timeout}ms)")
            response = await page.goto(url, wait_until="load", timeout=self.load_timeout)
            status_code = response.status if response else 200
            if self.log_level == "verbose":
                Logger.note(f"  ✓ Success with load - Status: {status_code}")
            return True, status_code
        except PlaywrightTimeoutError:
            if self.log_level == "verbose":
                Logger.note("  ⚠ load timeout, trying 'networkidle'...")
            pass

        # Strategy 2: Fallback to networkidle (slower but more complete)
        try:
            if self.log_level == "verbose":
                Logger.note(f"  ⏳ Loading strategy: networkidle (timeout: {self.network_idle_timeout}ms)")
            response = await page.goto(url, wait_until="networkidle", timeout=self.network_idle_timeout)
            status_code = response.status if response else 200
            if self.log_level == "verbose":
                Logger.note(f"  ✓ Success with networkidle - Status: {status_code}")
            return True, status_code
        except PlaywrightTimeoutError:
            if self.log_level == "verbose":
                Logger.note("  ⚠ networkidle timeout, trying 'domcontentloaded'...")
            pass

        # Strategy 3: Fallback to domcontentloaded (fastest but least complete)
        try:
            if self.log_level == "verbose":
                Logger.note("  ⏳ Loading strategy: domcontentloaded")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.load_timeout)
            status_code = response.status if response else 200
            if self.log_level == "verbose":
                Logger.note(f"  ✓ Success with domcontentloaded - Status: {status_code}")
            return True, status_code
        except PlaywrightTimeoutError:
            if self.log_level == "verbose":
                Logger.note("  ❌ All loading strategies failed")
            return False, 408  # Request Timeout

    async def _wait_for_selectors(self, page: Page) -> bool:
        """Wait for specified CSS selectors to appear on the page.
        
        Args:
            page (Page): Playwright page object.
            
        Returns:
            bool: True if successful or no selectors specified.
        """
        if not self.wait_for_selectors:
            return True

        try:
            for selector in self.wait_for_selectors:
                try:
                    Logger.note(f"GhostScraper: Waiting for selector '{selector}'")
                    await page.wait_for_selector(selector, timeout=5000)
                    Logger.note(f"GhostScraper: Found selector '{selector}'")
                except PlaywrightTimeoutError:
                    Logger.note(f"GhostScraper: Selector '{selector}' not found, continuing anyway")
            return True
        except Exception as e:
            Logger.note(f"GhostScraper: Error waiting for selectors: {str(e)}")
            return False

    async def fetch_url(self, url: str) -> Tuple[str, int]:
        """Fetch a specific URL using the shared browser instance.
        
        Args:
            url (str): The URL to fetch.
            
        Returns:
            Tuple[str, int]: (html_content, status_code)
        """
        if self.log_level in ["normal", "verbose"]:
            Logger.note(f"🌐 Fetching: {url[:80]}...")
        await self._ensure_browser()
        attempts = 0

        while attempts <= self.max_retries:
            page: Page = await self._context.new_page()
            try:
                page.set_default_navigation_timeout(self.load_timeout)
                load_success, status_code = await self._try_progressive_load(page, url)

                if not load_success:
                    if attempts == self.max_retries:
                        if self.log_level == "verbose":
                            Logger.note(f"  ❌ Max retries reached - All strategies failed")
                        return "", 408
                    wait_time = self.backoff_factor ** attempts
                    if self.log_level == "verbose":
                        Logger.note(f"  ⏳ Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                if status_code >= 400:
                    if attempts == self.max_retries:
                        if self.log_level == "verbose":
                            Logger.note(f"  ❌ Max retries reached - Status {status_code}")
                        return "", status_code

                    wait_time = self.backoff_factor ** attempts
                    if self.log_level == "verbose":
                        Logger.note(f"  ⚠ Status {status_code} - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                await self._wait_for_selectors(page)
                html: str = await page.content()
                return html, status_code

            except PlaywrightTimeoutError as e:
                if attempts == self.max_retries:
                    if self.log_level == "verbose":
                        Logger.note(f"  ❌ Timeout - Max retries reached")
                    return "", 408

                wait_time = self.backoff_factor ** attempts
                if self.log_level == "verbose":
                    Logger.note(f"  ⏳ Timeout - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                attempts += 1

            except Exception as e:
                if attempts == self.max_retries:
                    if self.log_level == "verbose":
                        Logger.note(f"  ❌ Error: {str(e)[:50]}... - Max retries reached")
                    return "", 500

                wait_time = self.backoff_factor ** attempts
                if self.log_level == "verbose":
                    Logger.note(f"  ⚠ Error: {str(e)[:50]}... - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                attempts += 1

            finally:
                await page.close()

        return "", 500

    async def fetch(self) -> Tuple[str, int]:
        """Fetch the URL specified in constructor.
        
        Returns:
            Tuple[str, int]: (html_content, status_code)
            
        Raises:
            ValueError: If no URL was specified in constructor.
        """
        if not self.url:
            raise ValueError("No URL specified. Use fetch_url(url) or provide url in constructor.")
        result = await self.fetch_url(self.url)
        self.last_status_code = result[1]
        return result

    async def fetch_many(self, urls: List[str], max_concurrent: int = 5) -> List[Tuple[str, int]]:
        """Fetch multiple URLs in parallel using a shared browser instance.
        
        Args:
            urls (List[str]): List of URLs to fetch.
            max_concurrent (int): Maximum concurrent requests. Defaults to 5.
            
        Returns:
            List[Tuple[str, int]]: List of (html_content, status_code) tuples.
        """
        await self._ensure_browser()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(url: str) -> Tuple[str, int]:
            async with semaphore:
                return await self.fetch_url(url)
        
        results = await asyncio.gather(*[fetch_with_semaphore(url) for url in urls], return_exceptions=True)
        
        # Convert exceptions to error tuples
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if self.log_level == "verbose":
                    Logger.note(f"  ❌ Error fetching {urls[i][:60]}...: {str(result)[:40]}")
                processed_results.append(("", 500))
            else:
                processed_results.append(result)
        
        return processed_results

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_and_close(self) -> Tuple[str, int]:
        """Fetch URL and immediately close browser.
        
        Returns:
            Tuple[str, int]: (html_content, status_code)
        """
        try:
            return await self.fetch()
        finally:
            await self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
