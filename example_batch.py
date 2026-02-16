import asyncio
from ghostscraper import GhostScraper

async def main():
    urls = [
        "https://www.audible.de/pd/B0DPKPGH3Q?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DT9RDQZR?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DN6K9LP4?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DQV9S8FK?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DTN1X5D2?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DTPKH7JN?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0D155D4DC?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DV6BS3YT?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DMWNPHMY?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DJWFBVJR?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DTZ33D5R?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DPZTKMW4?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DNKJ9TRJ?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DQYH6L1L?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DNKGCBJ9?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DNQRKGBJ?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DQL1D4NZ?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DT1JFNY2?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DQ8PG2N7?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DT1HNZCX?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DTPLWYGW?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.de/pd/B0DSJFCGRT?overrideBaseCountry=true&ipRedirectOverride=true",
    ]
    
    # Scrape multiple URLs in parallel with shared browser
    # log_level options: "none", "normal", "verbose"
    scrapers = await GhostScraper.scrape_many(
        urls=urls,
        log_level="normal"  # No logging output
    )
    
    # Access results from each scraper
    for scraper in scrapers:
        html = await scraper.html()
        status = await scraper.response_code()
        print(f"{scraper.url}: {status} - {len(html)} chars")

if __name__ == "__main__":
    asyncio.run(main())
