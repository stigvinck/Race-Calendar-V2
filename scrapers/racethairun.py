"""
race.thai.run scraper — uses Google's search index.
race.thai.run is a fully JS-rendered SPA with no public API.
Google has already rendered these pages and indexed the content.

Note: Some events overlap with the Thai.Run (thai.run/events) scraper.
Deduplication happens at the server level.
"""

import re
from datetime import datetime
from scrapers.google_index import (
    google_search, extract_date_from_text, extract_province_from_text,
    extract_distances_from_text, extract_year_from_text, detect_type,
)

BASE_URL = "https://race.thai.run"


def scrape():
    races = []
    seen_urls = set()
    current_year = datetime.utcnow().year

    # Search for current and upcoming events
    queries = [
        f"site:race.thai.run 2026",
        f"site:race.thai.run 2025 วิ่ง",
        f"site:race.thai.run marathon run trail",
    ]

    all_results = []
    for q in queries:
        results = google_search(q, num_results=20)
        all_results.extend(results)
        print(f"    [race.thai.run] Google '{q}' → {len(results)} results")

    for r in all_results:
        url = r["url"]

        # Only process event pages (skip homepage, static pages)
        if url in seen_urls:
            continue
        # Must be race.thai.run/someslug (not subpaths or query strings for non-events)
        if not re.match(r'https?://race\.thai\.run/[a-zA-Z0-9_-]+$', url):
            continue
        seen_urls.add(url)

        # Extract slug
        slug_m = re.search(r'race\.thai\.run/([^/?#]+)', url)
        if not slug_m:
            continue
        slug = slug_m.group(1)

        # Skip non-event pages
        skip_slugs = {"about", "contact", "login", "register", "privacy", "terms", "help", "faq"}
        if slug.lower() in skip_slugs:
            continue

        title = r["title"]
        snippet = r.get("snippet", "")
        combined = f"{title} {snippet}"

        # Clean title
        name = re.sub(r'\s*[-–|:]\s*(race\.thai\.run|ระบบ.*)$', '', title, flags=re.IGNORECASE).strip()
        if not name or len(name) < 3:
            name = title

        # Skip past events
        year = extract_year_from_text(combined)
        if year and year < current_year:
            continue

        # Filter out non-Thailand events (Laos, Malaysia etc) unless interesting
        lower = combined.lower()
        non_thai = ["lao pdr", "laos", "malaysia", "vietnam", "cambodia", "myanmar", "singapore"]
        if any(x in lower for x in non_thai):
            # Still include if it says Thailand too, otherwise skip
            if "thailand" not in lower and "ไทย" not in combined:
                continue

        # Extract date
        date = extract_date_from_text(combined)

        # Extract province
        province = extract_province_from_text(combined)

        # Extract distances
        distances = extract_distances_from_text(combined)

        # Detect type
        race_type = detect_type(name)

        race = {
            "id": f"racethairun-{slug}",
            "name": name,
            "nameTh": "",
            "date": date,
            "location": province or "",
            "province": province,
            "type": race_type,
            "distances": distances,
            "url": url,
            "image": "",
            "source": "race.thai.run",
            "tags": [],
        }

        if re.search(r'[\u0E00-\u0E7F]', name):
            race["nameTh"] = name

        races.append(race)

    # Deduplicate
    deduped = {}
    for r in races:
        rid = r["id"]
        if rid not in deduped:
            deduped[rid] = r
        else:
            existing = deduped[rid]
            if existing["date"] == "TBA" and r["date"] != "TBA":
                existing["date"] = r["date"]
            if not existing["province"] and r["province"]:
                existing["province"] = r["province"]
            if not existing["distances"] and r["distances"]:
                existing["distances"] = r["distances"]

    races = list(deduped.values())
    print(f"    [race.thai.run] {len(races)} events from Google index")
    return races
