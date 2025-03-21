from ghostscraper import GhostScraper
import asyncio

async def main():
    scraper = GhostScraper(url="https://rogersreads.com/review-of-darius-the-great-is-not-okay-by-adib-khorram/")


    print(await scraper.text())


if __name__ == '__main__':
    asyncio.run(main())