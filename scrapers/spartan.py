"""
Spartan Thailand scraper
Scrapes th.spartan.com for Thailand OCR events.
The main site is JS-rendered, so we try the tickets site and known schedule pages.
"""

import re
import urllib.request
import json
from datetime import datetime

URLS = [
    "https://th.spartan.com/en/race/find-race",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ThaiRaceFinder/1.0)",
    "Accept": "text/html,application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# Known Spartan Thailand typical venues/events
KNOWN_SPARTAN_EVENTS = [
    # These get refreshed if the site is scrapable; otherwise serve as baseline
]

def scrape():
    races = []

    # Try fetching the find-race page for any embedded JSON
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Look for embedded race data in script tags (Spartan uses Next.js/React)
            json_blocks = re.findall(r'\"events?\"\s*:\s*(\[.*?\])', html, re.DOTALL)
            for block in json_blocks:
                try:
                    events = json.loads(block)
                    for ev in events:
                        if not isinstance(ev, dict):
                            continue
                        # Filter for Thailand
                        country = ev.get("country", "") or ev.get("countryCode", "")
                        venue = ev.get("venue", "") or ev.get("location", "") or ""
                        name = ev.get("name", "") or ev.get("title", "") or ""

                        if "thailand" not in (country + venue + name).lower() and "th" != country.lower():
                            continue

                        date_str = ev.get("date", "") or ev.get("startDate", "") or ""
                        if date_str:
                            date_str = date_str[:10]

                        race = {
                            "id": f"spartan-{ev.get('id', name[:30])}".lower().replace(" ", "-"),
                            "name": name,
                            "date": date_str or "TBA",
                            "location": venue,
                            "province": detect_province(venue + " " + name),
                            "type": "obstacle",
                            "distances": extract_distances(ev),
                            "url": ev.get("url", "https://th.spartan.com/en/race/find-race"),
                            "image": ev.get("image", "") or ev.get("heroImage", ""),
                            "source": "Spartan",
                            "tags": ["obstacle", "spartan", "OCR"],
                        }
                        races.append(race)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Also look for structured data
            ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
            for ld in ld_blocks:
                try:
                    data = json.loads(ld)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") not in ("Event", "SportsEvent"):
                            continue
                        loc = item.get("location", {})
                        loc_name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                        if "thailand" not in (loc_name + item.get("name", "")).lower():
                            continue
                        date_str = (item.get("startDate", "") or "")[:10]
                        name = item.get("name", "Spartan Thailand")
                        race = {
                            "id": f"spartan-{name[:40]}".lower().replace(" ", "-"),
                            "name": name,
                            "date": date_str or "TBA",
                            "location": loc_name,
                            "province": detect_province(loc_name),
                            "type": "obstacle",
                            "distances": [],
                            "url": item.get("url", "https://th.spartan.com/en/race/find-race"),
                            "image": "",
                            "source": "Spartan",
                            "tags": ["obstacle", "spartan", "OCR"],
                        }
                        races.append(race)
                except (json.JSONDecodeError, TypeError):
                    pass

        except Exception as e:
            print(f"    [Spartan] Error fetching {url}: {e}")

    print(f"    [Spartan] Found {len(races)} races")
    return races


def detect_province(text):
    text_lower = text.lower()
    provinces = {
        "chiang mai": "Chiang Mai", "phuket": "Phuket", "pattaya": "Chon Buri",
        "chon buri": "Chon Buri", "khao yai": "Nakhon Ratchasima",
        "nakhon ratchasima": "Nakhon Ratchasima", "bangkok": "Bangkok",
        "hua hin": "Prachuap Khiri Khan", "koh samui": "Surat Thani",
        "krabi": "Krabi", "chiang rai": "Chiang Rai",
    }
    for key, prov in provinces.items():
        if key in text_lower:
            return prov
    return ""


def extract_distances(ev):
    dists = []
    for key in ("distances", "raceTypes", "formats"):
        val = ev.get(key, [])
        if isinstance(val, list):
            for d in val:
                if isinstance(d, str):
                    dists.append(d)
                elif isinstance(d, dict):
                    dists.append(d.get("name", "") or d.get("distance", ""))
    return [d for d in dists if d]
