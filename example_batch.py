import asyncio
from ghostscraper import GhostScraper

async def main():
    urls = [
        "https://www.audible.de/pd/B0DPKPGH3Q?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B082BHJMFF?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B007NLZ9SM?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002UZLF2U?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002VA35NG?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00WNBF0RM?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V5D7KC?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002VA9WOW?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V59TMM?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B077D2KFF7?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00VGSQTHS?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002UZJGYY?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B08G9PRS1K?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B003D8W5VS?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V1OF70?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V5A12Y?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V0QDNU?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B0036N2C7M?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00P0277C2?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V8L5FS?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00HJZAQPI?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B01M0JIAL6?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B086WNG3RK?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V5GWHM?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B0053ZT602?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B0030GOEUS?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002VACDZ2?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V5GYHA?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B0049WSD36?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V1NMX8?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00GMPEKHG?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V1OL2O?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V5GV1O?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00GHUHVPO?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B007CMDU5G?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002V8ODZW?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B073H9PF2D?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B002VA9X3C?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/0062969536?overrideBaseCountry=true&ipRedirectOverride=true",
        "https://www.audible.com/pd/B00505UB2W?overrideBaseCountry=true&ipRedirectOverride=true",
    ]
    
    # Scrape multiple URLs in parallel with shared browser
    # log_level options: "none", "normal", "verbose"
    scrapers = await GhostScraper.scrape_many(
        urls=urls[:15],
        dynamodb_table="ghostscraper_cache",
    )
    
    # Access results from each scraper
    for scraper in scrapers:
        html = await scraper.html()
        status = await scraper.response_code()
        print(f"{scraper.url}: {status} - {len(html)} chars")

if __name__ == "__main__":
    asyncio.run(main())
