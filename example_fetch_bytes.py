import asyncio
from ghostscraper import GhostScraper

URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Collage_of_Nine_Dogs.jpg/1200px-Collage_of_Nine_Dogs.jpg"

async def main():
    body, status_code, headers = await GhostScraper.fetch_bytes(URL, cache=True)
    print(f"Status: {status_code} | Size: {len(body)} bytes | Content-Type: {headers.get('content-type')}")

asyncio.run(main())
