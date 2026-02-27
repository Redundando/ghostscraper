"""Playwright-based web scraper with retry logic and progressive loading.

This module provides low-level browser automation using Playwright with
automatic browser installation, retry mechanisms, and multiple loading strategies.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from logorator import Logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError

from .playwright_installer import check_browser_installed, install_browser
from .config import ScraperDefaults


class PlaywrightScraper:
    """Low-level browser automation class using Playwright.
    
    Handles browser lifecycle, page loading with multiple strategies,
    retry logic with exponential backoff, and concurrent scraping.
    
    Attributes:
        url (str): The URL to scrape.
        browser_type (str): Browser engine - "chromium", "firefox", or "webkit".
        headless (bool): Whether to run browser in headless mode.
        logging (bool): Enable/disable logging.
    """
    
    BROWSERS_CHECKED = {}

    def __init__(self, url: str = "", browser_type: Literal["chromium", "firefox", "webkit"] = ScraperDefaults.BROWSER_TYPE, 
                 headless: bool = ScraperDefaults.HEADLESS, browser_args: Optional[Dict[str, Any]] = None,
                 context_args: Optional[Dict[str, Any]] = None, max_retries: int = ScraperDefaults.MAX_RETRIES, 
                 backoff_factor: float = ScraperDefaults.BACKOFF_FACTOR, 
                 network_idle_timeout: int = ScraperDefaults.NETWORK_IDLE_TIMEOUT,
                 load_timeout: int = ScraperDefaults.LOAD_TIMEOUT,
                 wait_for_selectors: Optional[List[str]] = None,
                 logging: bool = ScraperDefaults.LOGGING,
                 on_progress: Optional[Callable] = None,
                 load_strategies: Optional[List[str]] = None,
                 no_retry_on: Optional[List[int]] = None
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
            logging (bool): Enable logging. Defaults to True.
            load_strategies (List[str], optional): Loading strategies to try in order. Defaults to ["load", "networkidle", "domcontentloaded"].
            no_retry_on (List[int], optional): Status codes that skip retries immediately. Defaults to None.
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
        self.logging: bool = logging
        self._on_progress = on_progress
        self.load_strategies: List[str] = load_strategies if load_strategies is not None else ScraperDefaults.LOAD_STRATEGIES
        self.no_retry_on: List[int] = no_retry_on or []
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.last_status_code: int = 200

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
        if await check_browser_installed(self.browser_type, logging=self.logging, on_progress=self._on_progress):
            PlaywrightScraper.BROWSERS_CHECKED[self.browser_type] = True
            return True
        else:
            install_browser(self.browser_type, on_progress=self._on_progress)
            PlaywrightScraper.BROWSERS_CHECKED[self.browser_type] = await check_browser_installed(self.browser_type, logging=self.logging, on_progress=self._on_progress)
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

    async def _try_progressive_load(self, page: Page, url: str, attempt: int = 0) -> Tuple[bool, int, dict, list]:
        """Try loading strategies in order, falling back on timeout.

        Returns:
            Tuple[bool, int, dict, list]: (success, status_code, headers, redirect_chain)
        """
        strategies = self.load_strategies
        for i, strategy in enumerate(strategies):
            timeout = self.network_idle_timeout if strategy == "networkidle" else self.load_timeout
            redirect_chain = []

            def on_response(response):
                redirect_chain.append({"url": response.url, "status": response.status})

            page.on("response", on_response)
            try:
                if self.logging:
                    Logger.note(f"  ⏳ Loading strategy: {strategy} (timeout: {timeout}ms)")
                await self._emit({"event": "loading_strategy", "url": url, "strategy": strategy, "attempt": attempt + 1, "max_retries": self.max_retries, "timeout": timeout})
                response = await page.goto(url, wait_until=strategy, timeout=timeout)
                status_code = response.status if response else 200
                headers = dict(response.headers) if response else {}
                if self.logging:
                    Logger.note(f"  ✓ Success with {strategy} - Status: {status_code}")
                return True, status_code, headers, redirect_chain
            except PlaywrightTimeoutError:
                page.remove_listener("response", on_response)
                next_strategy = strategies[i + 1] if i + 1 < len(strategies) else None
                if next_strategy:
                    if self.logging:
                        Logger.note(f"  ⚠ {strategy} timeout, trying '{next_strategy}'...")
                else:
                    if self.logging:
                        Logger.note("  ❌ All loading strategies failed")
                    return False, 408, {}, []

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

    async def fetch_url(self, url: str) -> Tuple[str, int, dict, list]:
        """Fetch a specific URL using the shared browser instance.

        Returns:
            Tuple[str, int, dict, list]: (html_content, status_code, headers, redirect_chain)
        """
        if self.logging:
            Logger.note(f"🌐 Fetching: {url[:80]}...")
        await self._ensure_browser()
        attempts = 0

        while attempts < self.max_retries:
            page: Page = await self._context.new_page()
            try:
                page.set_default_navigation_timeout(self.load_timeout)
                load_success, status_code, headers, redirect_chain = await self._try_progressive_load(page, url, attempt=attempts)

                if not load_success:
                    if attempts == self.max_retries:
                        if self.logging:
                            Logger.note(f"  ❌ Max retries reached - All strategies failed")
                        return "", 408, {}, []
                    wait_time = self.backoff_factor ** attempts
                    if self.logging:
                        Logger.note(f"  ⏳ Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                    if attempts < self.max_retries - 1:
                        await self._emit({"event": "retry", "url": url, "attempt": attempts + 1, "max_retries": self.max_retries})
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                if status_code >= 400:
                    if self.no_retry_on and status_code in self.no_retry_on:
                        if self.logging:
                            Logger.note(f"  ❌ Status {status_code} - no retry (no_retry_on)")
                        return "", status_code, headers, redirect_chain

                    if attempts == self.max_retries:
                        if self.logging:
                            Logger.note(f"  ❌ Max retries reached - Status {status_code}")
                        return "", status_code, headers, redirect_chain

                    wait_time = self.backoff_factor ** attempts
                    if self.logging:
                        Logger.note(f"  ⚠ Status {status_code} - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                    if attempts < self.max_retries - 1:
                        await self._emit({"event": "retry", "url": url, "attempt": attempts + 1, "max_retries": self.max_retries, "status_code": status_code})
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                await self._wait_for_selectors(page)
                html: str = await page.content()
                return html, status_code, headers, redirect_chain

            except PlaywrightTimeoutError as e:
                if attempts == self.max_retries:
                    if self.logging:
                        Logger.note(f"  ❌ Timeout - Max retries reached")
                    return "", 408, {}, []

                wait_time = self.backoff_factor ** attempts
                if self.logging:
                    Logger.note(f"  ⏳ Timeout - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                if attempts < self.max_retries - 1:
                    await self._emit({"event": "retry", "url": url, "attempt": attempts + 1, "max_retries": self.max_retries, "reason": "timeout"})
                await asyncio.sleep(wait_time)
                attempts += 1

            except Exception as e:
                if attempts == self.max_retries:
                    if self.logging:
                        Logger.note(f"  ❌ Error: {str(e)[:50]}... - Max retries reached")
                    return "", 500, {}, []

                wait_time = self.backoff_factor ** attempts
                if self.logging:
                    Logger.note(f"  ⚠ Error: {str(e)[:50]}... - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                if attempts < self.max_retries - 1:
                    await self._emit({"event": "retry", "url": url, "attempt": attempts + 1, "max_retries": self.max_retries, "reason": str(e).splitlines()[0]})
                await asyncio.sleep(wait_time)
                attempts += 1

            finally:
                await page.close()

        return "", 500, {}, []

    async def fetch_bytes(self, url: str) -> Tuple[bytes, int, dict]:
        """Fetch a URL as raw bytes using the browser context (inherits UA, cookies, headers).

        Returns:
            Tuple[bytes, int, dict]: (body, status_code, headers)
        """
        await self._ensure_browser()
        attempts = 0
        while attempts < self.max_retries:
            try:
                response = await self._context.request.get(url)
                return await response.body(), response.status, dict(response.headers)
            except Exception as e:
                if attempts == self.max_retries - 1:
                    if self.logging:
                        Logger.note(f"  ❌ fetch_bytes error: {str(e)[:50]}... - Max retries reached")
                    return b"", 500, {}
                wait_time = self.backoff_factor ** attempts
                if self.logging:
                    Logger.note(f"  ⚠ fetch_bytes error: {str(e)[:50]}... - Retry {attempts + 1}/{self.max_retries} in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                attempts += 1
        return b"", 500, {}

    async def fetch(self) -> Tuple[str, int, dict, list]:
        """Fetch the URL specified in constructor.

        Returns:
            Tuple[str, int, dict, list]: (html_content, status_code, headers, redirect_chain)
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
                if self.logging:
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
