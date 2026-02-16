"""
Thailand Race Finder — Lightweight server
Serves the static site + runs scrapers on a schedule.
Tracks dateFound/lastSeen for each race across scrapes.
Filters out past races. Includes source registry.
Self-pings to prevent Render free plan spin-down.
"""

import os
import json
import threading
import time
import http.server
import socketserver
import urllib.request
from datetime import datetime, timedelta

from scrapers.runlah import scrape as scrape_runlah
from scrapers.gotorace import scrape as scrape_gotorace
from scrapers.jogandjoy import scrape as scrape_jaj
from scrapers.thairun import scrape as scrape_thairun
from scrapers.finishers import scrape as scrape_finishers
from scrapers.pho3nix import scrape as scrape_pho3nix
from scrapers.cycloworld import scrape as scrape_cyclo
from scrapers.xrace import scrape as scrape_xrace
from scrapers.oceanman import scrape as scrape_ocean

PORT = int(os.environ.get("PORT", 10000))
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6)) * 3600
RACES_PATH = os.path.join(DATA_DIR, "public", "races.json")

# Set this in Render environment variables
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PING_INTERVAL = 10 * 60  # 10 minutes

# ── Source registry (shown in frontend modal) ──
SOURCE_REGISTRY = [
    {
        "name": "Runlah",
        "url": "runlah.com",
        "desc": "Largest Thai running calendar — all 77 provinces scraped (EN + TH)",
        "status": "active"
    },
    {
        "name": "GoToRace",
        "url": "gotorace.com",
        "desc": "Curated Thailand events — road, trail, triathlon, cycling",
        "status": "active"
    },
    {
        "name": "JogAndJoy",
        "url": "jogandjoy.com",
        "desc": "Thailand running calendar with event listings",
        "status": "active"
    },
    {
        "name": "Thai.Run",
        "url": "thai.run",
        "desc": "Thai race registration platform & event calendar",
        "status": "active"
    },
    {
        "name": "Finishers",
        "url": "finishers.com",
        "desc": "Asia-wide race aggregator — Thailand & SEA events",
        "status": "active"
    },
    {
        "name": "Pho3nix Kids",
        "url": "pho3nixkidsthailand.com",
        "desc": "Kids triathlon & duathlon series across Thailand",
        "status": "active"
    },
    {
        "name": "CycloWorld",
        "url": "cycloworld.cc",
        "desc": "Cycling race directory — gran fondo & road races in Thailand",
        "status": "active"
    },
    {
        "name": "XRace Asia",
        "url": "xraceasia.com",
        "desc": "Obstacle & adventure race series — Thailand events",
        "status": "active"
    },
    {
        "name": "Oceanman",
        "url": "oceanmanswim.com",
        "desc": "Open water swimming events — Krabi, Thailand",
        "status": "active"
    },
    {
        "name": "WorldsMarathons",
        "url": "worldsmarathons.com",
        "desc": "Global marathon directory (JS-rendered — needs headless browser)",
        "status": "blocked"
    },
    {
        "name": "Ahotu",
        "url": "ahotu.com",
        "desc": "Global endurance calendar (JS-rendered — needs headless browser)",
        "status": "blocked"
    },
    {
        "name": "IRONMAN",
        "url": "ironman.com",
        "desc": "IRONMAN & 70.3 Thailand/SEA events (JS-rendered SPA)",
        "status": "blocked"
    },
]


def is_past(date_str):
    """Check if a date string is in the past. TBA/TBD dates are NOT past."""
    if not date_str:
        return False
    upper = date_str.upper().strip()
    if upper in ("TBA", "TBD", "UNKNOWN", ""):
        return False
    try:
        race_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return race_date.date() < datetime.utcnow().date()
    except (ValueError, TypeError):
        return False


def load_existing():
    """Load existing races.json to preserve dateFound values."""
    try:
        with open(RACES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {r["id"]: r for r in data.get("races", []) if "id" in r}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_all_scrapers():
    """Run all scrapers, merge, filter past, write races.json."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = load_existing()
    fresh_races = []

    # ── Register scrapers here ─────────────────────
    scrapers = [
        ("Runlah", scrape_runlah),
        ("GoToRace", scrape_gotorace),
        ("JogAndJoy", scrape_jaj),
        ("ThaiRun", scrape_thairun),
        ("Finishers", scrape_finishers),
        ("Pho3nix", scrape_pho3nix),
        ("CycloWorld", scrape_cyclo),
        ("XRace", scrape_xrace),
        ("Oceanman", scrape_ocean),
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

        # Skip past races
        if is_past(r.get("date", "")):
            continue

        if rid in existing:
            r["dateFound"] = existing[rid].get("dateFound", now)
        else:
            r["dateFound"] = now

        r["lastSeen"] = now
        merged[rid] = r

    # Keep existing races that weren't in this scrape (if not past)
    for rid, old_race in existing.items():
        if rid not in merged and not is_past(old_race.get("date", "")):
            old_race.setdefault("status", "unknown")
            merged[rid] = old_race

    # Sort by date (TBA at the end)
    def sort_key(r):
        d = r.get("date", "")
        if not d or d.upper() in ("TBA", "TBD", "UNKNOWN"):
            return "9999-99-99"
        return d

    races_list = sorted(merged.values(), key=sort_key)

    output = {
        "lastUpdated": now,
        "totalSources": len(scrapers),
        "sources": SOURCE_REGISTRY,
        "races": races_list,
    }

    with open(RACES_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    past_filtered = len(fresh_races) - len([r for r in fresh_races if not is_past(r.get("date", ""))])
    print(f"✓ Saved {len(races_list)} races ({len(fresh_races)} fresh, {past_filtered} past filtered out)")


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
    """Ping ourselves every 10 min to prevent Render free-plan spin-down."""
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
            pass


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(DATA_DIR, "public"), **kwargs)

    def log_message(self, format, *args):
        msg = str(args)
        if "404" in msg or "500" in msg:
            super().log_message(format, *args)


if __name__ == "__main__":
    t1 = threading.Thread(target=scraper_loop, daemon=True)
    t1.start()

    t2 = threading.Thread(target=keep_alive_loop, daemon=True)
    t2.start()

    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"🌐 Serving on port {PORT}")
        httpd.serve_forever()
