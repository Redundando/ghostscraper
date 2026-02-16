"""GhostScraper Configuration

Centralized configuration for default scraping behavior.

You can override defaults in two ways:
1. Pass parameters directly to GhostScraper or PlaywrightScraper
2. Modify ScraperDefaults class attributes at runtime:

    >>> from ghostscraper import ScraperDefaults
    >>> ScraperDefaults.MAX_CONCURRENT = 20
    >>> ScraperDefaults.LOG_LEVEL = "verbose"
"""

from typing import Literal

# Logging levels
LogLevel = Literal["none", "normal", "verbose"]


class ScraperDefaults:
    """Default configuration values for GhostScraper.
    
    These class attributes can be modified at runtime to change defaults
    for all future scraper instances.
    
    Example:
        >>> ScraperDefaults.MAX_CONCURRENT = 10
        >>> ScraperDefaults.HEADLESS = False
    """
    
    # Browser settings
    BROWSER_TYPE: Literal["chromium", "firefox", "webkit"] = "chromium"
    HEADLESS: bool = True
    
    # Timeout settings (in milliseconds)
    NETWORK_IDLE_TIMEOUT: int = 3000   # 3 seconds (reduced from 10s)
    LOAD_TIMEOUT: int = 20000          # 20 seconds (reduced from 30s)
    
    # Retry settings
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 2.0
    
    # Concurrency settings
    MAX_CONCURRENT: int = 15  # Parallel requests in batch mode
    
    # Cache settings
    CACHE_TTL: int = 999  # Days
    CACHE_DIRECTORY: str = "data/ghostscraper"
    
    # Logging
    LOG_LEVEL: LogLevel = "normal"  # "none", "normal", or "verbose"
