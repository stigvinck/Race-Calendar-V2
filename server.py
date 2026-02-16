"""
Thailand Race Finder — Lightweight server
Serves the static site + runs scrapers on a schedule.
Tracks dateFound/lastSeen for each race across scrapes.
Includes self-ping to prevent Render free plan spin-down.
"""

import os
import json
import threading
import time
import http.server
import socketserver
import urllib.request
from datetime import datetime

from scrapers.runlah import scrape as scrape_runlah
from scrapers.gotorace import scrape as scrape_gotorace

PORT = int(os.environ.get("PORT", 10000))
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6)) * 3600
RACES_PATH = os.path.join(DATA_DIR, "public", "races.json")

# Set this in Render environment variables, e.g. https://your-app.onrender.com
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PING_INTERVAL = 10 * 60  # 10 minutes (Render sleeps at 15 min idle)


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
            r["dateFound"] = existing[rid].get("dateFound", now)
        else:
            r["dateFound"] = now

        r["lastSeen"] = now
        merged[rid] = r

    # Keep races from previous data that weren't in this scrape
    for rid, old_race in existing.items():
        if rid not in merged:
            old_race.setdefault("status", "unknown")
            merged[rid] = old_race

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
    """Run scrapers immediately on startup, then on interval."""
    while True:
        print(f"\n{'='*50}")
        print(f"Scraping at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*50}")
        run_all_scrapers()
        print(f"Next scrape in {SCRAPE_INTERVAL // 3600} hours\n")
        time.sleep(SCRAPE_INTERVAL)


def keep_alive_loop():
    """Ping ourselves every 10 min to prevent Render free-plan spin-down.
    Uses RENDER_EXTERNAL_URL env var (must be set manually on free plan)."""
    url = RENDER_URL
    if not url:
        print("⚠ RENDER_EXTERNAL_URL not set — self-ping disabled.")
        print("  Set it in Render dashboard → Environment → Add Variable:")
        print("  RENDER_EXTERNAL_URL = https://your-app.onrender.com")
        return

    ping_url = url.rstrip("/") + "/races.json"
    print(f"🏓 Keep-alive pinging {ping_url} every {PING_INTERVAL // 60} min")

    while True:
        time.sleep(PING_INTERVAL)
        try:
            req = urllib.request.Request(ping_url, headers={
                "User-Agent": "self-ping/keep-alive"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                _ = resp.read(100)
        except Exception:
            pass  # Network hiccup, will retry next cycle


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(DATA_DIR, "public"), **kwargs)

    def log_message(self, format, *args):
        msg = str(args)
        if "404" in msg or "500" in msg:
            super().log_message(format, *args)


if __name__ == "__main__":
    # Start scraper thread — runs immediately then every N hours
    t1 = threading.Thread(target=scraper_loop, daemon=True)
    t1.start()

    # Start keep-alive thread — pings self every 10 min
    t2 = threading.Thread(target=keep_alive_loop, daemon=True)
    t2.start()

    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"🌐 Serving on port {PORT}")
        httpd.serve_forever()
