"""
Scraper: Pho3nixKidsThailand.com — Kids triathlon series
Scrapes event pages for upcoming kids tri/duathlon events.
"""

import re
import urllib.request
from html.parser import HTMLParser

BASE = "https://pho3nixkidsthailand.com"
URLS = [
    BASE + "/",
    BASE + "/wellington-college/",
    BASE + "/pattana-sports/",
    BASE + "/thanyapura-sports/",
]

PROVINCE_KEYWORDS = {
    "Bangkok": ["bangkok", "wellington college", "กรุงเทพ"],
    "Chon Buri": ["chon buri", "pattana sports", "si racha", "ชลบุรี"],
    "Phuket": ["phuket", "thanyapura", "ภูเก็ต"],
    "Samut Prakan": ["samut prakan", "samut prakarn", "สมุทรปราการ"],
    "Chiang Mai": ["chiang mai", "เชียงใหม่"],
}

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
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
    # DD Month YYYY
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
    """Scrape pho3nixkidsthailand.com for upcoming events."""
    print("    [Pho3nix] Fetching event pages...")
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

            # Extract event info via regex
            # Look for date patterns near event-related text
            date_matches = re.findall(
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})',
                html, re.IGNORECASE
            )

            # Look for event titles/headings
            title_matches = re.findall(
                r'<h[1-4][^>]*>(.*?)</h[1-4]>',
                html, re.DOTALL | re.IGNORECASE
            )
            titles = [re.sub(r'<[^>]+>', '', t).strip() for t in title_matches]
            titles = [t for t in titles if len(t) > 5 and ("pho3nix" in t.lower() or "triathlon" in t.lower() or "kids" in t.lower())]

            # Look for location info
            all_text = re.sub(r'<[^>]+>', ' ', html)

            # Extract venue/location
            location = ""
            province = detect_province(all_text)

            # If we found dates and titles, create race entries
            if date_matches and titles:
                name = titles[0]
                date_str = parse_date(date_matches[0])
                rid = "p3x-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40])

                if rid not in seen:
                    seen.add(rid)
                    races.append({
                        "id": rid,
                        "name": name,
                        "date": date_str or "TBA",
                        "type": "triathlon",
                        "province": province or "Unknown",
                        "location": location,
                        "url": url,
                        "image": "",
                        "source": "Pho3nix",
                        "distances": ["Kids tri/duathlon"],
                        "tags": ["kids"],
                    })
            elif titles:
                # No date found but have title
                name = titles[0]
                rid = "p3x-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40])
                if rid not in seen:
                    seen.add(rid)
                    races.append({
                        "id": rid,
                        "name": name,
                        "date": "TBA",
                        "type": "triathlon",
                        "province": province or "Unknown",
                        "location": "",
                        "url": url,
                        "image": "",
                        "source": "Pho3nix",
                        "distances": ["Kids tri/duathlon"],
                        "tags": ["kids"],
                    })

        except Exception as e:
            print("    [Pho3nix] Error on %s: %s" % (url, e))

    print("    [Pho3nix] Found %d events" % len(races))
    return races
