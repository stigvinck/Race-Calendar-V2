"""
Scraper: Finishers.com — Asia race aggregator
Scrapes Thailand event listings from the finishers.com platform.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

BASE = "https://www.finishers.com"
THAILAND_URL = BASE + "/en/destinations/asia/thailand"
# Also try paginated
URLS = [
    BASE + "/en/destinations/asia/thailand",
    BASE + "/en/event?country=thailand",
]

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

PROVINCE_KEYWORDS = {
    "Chiang Mai": ["chiang mai", "chiangmai", "เชียงใหม่", "doi suthep", "chiang dao"],
    "Bangkok": ["bangkok", "กรุงเทพ"],
    "Phuket": ["phuket", "ภูเก็ต", "laguna"],
    "Chiang Rai": ["chiang rai", "chiangrai"],
    "Chon Buri": ["chon buri", "chonburi", "pattaya", "bangsaen", "bang saen"],
    "Nakhon Ratchasima": ["nakhon ratchasima", "korat", "khao yai"],
    "Khon Kaen": ["khon kaen"],
    "Surat Thani": ["surat thani", "samui", "koh samui"],
    "Krabi": ["krabi"],
    "Prachuap Khiri Khan": ["prachuap", "hua hin", "sam roi yod"],
    "Songkhla": ["songkhla", "hat yai"],
    "Phetchabun": ["phetchabun", "khao kho"],
    "Nan": ["nan province", "nan city"],
    "Lampang": ["lampang"],
    "Sukhothai": ["sukhothai"],
    "Trang": ["trang"],
    "Rayong": ["rayong"],
    "Trat": ["trat"],
    "Mae Hong Son": ["mae hong son", "pai "],
    "Yala": ["yala", "betong"],
    "Nakhon Pathom": ["nakhon pathom"],
    "Prachin Buri": ["prachin buri"],
    "Nakhon Sawan": ["nakhon sawan"],
    "Nong Khai": ["nong khai"],
    "Phrae": ["phrae"],
}


def detect_province(text):
    lower = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return province
    return None


def detect_type(text):
    lower = text.lower()
    if "trail" in lower or "ultra" in lower:
        return "trail"
    if "triathlon" in lower or "ironman" in lower or "70.3" in lower or "duathlon" in lower:
        return "triathlon"
    if "cycling" in lower or "bike" in lower or "fondo" in lower:
        return "cycling"
    if "swim" in lower or "open water" in lower:
        return "swim"
    if "obstacle" in lower or "ocr" in lower or "spartan" in lower:
        return "obstacle"
    return "run"


def parse_date(text):
    if not text:
        return None
    text = text.strip()

    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)

    # DD Month YYYY or DD Mon YYYY
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)

    # Month DD, YYYY
    m = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)

    return None


def scrape():
    """Scrape finishers.com for Thailand races."""
    print("    [Finishers] Fetching Thailand pages...")
    races = []
    seen_ids = set()

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            if len(html) < 1000:
                print("    [Finishers] Page too short, might be SPA: %s" % url)
                continue

            # Extract races using regex patterns
            page_races = extract_races(html)
            for race in page_races:
                if race["id"] not in seen_ids:
                    seen_ids.add(race["id"])
                    races.append(race)

        except Exception as e:
            print("    [Finishers] Error fetching %s: %s" % (url, e))

    print("    [Finishers] Parsed %d races" % len(races))
    return races


def extract_races(html):
    """Extract races from HTML using regex and structure detection."""
    races = []

    # Pattern 1: Event cards with links
    # Look for <a href="/en/event/...">...</a> blocks
    event_pattern = re.compile(
        r'<a[^>]*href=["\'](/en/event/[^"\']+)["\'][^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )

    for match in event_pattern.finditer(html):
        event_path = match.group(1)
        block = match.group(2)

        # Clean HTML tags from block
        name = re.sub(r'<[^>]+>', ' ', block).strip()
        name = re.sub(r'\s+', ' ', name).strip()

        if len(name) < 3 or len(name) > 150:
            continue

        # Skip navigation/footer links
        if name.lower() in ("view", "details", "more", "see all"):
            continue

        url = BASE + event_path
        race_id = "fin-" + re.sub(r'[^a-z0-9]', '', event_path.lower()[:50])

        province = detect_province(name)
        race_type = detect_type(name)

        races.append({
            "id": race_id,
            "name": name,
            "date": "TBA",  # Will try to find date nearby
            "type": race_type,
            "province": province or "Unknown",
            "location": "",
            "url": url,
            "image": "",
            "source": "Finishers",
            "distances": [],
            "tags": [],
        })

    # Pattern 2: Look for date + name pairs near event cards
    # Try to find dates near each event
    date_pattern = re.compile(
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})',
        re.IGNORECASE
    )
    all_dates = date_pattern.findall(html)

    # Pattern 3: JSON-LD structured data
    jsonld_pattern = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL)
    for match in jsonld_pattern.finditer(html):
        try:
            import json
            data = json.loads(match.group(1))
            if isinstance(data, list):
                for item in data:
                    race = parse_jsonld_event(item)
                    if race:
                        races.append(race)
            elif isinstance(data, dict):
                if data.get("@type") == "Event":
                    race = parse_jsonld_event(data)
                    if race:
                        races.append(race)
        except Exception:
            pass

    # Try to match dates to races
    if all_dates and races:
        # Simple approach: if we have same number of dates and races
        for i, race in enumerate(races):
            if race["date"] == "TBA" and i < len(all_dates):
                d = parse_date(all_dates[i])
                if d:
                    race["date"] = d

    return races


def parse_jsonld_event(data):
    """Parse a JSON-LD Event object."""
    if not isinstance(data, dict):
        return None
    if data.get("@type") != "Event":
        return None

    name = data.get("name", "")
    if not name:
        return None

    date_str = data.get("startDate", "")
    if date_str:
        date_str = parse_date(date_str) or date_str[:10]

    location = ""
    province = None
    loc_data = data.get("location", {})
    if isinstance(loc_data, dict):
        location = loc_data.get("name", "")
        addr = loc_data.get("address", {})
        if isinstance(addr, dict):
            location = addr.get("addressLocality", location)
        province = detect_province(location)

    if not province:
        province = detect_province(name)

    return {
        "id": "fin-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40]),
        "name": name,
        "date": date_str or "TBA",
        "type": detect_type(name),
        "province": province or "Unknown",
        "location": location,
        "url": data.get("url", ""),
        "image": data.get("image", ""),
        "source": "Finishers",
        "distances": [],
        "tags": [],
    }
