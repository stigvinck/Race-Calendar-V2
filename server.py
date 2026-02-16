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
from scrapers.spartan import scrape as scrape_spartan
from scrapers.runningconnect import scrape as scrape_rc
from scrapers.granfondoguide import scrape as scrape_gfg
from scrapers.muangthai import scrape as scrape_mtl
from scrapers.lagunaphuket import scrape as scrape_lpt
from scrapers.checkrace import scrape as scrape_checkrace
from scrapers.racethairun import scrape as scrape_racethairun

# ── Version ──────────────────────────────────────
VERSION = "0.8.1"

# ── Config ───────────────────────────────────────
PORT = int(os.environ.get("PORT", 10000))
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6)) * 3600
RACES_PATH = os.path.join(DATA_DIR, "public", "races.json")
STATUS_PATH = os.path.join(DATA_DIR, "public", "scrape-status.json")

RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PING_INTERVAL = 10 * 60

# ── Changelog ────────────────────────────────────
CHANGELOG = [
    {
        "version": "0.8.1",
        "date": "2026-02-16",
        "changes": [
            "Version number now shows immediately on page load (before scrape completes)",
            "Card/Table view toggle — switch between visual cards and compact table",
            "Table view: sortable columns, no images, compact layout for scanning",
            "Laguna Phuket Tri: fixed fallback date (Nov 15, 2026 — 30th edition)",
            "Headless browser status shown in scrape bar ('headless browser')",
        ]
    },
    {
        "version": "0.8.0",
        "date": "2026-02-16",
        "changes": [
            "Added Playwright headless browser — unlocks JS-rendered sites",
            "Added Checkrace scraper (run.checkrace.com) — Thailand's #1 registration platform",
            "Added race.thai.run scraper — Thai.Run active event listings",
            "Added Laguna Phuket Triathlon scraper — tri, sprint, duathlon, fun run, OWS",
            "16 active scrapers, 4 blocked sources",
            "Dockerfile updated with Chromium for headless browsing",
        ]
    },
    {
        "version": "0.7.0",
        "date": "2026-02-16",
        "changes": [
            "Added Muangthai Triathlon scraper — Eco Hero Super Series (3 events/year)",
            "Runlah now shows live province-by-province progress: 'Runlah (23/77)' in status bar",
            "Progress updates every 5 provinces instead of every 15",
            "13 active scrapers, 7 blocked sources",
        ]
    },
    {
        "version": "0.6.0",
        "date": "2026-02-16",
        "changes": [
            "Added GranFondoGuide scraper — Dustman gravel, GFNY Krabi, Tour of Phuket, Chiang Mai Gran Fondo",
            "12 active scrapers, 7 blocked sources tracked",
            "Removed AI enrichment module (simplifying stack)",
            "Added Checkrace and race.thai.run to blocked sources list (JS-rendered SPAs)",
        ]
    },
    {
        "version": "0.5.2",
        "date": "2026-02-16",
        "changes": [
            "Restored full bilingual scraping (EN + TH) for Runlah — never skip Thai data",
            "Reduced inter-request delay to 0.15s for faster scraping while staying polite",
            "Thai race names preserved as nameTh field for AI enrichment",
            "Status bar shows '77 provinces × EN+TH — takes ~2 min' for Runlah",
        ]
    },
    {
        "version": "0.5.1",
        "date": "2026-02-16",
        "changes": [
            "Runlah scraper 2x faster: EN-only pass (was EN+TH), reduced delays",
            "Scrape status bar shows context hints for slow scrapers (e.g. '77 provinces — takes ~1 min')",
            "Timing shown per-scraper in logs",
        ]
    },
    {
        "version": "0.5.0",
        "date": "2026-02-16",
        "changes": [
            "Added Spartan Thailand scraper (th.spartan.com) — OCR obstacle races",
            "Added RunningConnect scraper — UTMB Thailand series, trail & ultra events",
            "11 active scrapers, 4 blocked sources tracked",
            "AI status badge now shows ON (green) or OFF (red) — always visible",
            "Version number in zip filename for easier tracking",
            "Improved scrape status bar with real-time progress",
        ]
    },
    {
        "version": "0.4.0",
        "date": "2026-02-16",
        "changes": [
            "Added version numbering + changelog",
            "Live scrape status indicator on frontend",
            "AI enrichment module (Claude Sonnet) — translates Thai names, deduplicates, improves classification",
            "9 active scrapers: Runlah, GoToRace, JogAndJoy, Thai.Run, Finishers, Pho3nix, CycloWorld, XRace, Oceanman",
            "Source tag moved from card image to footer link",
            "Toggled-off filter buttons now visually faded",
        ]
    },
    {
        "version": "0.3.0",
        "date": "2026-02-16",
        "changes": [
            "Expanded to 9 scrapers (added Pho3nix, CycloWorld, XRace, Oceanman)",
            "Past races automatically filtered out",
            "TBD/TBA date toggle filter",
            "Sources popup showing all tracked sites",
            "Self-ping keep-alive for Render free tier",
        ]
    },
    {
        "version": "0.2.0",
        "date": "2026-02-15",
        "changes": [
            "Rebuilt Runlah scraper to cover all 77 Thai provinces",
            "Rebuilt GoToRace scraper with correct pagination",
            "Removed WorldsMarathons and Ahotu (JS-rendered SPAs)",
            "Bilingual scraping (EN + TH) for better coverage",
            "Province-based location detection",
        ]
    },
    {
        "version": "0.1.0",
        "date": "2026-02-14",
        "changes": [
            "Initial release — Thailand Race Finder",
            "Card-based UI with type/location/time filters",
            "Runlah + GoToRace scrapers",
            "Auto-scrape every 6 hours",
        ]
    },
]

