from logorator import Logger
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from cacherator import Cached, JSONCache
from slugify import slugify

from .playwright_scraper import PlaywrightScraper
import html2text

class GhostScraper(JSONCache):
    def __init__(self, url="", clear_cache=False, ttl=999,markdown_options: Optional[Dict[str, Any]] = None, **kwargs):
        self.url = url
        self._html: str | None = None
        self._soup: BeautifulSoup | None = None
        self._markdown: str | None = None
        self._response_code: int | None = None
        self.kwargs = kwargs
        self._markdown_options = markdown_options or {}

        JSONCache.__init__(self, data_id=f"{slugify(self.url)}", directory="data/ghostscraper", clear_cache=clear_cache, ttl=ttl)

    def __str__(self):
        return f"{self.url}"

    def __repr__(self):
        return self.__str__()

    @property
    @Cached()
    def _playwright_scraper(self):
        return PlaywrightScraper(url=self.url, **self.kwargs)

    @Logger(override_function_name="Fetching URL via Playwright")
    async def _fetch_response(self):
        return await self._playwright_scraper.fetch_and_close()

    async def get_response(self):
        if self._response_code is None or self._html is None:
            (self._html, self._response_code) = await self._fetch_response()
        return {"html": self._html, "response_code": self._response_code}

    async def html(self):
        return (await self.get_response())["html"]

    async def response_code(self):
        return (await self.get_response())["response_code"]

    async def markdown(self) -> str:
        if self._markdown is None:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.body_width = 0
            h.ignore_images = False
            self._markdown = h.handle(await self.html())
        return self._markdown

    async def soup(self) -> BeautifulSoup:
        if self._soup is None:
            self._soup = BeautifulSoup(await self.html(), "html.parser")
        return self._soup
