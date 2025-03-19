from ghostscraper import GhostScraper
import asyncio

async def main():
    scraper = GhostScraper(url="https://www.example.com")
    print((await scraper.soup()).prettify())


if __name__ == '__main__':
    scraper = GhostScraper(url="https://www.example.com", clear_cache=True)
    print(len(asyncio.run(scraper.html())))