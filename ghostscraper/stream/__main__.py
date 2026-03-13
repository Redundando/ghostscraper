"""Entry point for subprocess worker: python -m ghostscraper.stream <temp_file_path>"""

import asyncio
import sys

from .worker import worker_main

if __name__ == "__main__":
    asyncio.run(worker_main(sys.argv[1]))
