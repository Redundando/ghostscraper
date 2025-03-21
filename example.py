from ghostscraper import GhostScraper
import asyncio

async def main():
    scraper = GhostScraper(url="https://en.wikipedia.org/wiki/Darius_the_Great_Is_Not_Okay", clear_cache=True)
    html = await scraper.html()
    md = await scraper.markdown()
    print(md)


if __name__ == '__main__':
    asyncio.run(main())