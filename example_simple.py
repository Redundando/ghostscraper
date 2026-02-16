import asyncio
from ghostscraper import GhostScraper

async def main():
    scraper = GhostScraper(url="https://example.com")
    
    html = await scraper.html()
    print(f"HTML length: {len(html)} characters")
    
    text = await scraper.text()
    print(f"\nText content:\n{text}")

if __name__ == "__main__":
    asyncio.run(main())
