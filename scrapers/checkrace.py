"""
Checkrace scraper — uses Google's search index.
Checkrace (run.checkrace.com) is a fully JS-rendered SPA with no public API.
Google has already rendered these pages and indexed the content.
We search Google for 'site:run.checkrace.com/event' and parse event data
from the search result titles and snippets.
"""

import re
from datetime import datetime
from scrapers.google_index import (
    google_search, extract_date_from_text, extract_province_from_text,
    extract_distances_from_text, extract_year_from_text, detect_type,
)

BASE_URL = "https://run.checkrace.com"


def scrape():
    races = []
    seen_urls = set()
    current_year = datetime.utcnow().year

    # Search for current and upcoming events
    queries = [
        f"site:run.checkrace.com/event 2026",
        f"site:run.checkrace.com/event 2025",
        f"site:run.checkrace.com/event วิ่ง เปิดรับสมัคร",
    ]

    all_results = []
    for q in queries:
        results = google_search(q, num_results=20)
        all_results.extend(results)
        print(f"    [Checkrace] Google '{q}' → {len(results)} results")

    for r in all_results:
        url = r["url"]

        # Only process event pages
        if "/event/" not in url or url in seen_urls:
            continue
        seen_urls.add(url)

        # Extract slug from URL
        slug_m = re.search(r'/event/([^/?#]+)', url)
        if not slug_m:
            continue
        slug = slug_m.group(1)

        title = r["title"]
        snippet = r.get("snippet", "")
        combined = f"{title} {snippet}"

        # Clean title — remove " - Checkrace" etc
        name = re.sub(r'\s*[-–|:]\s*(Checkrace|Run\.checkrace\.com|ระบบ.*)$', '', title, flags=re.IGNORECASE).strip()
        if not name or len(name) < 3:
            name = title

        # Skip past events — check year
        year = extract_year_from_text(combined)
        if year and year < current_year:
            continue

        # Extract date
        date = extract_date_from_text(combined)

        # Extract province
        province = extract_province_from_text(combined)

        # Extract distances
        distances = extract_distances_from_text(combined)

        # Detect type
        race_type = detect_type(name)

        # Build race entry
        race = {
            "id": f"checkrace-{slug}",
            "name": name,
            "nameTh": "",
            "date": date,
            "location": province or "",
            "province": province,
            "type": race_type,
            "distances": distances,
            "url": url,
            "image": "",
            "source": "Checkrace",
            "tags": [],
        }

        # If name looks Thai, put it as nameTh too
        if re.search(r'[\u0E00-\u0E7F]', name):
            race["nameTh"] = name

        races.append(race)

    # Deduplicate by slug (different queries may find same event)
    deduped = {}
    for r in races:
        rid = r["id"]
        if rid not in deduped:
            deduped[rid] = r
        else:
            # Merge: prefer the one with more data
            existing = deduped[rid]
            if existing["date"] == "TBA" and r["date"] != "TBA":
                existing["date"] = r["date"]
            if not existing["province"] and r["province"]:
                existing["province"] = r["province"]
            if not existing["distances"] and r["distances"]:
                existing["distances"] = r["distances"]

    races = list(deduped.values())
    print(f"    [Checkrace] {len(races)} events from Google index")
    return races
