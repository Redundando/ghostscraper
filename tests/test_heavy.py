"""Heavy lifting test: stream ~70 Audible.it URLs and monitor memory."""
import asyncio
import os
import psutil
from ghostscraper import GhostScraper, ScraperDefaults

ScraperDefaults.MAX_WORKERS = 2
ScraperDefaults.SUBPROCESS_BATCH_SIZE = 15

ASINS = [
    "B0CDLR2L3T", "B0BZDRDGZV", "B0FDL1PQF4", "B0G99MQWV4", "B01MXPXE0D",
    "B0C441X1G8", "B0D1R4HPRK", "B0G3XGJ66W", "B0DM2DTKRC", "B0D9Q5RMMJ",
    "B0DWSL1SJC", "B072JXMKSZ", "B0BBSJNPHC", "B0BZDNM8KK", "B0F1NCTKK7",
    "B0BBSGQWFG", "B0CCJ4V595", "3748044615", "B07T9FW6QD", "3748029446",
    "B0BZ5437QT", "B0G2MG5QGV", "B07VF72VJL", "B07DPL4W5F", "B0CPM5HCXJ",
    "B0BVBWGTBV", "B07YYJ7VK9", "B0FCS46759", "8865747854", "3960858108",
    "B0FNWR9GV5", "B0G5PNBDS2", "B0CNRSV6Z8", "3748050739", "B09LVMTC3P",
    "B07Q9192JJ", "B0FP32VMYR", "B0GL2WLN1Y", "B0DB59G1X8", "B0G6Z5DWWP",
    "8868162059", "8867157590", "B0D31VCYSR", "B0DNZD9BGF", "B0F9FG65WS",
    "B0B8JMVNBZ", "8858490754", "872656100X", "8852155031", "B0G1MM9WGS",
    "B0GH8DD64W", "B0C1C28C36", "3748035373", "B0FGQ1ZDRQ", "B0CH8SFRR6",
    "B0CK4VJZK2", "B0G4F1RTP3", "B0G5NBN9B4", "B0FX9XVCTM", "8862771908",
    "B074FZP6HG", "B0CLPGPZWX", "B07VYM9QQP", "8852154736", "B0GNSWP7SS",
    "8893311224", "B07P5DZP4T", "3748044607", "B0CG6QVKK6", "8833536793",
]

BASE = "https://www.audible.it/pd/{}?overrideBaseCountry=true&ipRedirectOverride=true"
URLS = [BASE.format(asin) for asin in ASINS]


def mem_mb():
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024


async def main():
    print(f"Total URLs: {len(URLS)}")
    print(f"Initial memory: {mem_mb():.1f} MB\n")

    def on_progress(event):
        e = event.get("event", event.get("type", ""))
        url = event.get("url", "")[-40:]
        extra = ""
        if "completed" in event and "total" in event:
            extra = f" [{event['completed']}/{event['total']}]"
        if "chunk_index" in event:
            extra = f" chunk={event['chunk_index']} size={event.get('chunk_size', '?')}"
        print(f"  ⚡ {e}{extra} {url}")

    print("Creating stream...")
    stream = GhostScraper.create_stream(
        urls=URLS,
        dynamodb_table="test-scrape",
        stream_id="audible-heavy-test",
        clear_cache=True,
        max_retries=2,
        load_strategies=["domcontentloaded"],
        no_retry_on=[404, 403],
        subprocess_batch_size=15,
        max_concurrent=10,
        on_progress=on_progress,
    )
    print(f"Stream created. Memory: {mem_mb():.1f} MB")
    print("Starting iteration...")

    ok = 0
    fail = 0

    async for scraper in stream:
        if scraper.error:
            fail += 1
            print(f"  ❌ {scraper.url[-20:]} — {scraper.error}")
        else:
            ok += 1
            print(f"  ✅ {scraper.url[-20:]}")

        done = ok + fail
        if done % 10 == 0:
            print(f"  --- {done}/{len(URLS)} done | Memory: {mem_mb():.1f} MB ---")

    print(f"\nDone: {ok} ok, {fail} failed")
    print(f"Final memory: {mem_mb():.1f} MB")

    await GhostScraper.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
