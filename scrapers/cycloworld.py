"""
Scraper: CycloWorld.cc — Cycling race directory
Scrapes Thailand cycling events (gran fondo, road races, etc.)
"""

import re
import urllib.request
from html.parser import HTMLParser

BASE = "https://www.cycloworld.cc"
URLS = [
    BASE + "/en/gran-fondo/thailand",
    BASE + "/en/races/thailand",
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
    "Chiang Mai": ["chiang mai", "chiangmai", "mae rim", "doi suthep", "fang"],
    "Bangkok": ["bangkok"],
    "Phuket": ["phuket"],
    "Chiang Rai": ["chiang rai"],
    "Chon Buri": ["chon buri", "pattaya", "bang saen"],
    "Nakhon Ratchasima": ["nakhon ratchasima", "korat", "khao yai"],
    "Prachuap Khiri Khan": ["prachuap", "hua hin", "sam roi yod"],
    "Krabi": ["krabi"],
    "Surat Thani": ["samui", "surat thani"],
    "Kanchanaburi": ["kanchanaburi"],
    "Lampang": ["lampang"],
    "Nan": ["nan"],
    "Mae Hong Son": ["mae hong son", "pai"],
    "Phetchabun": ["phetchabun", "khao kho"],
}


def detect_province(text):
    lower = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return province
    return None


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)
    m = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)
    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)
    return None


def scrape():
    """Scrape cycloworld.cc for Thailand cycling races."""
    print("    [CycloWorld] Fetching cycling pages...")
    races = []
    seen = set()

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            if len(html) < 500:
                print("    [CycloWorld] Page too short: %s" % url)
                continue

            # Extract race links: <a href="/en/gran-fondo/thailand/event-name/12345">
            link_pattern = re.compile(
                r'<a[^>]*href=["\']((?:/en/(?:gran-fondo|races?)/thailand/[^"\']+))["\']\s*[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE
            )

            for match in link_pattern.finditer(html):
                path = match.group(1)
                inner = match.group(2)
                name = re.sub(r'<[^>]+>', ' ', inner).strip()
                name = re.sub(r'\s+', ' ', name).strip()

                if len(name) < 4 or len(name) > 150:
                    continue
                # Skip nav links
                if name.lower() in ("view", "details", "more", "see all", "thailand"):
                    continue

                event_url = BASE + path
                rid = "cyclo-" + re.sub(r'[^a-z0-9]', '', path.lower()[:50])

                if rid in seen:
                    continue
                seen.add(rid)

                province = detect_province(name + " " + path)
                races.append({
                    "id": rid,
                    "name": name,
                    "date": "TBA",
                    "type": "cycling",
                    "province": province or "Unknown",
                    "location": "",
                    "url": event_url,
                    "image": "",
                    "source": "CycloWorld",
                    "distances": [],
                    "tags": ["cycling"],
                })

            # Also try to extract dates from nearby text
            # Pattern: look for date text near event cards
            date_blocks = re.findall(
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})',
                html, re.IGNORECASE
            )

            # Try to match dates to races
            for i, race in enumerate(races):
                if race["date"] == "TBA" and i < len(date_blocks):
                    d = parse_date(date_blocks[i])
                    if d:
                        race["date"] = d

        except Exception as e:
            print("    [CycloWorld] Error on %s: %s" % (url, e))

    print("    [CycloWorld] Found %d events" % len(races))
    return races
