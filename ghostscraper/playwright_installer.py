"""Playwright browser installation utilities.

Provides functions to check if browsers are installed and install them if needed.
"""

import subprocess
import sys
import os
from playwright.async_api import async_playwright, Browser, BrowserContext
from logorator import Logger


async def check_browser_installed(browser_name: str) -> bool:
    """Check if a Playwright browser is installed and working.
    
    Args:
        browser_name (str): Browser name - "chromium", "firefox", or "webkit".
        
    Returns:
        bool: True if browser is installed and working, False otherwise.
    """
    async with async_playwright() as p:
        browsers = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit, }
        if browser_name not in browsers:
            Logger.note(f"❌ Invalid browser name: {browser_name}")
            return False

        try:
            browser = await browsers[browser_name].launch()
            await browser.close()
            Logger.note(f"✅ {browser_name} is installed and working!")
            return True
        except Exception as e:
            Logger.note(f"❌ {browser_name} is NOT installed or failed to launch: {e}")
            return False

@Logger()
def install_browser(browser_type: str) -> bool:
    """Install a Playwright browser.
    
    Args:
        browser_type (str): Browser to install - "chromium", "firefox", or "webkit".
        
    Returns:
        bool: True if installation succeeded, False otherwise.
    """
    try:
        Logger.note(f"\n[Ghostscraper] Installing {browser_type} browser (first-time setup)")
        Logger.note("[Ghostscraper] This may take a few minutes...")

        subprocess.check_call([
                sys.executable, "-m", "playwright", "install", browser_type
        ])

        Logger.note(f"[Ghostscraper] Successfully installed {browser_type} browser.")
        return True

    except subprocess.CalledProcessError as e:
        Logger.note(f"\n[Ghostscraper] Failed to install {browser_type} browser. Error code: {e.returncode}")

        if os.name == 'posix' and os.geteuid() != 0:
            Logger.note("[Ghostscraper] You may need to run with sudo privileges.")
            Logger.note(f"[Ghostscraper] Try: sudo playwright install {browser_type}")
        else:
            Logger.note("[Ghostscraper] You may need administrator privileges.")
            Logger.note(f"[Ghostscraper] Try running: playwright install {browser_type}")

        return False

    except Exception as e:
        Logger.note(f"\n[Ghostscraper] An unexpected error occurred: {str(e)}")
        Logger.note(f"[Ghostscraper] Please run 'playwright install {browser_type}' manually.")
        return False