# ── Live scrape status (shared between threads) ──
scrape_status = {
    "state": "idle",          # idle | scraping | done
    "startedAt": None,
    "currentSource": None,
    "sourcesTotal": 0,
    "sourcesDone": 0,
    "racesFound": 0,
    "lastCompleted": None,
    "log": [],                # last few status messages
}
scrape_lock = threading.Lock()


def update_status(**kwargs):
    """Thread-safe status update."""
    with scrape_lock:
        scrape_status.update(kwargs)
        scrape_status["version"] = VERSION
        # Write to a small JSON file the frontend can poll
        try:
            with open(STATUS_PATH, "w") as f:
                json.dump(scrape_status, f)
        except Exception:
            pass


def log_status(msg):
    """Add a log message to scrape status."""
    with scrape_lock:
        scrape_status["log"].append(msg)
        if len(scrape_status["log"]) > 20:
            scrape_status["log"] = scrape_status["log"][-20:]
        try:
            with open(STATUS_PATH, "w") as f:
                json.dump(scrape_status, f)
        except Exception:
            pass


# ── Source registry ──────────────────────────────
SOURCE_REGISTRY = [
    {"name": "Runlah", "url": "runlah.com", "desc": "Largest Thai running calendar — all 77 provinces scraped (EN + TH)", "status": "active"},
    {"name": "GoToRace", "url": "gotorace.com", "desc": "Curated Thailand events — road, trail, triathlon, cycling", "status": "active"},
    {"name": "JogAndJoy", "url": "jogandjoy.com", "desc": "Thailand running calendar with event listings", "status": "active"},
    {"name": "Thai.Run", "url": "thai.run", "desc": "Thai race registration platform & event calendar", "status": "active"},
    {"name": "Finishers", "url": "finishers.com", "desc": "Asia-wide race aggregator — Thailand & SEA events", "status": "active"},
    {"name": "Pho3nix Kids", "url": "pho3nixkidsthailand.com", "desc": "Kids triathlon & duathlon series across Thailand", "status": "active"},
    {"name": "CycloWorld", "url": "cycloworld.cc", "desc": "Cycling race directory — gran fondo & road races in Thailand", "status": "active"},
    {"name": "XRace Asia", "url": "xraceasia.com", "desc": "Obstacle & adventure race series — Thailand events", "status": "active"},
    {"name": "Oceanman", "url": "oceanmanswim.com", "desc": "Open water swimming events — Krabi, Thailand", "status": "active"},
    {"name": "Spartan Thailand", "url": "th.spartan.com", "desc": "Spartan OCR — Sprint, Super, Beast obstacle races in Thailand", "status": "active"},
    {"name": "RunningConnect", "url": "runningconnect.com", "desc": "Trail & ultra events incl. UTMB Thailand series (Amazean Jungle, Chiang Mai)", "status": "active"},
    {"name": "GranFondoGuide", "url": "granfondoguide.com", "desc": "Cycling events — Dustman gravel, GFNY Krabi, Tour of Phuket, gran fondos", "status": "active"},
    {"name": "Muangthai Triathlon", "url": "gotorace.com/mtl*", "desc": "Muangthai Triathlon Eco Hero Super Series — 3 events/year across Thailand", "status": "active"},
    {"name": "Laguna Phuket Tri", "url": "lagunaphukettri.com", "desc": "Laguna Phuket Triathlon weekend — triathlon, sprint, duathlon, fun run, OWS", "status": "active"},
    {"name": "Checkrace", "url": "run.checkrace.com", "desc": "Thailand's #1 race registration platform — hundreds of Thai races (headless browser)", "status": "active"},
    {"name": "race.thai.run", "url": "race.thai.run", "desc": "Thai.Run registration system — active event listings (headless browser)", "status": "active"},
    {"name": "WorldsMarathons", "url": "worldsmarathons.com", "desc": "Global marathon directory (JS-rendered — needs headless browser)", "status": "blocked"},
    {"name": "Ahotu", "url": "ahotu.com", "desc": "Global endurance calendar (JS-rendered — needs headless browser)", "status": "blocked"},
    {"name": "IRONMAN", "url": "ironman.com", "desc": "IRONMAN & 70.3 Thailand/SEA events (JS-rendered SPA)", "status": "blocked"},
    {"name": "MarathonGuide", "url": "marathonguide.com", "desc": "International marathon directory (403 — access blocked)", "status": "blocked"},
]


