"""
Checkrace scraper (run.checkrace.com)
Thailand's #1 race registration platform. JS-rendered SPA — requires headless browser.
"""

import re
import json
from scrapers.headless import fetch_js, is_available

BASE_URL = "https://run.checkrace.com"

THAI_MONTHS = {
    "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
    "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
    "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03",
    "เมษายน": "04", "พฤษภาคม": "05", "มิถุนายน": "06",
    "กรกฎาคม": "07", "สิงหาคม": "08", "กันยายน": "09",
    "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
}

MONTHS_EN = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

TYPE_RULES = [
    ("trail", ["trail", "เทรล", "mountain", "jungle", "ดอย", "เขา"]),
    ("triathlon", ["triathlon", "ไตรกีฬา", "duathlon"]),
    ("cycling", ["cycling", "bike", "จักรยาน", "gravel"]),
    ("swim", ["swim", "ว่ายน้ำ", "open water"]),
    ("obstacle", ["obstacle", "spartan", "mud"]),
]


def scrape():
    if not is_available():
        print("    [Checkrace] Skipped — headless browser not available")
        return []

    races = []

    # Fetch the main events page
    html = fetch_js(BASE_URL, wait_for=".event-card, .card, a[href*='/event/']")
    if not html:
        print("    [Checkrace] Failed to load page")
        return []

    # Try to find embedded JSON state (common in SPAs)
    json_blocks = re.findall(r'window\.__(?:NUXT|NEXT_DATA|INITIAL_STATE)__\s*=\s*({.*?});\s*</', html, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            events = find_events_in_json(data)
            for ev in events:
                race = json_event_to_race(ev)
                if race:
                    races.append(race)
        except (json.JSONDecodeError, TypeError):
            pass

    # Also parse event links from rendered HTML
    event_links = re.findall(r'href="(/event/([^"]+))"', html)
    event_links += re.findall(r'href="(https?://run\.checkrace\.com/event/([^"]+))"', html)

    seen_slugs = {r["id"] for r in races}

    for link, slug in event_links:
        rid = f"checkrace-{slug}"
        if rid in seen_slugs:
            continue
        seen_slugs.add(rid)

        # Fetch individual event page
        ev_url = link if link.startswith("http") else BASE_URL + link
        ev_html = fetch_js(ev_url, wait_for=".event-detail, .event-info, h1")
        if not ev_html:
            continue

        race = parse_event_page(ev_html, slug, ev_url)
        if race:
            races.append(race)

    # Parse event cards from main page HTML directly
    card_races = parse_event_cards(html)
    for cr in card_races:
        if cr["id"] not in seen_slugs:
            races.append(cr)
            seen_slugs.add(cr["id"])

    print(f"    [Checkrace] Found {len(races)} races")
    return races


def find_events_in_json(data, depth=0):
    """Recursively find event-like objects in JSON."""
    if depth > 5:
        return []
    events = []
    if isinstance(data, dict):
        if "name" in data and ("date" in data or "startDate" in data or "eventDate" in data):
            events.append(data)
        for v in data.values():
            events.extend(find_events_in_json(v, depth + 1))
    elif isinstance(data, list):
        for item in data:
            events.extend(find_events_in_json(item, depth + 1))
    return events


def json_event_to_race(ev):
    """Convert a JSON event object to our race format."""
    name = ev.get("name", "") or ev.get("title", "") or ""
    if not name:
        return None

    date_str = ev.get("date", "") or ev.get("startDate", "") or ev.get("eventDate", "") or ""
    if date_str:
        date_str = date_str[:10]

    slug = ev.get("slug", "") or ev.get("id", "") or name[:30].lower().replace(" ", "-")
    location = ev.get("location", "") or ev.get("venue", "") or ""
    image = ev.get("image", "") or ev.get("coverImage", "") or ev.get("banner", "") or ""

    return {
        "id": f"checkrace-{slug}",
        "name": name,
        "date": date_str or "TBA",
        "location": location if isinstance(location, str) else str(location),
        "province": detect_province(name + " " + str(location)),
        "type": detect_type(name),
        "distances": extract_distances(ev),
        "url": f"{BASE_URL}/event/{slug}",
        "image": image,
        "source": "Checkrace",
        "tags": [],
    }


def parse_event_page(html, slug, url):
    """Parse a Checkrace individual event page."""
    # Title
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    name = title_m.group(1).strip() if title_m else slug.replace("-", " ").title()

    # Date
    date_str = parse_date_from_html(html)

    # Location
    location = ""
    loc_m = re.search(r'(?:สถานที่|location|venue)[:\s]*([^<\n]{5,80})', html, re.IGNORECASE)
    if loc_m:
        location = re.sub(r'<[^>]+>', '', loc_m.group(1)).strip()

    # Image
    image = ""
    og_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if og_m:
        image = og_m.group(1)

    # Distances
    distances = []
    for d in re.findall(r'(\d+(?:\.\d+)?)\s*(?:km|K|กม)\b', html, re.IGNORECASE):
        ds = f"{d}K"
        if ds not in distances and 0.5 <= float(d) <= 200:
            distances.append(ds)

    return {
        "id": f"checkrace-{slug}",
        "name": name,
        "date": date_str or "TBA",
        "location": location,
        "province": detect_province(name + " " + location + " " + html[:2000]),
        "type": detect_type(name),
        "distances": distances[:8],
        "url": url,
        "image": image,
        "source": "Checkrace",
        "tags": [],
    }


def parse_event_cards(html):
    """Parse event cards from main listing page HTML."""
    races = []
    # Look for card patterns with event info
    cards = re.findall(
        r'<a[^>]*href="(?:/event/|https?://run\.checkrace\.com/event/)([^"]+)"[^>]*>.*?</a>',
        html, re.DOTALL
    )
    # This is a fallback — most data comes from JSON or individual pages
    return races


def parse_date_from_html(html):
    """Extract date from HTML using multiple Thai and English patterns."""
    # Thai: "15 มี.ค. 2569" or "15 มีนาคม 2569"
    for thai_m, num_m in THAI_MONTHS.items():
        pat = rf'(\d{{1,2}})\s*{re.escape(thai_m)}\s*(\d{{4}})'
        m = re.search(pat, html)
        if m:
            day = m.group(1).zfill(2)
            year = int(m.group(2))
            if year > 2500:
                year -= 543
            return f"{year}-{num_m}-{day}"

    # English: "March 15, 2026"
    for en_m, num_m in MONTHS_EN.items():
        pat = rf'{en_m}\s+(\d{{1,2}}),?\s+(\d{{4}})'
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            day = m.group(1).zfill(2)
            year = m.group(2)
            return f"{year}-{num_m}-{day}"

    # ISO: 2026-03-15
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', html)
    if m:
        return m.group(0)

    return ""


def detect_type(name):
    lower = name.lower()
    for rtype, keywords in TYPE_RULES:
        for kw in keywords:
            if kw in lower:
                return rtype
    return "run"


def detect_province(text):
    text_lower = text.lower()
    provinces = {
        "เชียงใหม่": "Chiang Mai", "chiang mai": "Chiang Mai",
        "กรุงเทพ": "Bangkok", "bangkok": "Bangkok",
        "ภูเก็ต": "Phuket", "phuket": "Phuket",
        "ชลบุรี": "Chon Buri", "chon buri": "Chon Buri", "พัทยา": "Chon Buri",
        "นครราชสีมา": "Nakhon Ratchasima", "โคราช": "Nakhon Ratchasima",
        "ขอนแก่น": "Khon Kaen", "khon kaen": "Khon Kaen",
        "เชียงราย": "Chiang Rai", "chiang rai": "Chiang Rai",
        "กระบี่": "Krabi", "krabi": "Krabi",
        "สุราษฎร์ธานี": "Surat Thani", "เกาะสมุย": "Surat Thani",
        "ประจวบ": "Prachuap Khiri Khan", "หัวหิน": "Prachuap Khiri Khan",
        "นครสวรรค์": "Nakhon Sawan", "บุรีรัมย์": "Buriram",
        "ราชบุรี": "Ratchaburi", "อุดรธานี": "Udon Thani",
        "สงขลา": "Songkhla", "หาดใหญ่": "Songkhla",
        "พังงา": "Phang Nga", "ลำปาง": "Lampang",
        "น่าน": "Nan", "แม่ฮ่องสอน": "Mae Hong Son",
        "กาญจนบุรี": "Kanchanaburi", "kanchanaburi": "Kanchanaburi",
    }
    for key, prov in provinces.items():
        if key in text_lower:
            return prov
    return ""


def extract_distances(ev):
    dists = []
    for key in ("distances", "categories", "raceTypes"):
        val = ev.get(key, [])
        if isinstance(val, list):
            for d in val:
                if isinstance(d, str):
                    m = re.search(r'(\d+(?:\.\d+)?)', d)
                    if m:
                        dists.append(f"{m.group(1)}K")
                elif isinstance(d, dict):
                    name = d.get("name", "") or d.get("distance", "")
                    m = re.search(r'(\d+(?:\.\d+)?)', str(name))
                    if m:
                        dists.append(f"{m.group(1)}K")
    return dists[:8]
