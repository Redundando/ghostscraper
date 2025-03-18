import asyncio
from typing import Any, Dict, List, Literal, Optional, Tuple

from logorator import Logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError

from playwright_installer import check_browser_installed, install_browser


class PlaywrightScraper:
    BROWSERS_CHECKED = {}

    def __init__(self, url: str = "", browser_type: Literal["chromium", "firefox", "webkit"] = "chromium", headless: bool = True, browser_args: Optional[Dict[str, Any]] = None,
            context_args: Optional[Dict[str, Any]] = None, max_retries: int = 3, backoff_factor: float = 2.0, network_idle_timeout: int = 10000,  # 10 seconds
            load_timeout: int = 30000,  # 30 seconds
            wait_for_selectors: Optional[List[str]] = None  # CSS selectors to wait for
    ):
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
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.last_status_code: int = 200

    async def check_and_install_browser(self):
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
        # Strategy 1: Try with networkidle first (strictest, but most reliable)
        try:
            Logger.note(f"GhostScraper: Attempting to load with 'networkidle' (timeout: {self.network_idle_timeout}ms)")
            response = await page.goto(url, wait_until="networkidle", timeout=self.network_idle_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("GhostScraper: 'networkidle' timed out, falling back to 'load'")
            pass

        # Strategy 2: Fallback to load event (less strict)
        try:
            Logger.note(f"GhostScraper: Attempting to load with 'load' (timeout: {self.load_timeout}ms)")
            response = await page.goto(url, wait_until="load", timeout=self.load_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("GhostScraper: 'load' timed out, falling back to 'domcontentloaded'")
            pass

        # Strategy 3: Fallback to domcontentloaded (least strict)
        try:
            Logger.note("GhostScraper: Attempting to load with 'domcontentloaded'")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.load_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("GhostScraper: All loading strategies failed")
            return False, 408  # Request Timeout

    async def _wait_for_selectors(self, page: Page) -> bool:
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

    async def fetch(self) -> Tuple[str, int]:
        await self._ensure_browser()
        attempts = 0

        while attempts <= self.max_retries:
            page: Page = await self._context.new_page()
            try:
                # Set a default navigation timeout
                page.set_default_navigation_timeout(self.load_timeout)
                # Try progressive loading strategies
                load_success, status_code = await self._try_progressive_load(page, self.url)
                self.last_status_code = status_code

                if not load_success:
                    if attempts == self.max_retries:
                        Logger.note(f"GhostScraper: Max retries reached. All loading strategies failed.")
                        return "", 408
                    wait_time = self.backoff_factor ** attempts
                    Logger.note(f"GhostScraper: All loading strategies failed. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                if status_code >= 400:
                    if attempts == self.max_retries:
                        Logger.note(f"GhostScraper: Max retries reached with status code {status_code}. Returning empty response.")
                        return "", status_code

                    wait_time = self.backoff_factor ** attempts
                    Logger.note(f"GhostScraper: Status code {status_code} received. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
                    attempts += 1
                    continue

                # Try to wait for specified selectors (if any)
                await self._wait_for_selectors(page)

                # If we reached here, we consider it a success. Grab the content and return.
                html: str = await page.content()
                return html, status_code

            except PlaywrightTimeoutError as e:
                if attempts == self.max_retries:
                    Logger.note(f"GhostScraper: Max retries reached after timeout. Returning empty response with 408 status.")
                    return "", 408

                wait_time = self.backoff_factor ** attempts
                Logger.note(f"GhostScraper: Timeout error occurred: {str(e)}. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                attempts += 1

            except Exception as e:
                if attempts == self.max_retries:
                    Logger.note(f"GhostScraper: Max retries reached after exception: {str(e)}. Returning empty response with 500 status.")
                    return "", 500

                wait_time = self.backoff_factor ** attempts
                Logger.note(f"GhostScraper: Exception occurred: {str(e)}. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                attempts += 1

            finally:
                await page.close()

        # This should not be reached, but just in case
        return "", 500

    async def close(self) -> None:
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
        try:
            return await self.fetch()
        finally:
            await self.close()

    async def __aenter__(self):
        await self._ensure_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


if __name__ == "__main__":
    async def main():
        urls = ["https://en.wikipedia.org/wiki/Debbie_Wasserman_Schultz", "https://en.wikipedia.org/wiki/Chuck_Schumer", "https://playwright.dev/python/docs/library"]
        pws = []
        tasks = []
        for url in urls:
            s = PlaywrightScraper(url=url)
            pws.append(s)
            tasks.append(asyncio.create_task(s.fetch_and_close()))
        await asyncio.gather(*tasks)


    asyncio.run(main())