def is_past(date_str):
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
    try:
        with open(RACES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {r["id"]: r for r in data.get("races", []) if "id" in r}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_all_scrapers():
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = load_existing()
    fresh_races = []

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
        ("Spartan", scrape_spartan),
        ("RunningConnect", scrape_rc),
        ("GranFondoGuide", scrape_gfg),
        ("Muangthai", scrape_mtl),
        ("LagunaPhkTri", scrape_lpt),
        ("Checkrace", scrape_checkrace),
        ("race.thai.run", scrape_racethairun),
    ]

    update_status(
        state="scraping",
        startedAt=now,
        currentSource=None,
        sourcesTotal=len(scrapers),
        sourcesDone=0,
        racesFound=0,
        log=[],
    )
    log_status("Scrape started at " + now)

    for i, (name, scraper_fn) in enumerate(scrapers):
        update_status(currentSource=name, sourcesDone=i)
        log_status("Scraping " + name + "...")
        try:
            t0 = time.time()
            # Pass progress callback to scrapers that support it
            if name == "Runlah":
                def runlah_progress(prov_done, prov_total, race_count):
                    log_status(f"Runlah: {prov_done}/{prov_total} provinces, {race_count} races")
                    update_status(currentSource=f"Runlah ({prov_done}/{prov_total})")
                races = scraper_fn(progress_cb=runlah_progress)
            else:
                races = scraper_fn()
            elapsed = round(time.time() - t0, 1)
            print(f"  [{name}] Found {len(races)} races ({elapsed}s)")
            log_status(name + ": " + str(len(races)) + " races (" + str(elapsed) + "s)")
            fresh_races.extend(races)
            update_status(racesFound=len(fresh_races))
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            log_status(name + ": ERROR - " + str(e)[:80])

    # Merge
    merged = {}
    for r in fresh_races:
        rid = r.get("id", "")
        if not rid:
            continue
        if is_past(r.get("date", "")):
            continue
        if rid in existing:
            r["dateFound"] = existing[rid].get("dateFound", now)
        else:
            r["dateFound"] = now
        r["lastSeen"] = now
        merged[rid] = r

    for rid, old_race in existing.items():
        if rid not in merged and not is_past(old_race.get("date", "")):
            old_race.setdefault("status", "unknown")
            merged[rid] = old_race

    def sort_key(r):
        d = r.get("date", "")
        if not d or d.upper() in ("TBA", "TBD", "UNKNOWN"):
            return "9999-99-99"
        return d

    races_list = sorted(merged.values(), key=sort_key)

    output = {
        "version": VERSION,
        "lastUpdated": now,
        "totalSources": len(scrapers),
        "sources": SOURCE_REGISTRY,
        "changelog": CHANGELOG,
        "races": races_list,
    }

    with open(RACES_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    past_filtered = len(fresh_races) - len([r for r in fresh_races if not is_past(r.get("date", ""))])
    print(f"✓ v{VERSION} — Saved {len(races_list)} races ({len(fresh_races)} fresh, {past_filtered} past filtered)")

    update_status(
        state="idle",
        currentSource=None,
        sourcesDone=len(scrapers),
        racesFound=len(races_list),
        lastCompleted=now,
    )
    log_status("Done — " + str(len(races_list)) + " races saved")


def scraper_loop():
    while True:
        print(f"\n{'='*50}")
        print(f"v{VERSION} — Scraping at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*50}")
        run_all_scrapers()
        print(f"Next scrape in {SCRAPE_INTERVAL // 3600} hours\n")
        time.sleep(SCRAPE_INTERVAL)


def keep_alive_loop():
    url = RENDER_URL
    if not url:
        print("⚠ RENDER_EXTERNAL_URL not set — self-ping disabled.")
        return

    ping_url = url.rstrip("/") + "/races.json"
    print(f"🏓 Keep-alive pinging {ping_url} every {PING_INTERVAL // 60} min")

    while True:
        time.sleep(PING_INTERVAL)
        try:
            req = urllib.request.Request(ping_url, headers={"User-Agent": "self-ping/keep-alive"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                _ = resp.read(100)
        except Exception:
            pass


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(DATA_DIR, "public"), **kwargs)

    def do_GET(self):
        if self.path == "/api/status":
            self._handle_status()
            return
        super().do_GET()

    def _handle_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            with open(RACES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            status = {
                "version": VERSION,
                "totalRaces": len(data.get("races", [])),
                "lastUpdated": data.get("lastUpdated", "never"),
                "totalSources": data.get("totalSources", 0),
                "scrape": scrape_status,
            }
        except Exception:
            status = {"version": VERSION, "error": "No data yet", "scrape": scrape_status}
        self.wfile.write(json.dumps(status, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        msg = str(args)
        if "/api/" in str(args[0]) or "404" in msg or "500" in msg:
            super().log_message(format, *args)


if __name__ == "__main__":
    import atexit
    from scrapers.headless import cleanup as headless_cleanup
    atexit.register(headless_cleanup)

    print(f"🏃 Thailand Race Finder v{VERSION}")

    # Write initial scrape status
    update_status(state="starting", startedAt=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

    t1 = threading.Thread(target=scraper_loop, daemon=True)
    t1.start()

    t2 = threading.Thread(target=keep_alive_loop, daemon=True)
    t2.start()

    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"🌐 Serving on port {PORT}")
        httpd.serve_forever()
