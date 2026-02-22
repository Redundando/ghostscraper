import asyncio
from ghostscraper import GhostScraper


async def on_progress(event):
    await asyncio.sleep(0)  # simulate async work
    print(event)


async def main():
    scrapers = await GhostScraper.scrape_many(
        urls=["https://example.com", "https://httpstat.us/404", "https://httpstat.us/500"],
        clear_cache=True,
        logging=False,
        on_progress=on_progress,
    )


asyncio.run(main())
