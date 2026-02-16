"""
GranFondoGuide scraper
Scrapes granfondoguide.com for Thailand cycling events.
Individual event pages are SSR HTML. Known Thailand events:
Dustman (Kanchanaburi/Chiang Rai gravel), GFNY Krabi, Tour of Phuket, Chiang Mai Gran Fondo.
"""

import re
import urllib.request
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ThaiRaceFinder/1.0)",
    "Accept": "text/html",
    "Accept-Language": "en-US,en;q=0.9",
}

# Known Thailand events on GranFondoGuide (IDs and slugs)
KNOWN_EVENTS = [
    {"id": "11586", "slug": "dustman", "name": "Dustman Kanchanaburi"},
    {"id": "11586", "slug": "dustman-chiang-rai", "name": "Dustman Chiang Rai"},
    {"id": "10899", "slug": "dustman-hua-hin", "name": "Dustman Hua Hin"},
    {"id": "8249", "slug": "gfny-krabi", "name": "GFNY Krabi"},
    {"id": "8732", "slug": "tour-of-phuket", "name": "Tour of Phuket"},
    {"id": "10637", "slug": "chiang-mai-gran-fondo", "name": "Chiang Mai Gran Fondo"},
]

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def scrape():
    races = []
    seen = set()

    for ev in KNOWN_EVENTS:
        url = f"https://www.granfondoguide.com/Events/Index/{ev['id']}/{ev['slug']}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            race = parse_event(html, ev, url)
            if race and race["id"] not in seen:
                seen.add(race["id"])
                races.append(race)

        except Exception as e:
            print(f"    [GranFondoGuide] Error fetching {ev['slug']}: {e}")

    # Also try searching the calendar page for any new Thailand events
    try:
        cal_url = "https://www.granfondoguide.com/Events/GranFondoCalendar"
        req = urllib.request.Request(cal_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Find Thailand event links
        links = re.findall(r'href="(/Events/(?:Index|Popup)/(\d+)/([^"]+))"', html)
        for link, eid, slug in links:
            if eid in seen:
                continue
            # Check surrounding text for Thailand
            idx = html.find(link)
            context = html[max(0, idx-200):idx+200].lower()
            if "thailand" not in context:
                continue

            ev_url = "https://www.granfondoguide.com" + link
            try:
                req2 = urllib.request.Request(ev_url, headers=HEADERS)
                with urllib.request.urlopen(req2, timeout=15) as resp2:
                    ev_html = resp2.read().decode("utf-8", errors="replace")
                race = parse_event(ev_html, {"slug": slug, "name": slug.replace("-", " ").title()}, ev_url)
                if race and race["id"] not in seen:
                    seen.add(race["id"])
                    races.append(race)
            except Exception:
                pass

    except Exception as e:
        print(f"    [GranFondoGuide] Calendar page error: {e}")

    print(f"    [GranFondoGuide] Found {len(races)} Thailand cycling events")
    return races


def parse_event(html, ev_info, url):
    """Parse a GranFondoGuide event page."""
    # Check if it mentions Thailand
    if "thailand" not in html.lower():
        return None

    # Check if cancelled
    if "Cancelled" in html:
        return None

    # Title
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    name = title_m.group(1).strip() if title_m else ev_info.get("name", "")

    # Date
    date_str = ""
    # Pattern: "October 31 2026" or "March 06 - March 08, 2026"
    date_m = re.search(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
        r'(\d{1,2})(?:\s*-\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)?\s*\d{1,2})?,?\s*'
        r'(\d{4})',
        html
    )
    if date_m:
        month = MONTHS.get(date_m.group(1).lower(), "01")
        day = date_m.group(2).zfill(2)
        year = date_m.group(3)
        date_str = f"{year}-{month}-{day}"

    # Location
    location = ""
    loc_m = re.search(r'Start Located At:\s*([^<]+)', html)
    if loc_m:
        location = loc_m.group(1).strip().rstrip(".")

    # Province detection
    province = detect_province(html)

    # Distances
    distances = []
    dist_m = re.search(r'Distances?:\s*([^<]+)', html)
    if dist_m:
        dist_text = dist_m.group(1)
        for d in re.findall(r'(\d+(?:,\d+)?)\s*km', dist_text, re.IGNORECASE):
            distances.append(d.replace(",", "") + "K")
        if not distances:
            # Try just numbers
            for d in re.findall(r'(\d+)', dist_text):
                if 5 <= int(d) <= 500:
                    distances.append(d + "K")

    # Image
    image = ""
    img_m = re.search(r'(https?://[^"\']+(?:\.jpg|\.png|\.jpeg|\.webp))', html, re.IGNORECASE)
    if img_m:
        image = img_m.group(1)

    slug = ev_info.get("slug", name.lower().replace(" ", "-"))

    return {
        "id": f"gfguide-{slug}",
        "name": name,
        "date": date_str or "TBA",
        "location": location,
        "province": province,
        "type": "cycling",
        "distances": distances[:6],
        "url": url,
        "image": image,
        "source": "GranFondoGuide",
        "tags": detect_tags(name + " " + html[:500]),
    }


def detect_province(html):
    text = html.lower()
    provinces = {
        "kanchanaburi": "Kanchanaburi", "chiang rai": "Chiang Rai",
        "chiang mai": "Chiang Mai", "krabi": "Krabi", "phuket": "Phuket",
        "phang nga": "Phang Nga", "hua hin": "Prachuap Khiri Khan",
        "bangkok": "Bangkok", "nakhon ratchasima": "Nakhon Ratchasima",
        "chon buri": "Chon Buri",
    }
    for key, prov in provinces.items():
        if key in text:
            return prov
    return ""


def detect_tags(text):
    tags = []
    lower = text.lower()
    if "gravel" in lower:
        tags.append("gravel")
    if "gran fondo" in lower or "gfny" in lower:
        tags.append("gran fondo")
    if "uci" in lower:
        tags.append("UCI")
    if "tour" in lower:
        tags.append("stage race")
    return tags
