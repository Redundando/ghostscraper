import asyncio
from ghostscraper import GhostScraper


async def main():
    scraper = GhostScraper(url="https://www.audible.com/pd/B0CQP8RXHN?overrideBaseCountry=true&ipRedirectOverride=true")
    seo = await scraper.seo()
    print(seo)


asyncio.run(main())
