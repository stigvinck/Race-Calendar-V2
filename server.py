"""
CM Races — Lightweight server
Serves the static site + runs scrapers on a schedule.
Tracks dateFound/lastSeen for each race across scrapes.
"""

import os
import json
import threading
import time
import http.server
import socketserver
from datetime import datetime

from scrapers.runlah import scrape as scrape_runlah
from scrapers.gotorace import scrape as scrape_gotorace
from scrapers.worldsmarathons import scrape as scrape_wm
from scrapers.ahotu import scrape as scrape_ahotu

PORT = int(os.environ.get("PORT", 10000))
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6)) * 3600
RACES_PATH = os.path.join(DATA_DIR, "public", "races.json")


def load_existing():
    """Load existing races.json to preserve dateFound values."""
    try:
        with open(RACES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {r["id"]: r for r in data.get("races", []) if "id" in r}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_all_scrapers():
    """Run all scrapers, merge with existing data, write races.json."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = load_existing()
    fresh_races = []

    # ── Register scrapers here ─────────────────────
    scrapers = [
        ("Runlah", scrape_runlah),
        ("GoToRace", scrape_gotorace),
        ("WorldsMarathons", scrape_wm),
        ("Ahotu", scrape_ahotu),
    ]

    for name, scraper_fn in scrapers:
        try:
            races = scraper_fn()
            print(f"  [{name}] Found {len(races)} races")
            fresh_races.extend(races)
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")

    # Merge: preserve dateFound, update lastSeen
    merged = {}
    for r in fresh_races:
        rid = r.get("id", "")
        if not rid:
            continue

        if rid in existing:
            # Preserve dateFound from previous scrape
            r["dateFound"] = existing[rid].get("dateFound", now)
        else:
            # First time we've seen this race
            r["dateFound"] = now

        r["lastSeen"] = now
        merged[rid] = r

    # Also keep races from previous data that weren't in this scrape
    # (they may have been removed from the source, but we keep them)
    for rid, old_race in existing.items():
        if rid not in merged:
            old_race.setdefault("status", "unknown")
            merged[rid] = old_race

    # Sort by date
    races_list = sorted(merged.values(), key=lambda r: r.get("date", ""))

    output = {
        "lastUpdated": now,
        "totalSources": len(scrapers),
        "races": races_list,
    }

    with open(RACES_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved {len(races_list)} races ({len(fresh_races)} fresh, {len(existing)} existing)")


def scraper_loop():
    """Run scrapers immediately, then on interval."""
    while True:
        print(f"\n{'='*50}")
        print(f"Scraping at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*50}")
        run_all_scrapers()
        print(f"Next scrape in {SCRAPE_INTERVAL // 3600} hours\n")
        time.sleep(SCRAPE_INTERVAL)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(DATA_DIR, "public"), **kwargs)

    def log_message(self, format, *args):
        if "404" in str(args) or "500" in str(args):
            super().log_message(format, *args)


if __name__ == "__main__":
    t = threading.Thread(target=scraper_loop, daemon=True)
    t.start()

    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"🌐 Serving on port {PORT}")
        httpd.serve_forever()
