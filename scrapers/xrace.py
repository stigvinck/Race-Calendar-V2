"""
Scraper: XRaceAsia.com — Obstacle & adventure race events
Scrapes upcoming XRace events in Thailand.
"""

import re
import urllib.request

BASE = "https://xraceasia.com"
URLS = [
    BASE + "/events/",
    BASE + "/event/",
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
    "Chiang Mai": ["chiang mai"],
    "Bangkok": ["bangkok"],
    "Phuket": ["phuket"],
    "Chon Buri": ["chon buri", "pattaya", "koh chang"],
    "Prachuap Khiri Khan": ["hua hin", "prachuap"],
    "Krabi": ["krabi"],
    "Trat": ["trat", "koh chang"],
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
    return None


def scrape():
    """Scrape xraceasia.com for obstacle/adventure events."""
    print("    [XRace] Fetching event pages...")
    races = []
    seen = set()

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            if len(html) < 500:
                continue

            # Extract event links
            link_pattern = re.compile(
                r'<a[^>]*href=["\'](https?://xraceasia\.com/event/[^"\']+)["\']\s*[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE
            )

            for match in link_pattern.finditer(html):
                event_url = match.group(1)
                inner = match.group(2)
                name = re.sub(r'<[^>]+>', ' ', inner).strip()
                name = re.sub(r'\s+', ' ', name).strip()

                if len(name) < 4 or len(name) > 150:
                    continue
                if name.lower() in ("view", "details", "more", "register"):
                    continue

                rid = "xrace-" + re.sub(r'[^a-z0-9]', '', event_url.lower()[-40:])
                if rid in seen:
                    continue
                seen.add(rid)

                province = detect_province(name + " " + event_url)

                races.append({
                    "id": rid,
                    "name": name,
                    "date": "TBA",
                    "type": "obstacle",
                    "province": province or "Unknown",
                    "location": "",
                    "url": event_url,
                    "image": "",
                    "source": "XRace",
                    "distances": [],
                    "tags": ["obstacle", "adventure"],
                })

            # Extract dates from page
            date_blocks = re.findall(
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})',
                html, re.IGNORECASE
            )
            for i, race in enumerate(races):
                if race["date"] == "TBA" and i < len(date_blocks):
                    d = parse_date(date_blocks[i])
                    if d:
                        race["date"] = d

        except Exception as e:
            print("    [XRace] Error on %s: %s" % (url, e))

    print("    [XRace] Found %d events" % len(races))
    return races
