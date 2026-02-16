"""
RunningConnect scraper
Scrapes runningconnect.com for Thailand running/trail events.
Primary source for UTMB Thailand events (Amazean Jungle, Chiang Mai UTMB, etc.)
SSR HTML — very scrapable.
"""

import re
import urllib.request
from datetime import datetime

BASE_URL = "https://www.runningconnect.com"
URLS = [
    "https://www.runningconnect.com/",
    "https://www.runningconnect.com/event",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ThaiRaceFinder/1.0)",
    "Accept": "text/html",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}


def scrape():
    races = []
    seen_ids = set()

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Extract event links: /event/XXXXX
            event_links = re.findall(r'href="(/event/([A-Z0-9_-]+))"', html)

            for link, event_id in event_links:
                if event_id in seen_ids:
                    continue
                if event_id in ("", "login", "create", "faq"):
                    continue
                seen_ids.add(event_id)

            # Parse event cards from homepage
            # Pattern: date block + event name + location + distances
            # The homepage has structured blocks with day, month, name, location, distances

            # Extract event blocks: look for h3 links with event names
            blocks = re.findall(
                r'<h3[^>]*>\s*<a[^>]*href="(/event/([^"]+))"[^>]*>([^<]+)</a>\s*</h3>'
                r'.*?(?:</div>)',
                html, re.DOTALL
            )

            for match in blocks:
                if len(match) >= 3:
                    link, eid, name = match[0], match[1], match[2].strip()
                    if eid in ("", "login", "create", "faq"):
                        continue

        except Exception as e:
            print(f"    [RunningConnect] Error fetching {url}: {e}")

    # Now fetch individual event pages for events we found
    for event_id in list(seen_ids)[:20]:  # Limit to 20 events
        try:
            event_url = f"{BASE_URL}/event/{event_id}"
            req = urllib.request.Request(event_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            race = parse_event_page(html, event_id, event_url)
            if race and is_thailand(race):
                races.append(race)

        except Exception as e:
            print(f"    [RunningConnect] Error fetching event {event_id}: {e}")

    print(f"    [RunningConnect] Found {len(races)} Thailand races")
    return races


def is_thailand(race):
    """Check if race is in Thailand based on location text."""
    text = (race.get("name", "") + " " + race.get("location", "")).lower()
    thailand_indicators = [
        "thailand", "chiang mai", "bangkok", "phuket", "pattaya",
        "khon kaen", "buriram", "nakhon", "chon buri", "hua hin",
        "betong", "phatthalung", "udon", "kanchanaburi", "krabi",
        "prachuap", "ayutthaya", "ratchaburi", "สมุทร", "กรุงเทพ",
        "เชียงใหม่", "ภูเก็ต", "จังหวัด", "อุโมงค์",
        "utmb", "amazean jungle",
    ]
    # Exclude non-Thailand events
    non_thailand = ["vietnam", "dalat", "phong nha", "mount yun", "china", "japan", "malaysia"]
    for nt in non_thailand:
        if nt in text:
            return False
    for ind in thailand_indicators:
        if ind in text:
            return True
    return False


def parse_event_page(html, event_id, url):
    """Parse a RunningConnect event page."""
    # Extract title
    title_m = re.search(r'<title[^>]*>RunningConnect\s*-\s*(.+?)</title>', html)
    if not title_m:
        title_m = re.search(r'<h[12][^>]*>([^<]+)</h[12]>', html)
    name = title_m.group(1).strip() if title_m else event_id

    # Extract date from page content
    # Look for patterns like "01 May" or "May 2026" or structured date
    date_str = ""

    # Try structured date patterns
    date_patterns = [
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]

    for pat in date_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[0].isdigit() and len(groups[0]) == 4:
                    # YYYY-MM-DD
                    date_str = f"{groups[0]}-{groups[1]}-{groups[2]}"
                elif len(groups) == 3 and groups[1].lower() in MONTHS:
                    # DD Month YYYY
                    day = groups[0].zfill(2)
                    month = MONTHS[groups[1].lower()]
                    year = groups[2]
                    date_str = f"{year}-{month}-{day}"
                elif len(groups) == 3 and groups[0].lower() in MONTHS:
                    # Month DD, YYYY
                    month = MONTHS[groups[0].lower()]
                    day = groups[1].zfill(2)
                    year = groups[2]
                    date_str = f"{year}-{month}-{day}"
            except (ValueError, KeyError):
                pass
            if date_str:
                break

    # Extract location
    location = ""
    loc_m = re.search(r'(?:PM|AM)\s+(.+?)(?:\s*<br|\s*\n|\s*$)', html)
    if loc_m:
        location = re.sub(r'<[^>]+>', '', loc_m.group(1)).strip()

    # Extract distances
    distances = []
    dist_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:km|K)\b', html, re.IGNORECASE)
    for d in dist_matches:
        km = d
        if float(km) > 0.5:
            dist_str = f"{km}K"
            if dist_str not in distances:
                distances.append(dist_str)

    # Extract image
    image = ""
    img_m = re.search(r'(https://runningconnect-media[^"\']+banner[^"\']*)', html)
    if img_m:
        image = img_m.group(1)
    if not image:
        img_m = re.search(r'(https://runningconnect-media[^"\']+illustration[^"\']*)', html)
        if img_m:
            image = img_m.group(1)

    # Detect province
    province = detect_province(name + " " + location)

    # Detect type
    race_type = detect_type(name)

    return {
        "id": f"runningconnect-{event_id}".lower(),
        "name": name,
        "date": date_str or "TBA",
        "location": location,
        "province": province,
        "type": race_type,
        "distances": distances[:8],
        "url": url,
        "image": image,
        "source": "RunningConnect",
        "tags": detect_tags(name),
    }


def detect_province(text):
    text_lower = text.lower()
    provinces = {
        "chiang mai": "Chiang Mai", "เชียงใหม่": "Chiang Mai",
        "bangkok": "Bangkok", "กรุงเทพ": "Bangkok",
        "phuket": "Phuket", "ภูเก็ต": "Phuket",
        "buriram": "Buriram", "บุรีรัมย์": "Buriram",
        "khon kaen": "Khon Kaen",
        "betong": "Yala", "เบตง": "Yala",
        "nakhon ratchasima": "Nakhon Ratchasima", "โคราช": "Nakhon Ratchasima",
        "ratchaburi": "Ratchaburi", "ราชบุรี": "Ratchaburi",
        "chombueng": "Ratchaburi",
        "phatthalung": "Phatthalung",
        "prachuap": "Prachuap Khiri Khan",
        "chon buri": "Chon Buri",
        "krabi": "Krabi",
    }
    for key, prov in provinces.items():
        if key in text_lower:
            return prov
    return ""


def detect_type(name):
    name_lower = name.lower()
    if any(w in name_lower for w in ["trail", "utmb", "jungle", "mountain", "doi", "ultra"]):
        return "trail"
    if any(w in name_lower for w in ["triathlon", "tri ", "duathlon"]):
        return "triathlon"
    if any(w in name_lower for w in ["cycling", "bike", "gran fondo"]):
        return "cycling"
    if any(w in name_lower for w in ["swim", "aqua"]):
        return "swim"
    return "run"


def detect_tags(name):
    tags = []
    name_lower = name.lower()
    if "utmb" in name_lower:
        tags.append("UTMB")
    if "trail" in name_lower:
        tags.append("trail")
    if "ultra" in name_lower:
        tags.append("ultra")
    if "marathon" in name_lower:
        tags.append("marathon")
    if "night" in name_lower:
        tags.append("night run")
    return tags
