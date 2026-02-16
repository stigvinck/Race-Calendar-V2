"""
CM Races — Lightweight server
Serves the static site + runs scrapers on a schedule.
"""

import os
import json
import threading
import time
import http.server
import socketserver
from datetime import datetime

# Import all scrapers
from scrapers.runlah import scrape as scrape_runlah

PORT = int(os.environ.get("PORT", 10000))
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6)) * 3600


def run_all_scrapers():
    """Run all scrapers and merge results into races.json"""
    all_races = []

    # ── Add scrapers here ──────────────────────────
    scrapers = [
        ("Runlah", scrape_runlah),
        # ("ChiangMaiLife", scrape_chiangmailife),
        # ("Facebook", scrape_facebook),
    ]

    for name, scraper_fn in scrapers:
        try:
            races = scraper_fn()
            print(f"  [{name}] Found {len(races)} races")
            all_races.extend(races)
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in all_races:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    # Sort by date
    unique.sort(key=lambda r: r.get("date", ""))

    # Write to races.json
    output = {
        "lastUpdated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "races": unique,
    }

    path = os.path.join(DATA_DIR, "public", "races.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved {len(unique)} races to races.json at {output['lastUpdated']}")


def scraper_loop():
    """Run scrapers immediately, then every SCRAPE_INTERVAL seconds."""
    while True:
        print(f"\n{'='*50}")
        print(f"Running scrapers at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*50}")
        run_all_scrapers()
        print(f"Next scrape in {SCRAPE_INTERVAL // 3600} hours\n")
        time.sleep(SCRAPE_INTERVAL)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files from /public, suppress noisy logs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(DATA_DIR, "public"), **kwargs)

    def log_message(self, format, *args):
        # Only log errors, not every request
        if "404" in str(args) or "500" in str(args):
            super().log_message(format, *args)


if __name__ == "__main__":
    # Start scraper in background thread
    t = threading.Thread(target=scraper_loop, daemon=True)
    t.start()

    # Start web server
    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"🌐 Serving on port {PORT}")
        httpd.serve_forever()
