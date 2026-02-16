"""
Headless browser helper using Playwright.
Provides a simple fetch_js(url) function that returns rendered HTML.
Lazy-loads browser on first use. Falls back gracefully if Playwright not installed.
"""

import os

_browser = None
_playwright = None
_available = None


def is_available():
    """Check if Playwright is installed."""
    global _available
    if _available is not None:
        return _available
    try:
        from playwright.sync_api import sync_playwright
        _available = True
    except ImportError:
        _available = False
        print("  [Headless] Playwright not installed — JS-rendered scrapers disabled")
    return _available


def _get_browser():
    """Lazy-init browser on first use."""
    global _browser, _playwright
    if _browser:
        return _browser
    if not is_available():
        return None

    from playwright.sync_api import sync_playwright

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",
        ]
    )
    print("  [Headless] Chromium browser started")
    return _browser


def fetch_js(url, wait_for=None, timeout=30000):
    """
    Fetch a URL with a headless browser, wait for JS to render, return HTML.
    
    Args:
        url: URL to fetch
        wait_for: CSS selector to wait for (e.g. '.event-card')
        timeout: max wait time in ms (default 30s)
    
    Returns:
        Rendered HTML string, or empty string on failure.
    """
    browser = _get_browser()
    if not browser:
        return ""

    page = None
    try:
        page = browser.new_page(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page.set_default_timeout(timeout)

        page.goto(url, wait_until="networkidle", timeout=timeout)

        if wait_for:
            try:
                page.wait_for_selector(wait_for, timeout=15000)
            except Exception:
                pass  # Continue even if selector not found

        # Small extra wait for any lazy-loaded content
        page.wait_for_timeout(2000)

        html = page.content()
        return html

    except Exception as e:
        print(f"  [Headless] Error fetching {url}: {e}")
        return ""

    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def cleanup():
    """Close browser. Call on shutdown."""
    global _browser, _playwright
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None
