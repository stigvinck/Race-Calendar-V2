"""
race.thai.run scraper
Thailand's premier race registration system. JS-rendered SPA — requires headless browser.
Different from thai.run/events (which we already scrape via HTTP).
This specifically scrapes race.thai.run which has the active event listings.
"""

import re
import json
from scrapers.headless import fetch_js, is_available

BASE_URL = "https://race.thai.run"

THAI_MONTHS = {
    "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
    "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
    "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03",
    "เมษายน": "04", "พฤษภาคม": "05", "มิถุนายน": "06",
    "กรกฎาคม": "07", "สิงหาคม": "08", "กันยายน": "09",
    "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
}

TYPE_RULES = [
    ("trail", ["trail", "เทรล", "mountain", "jungle", "ดอย", "เขา"]),
    ("triathlon", ["triathlon", "ไตรกีฬา", "duathlon"]),
    ("cycling", ["cycling", "bike", "จักรยาน", "gravel", "ปั่น"]),
    ("swim", ["swim", "ว่ายน้ำ", "open water"]),
    ("obstacle", ["obstacle", "spartan", "mud"]),
]


def scrape():
    if not is_available():
        print("    [race.thai.run] Skipped — headless browser not available")
        return []

    races = []

    # Fetch main page
    html = fetch_js(BASE_URL, wait_for="a[href*='/event'], .event, .card")
    if not html:
        print("    [race.thai.run] Failed to load page")
        return []

    # Try embedded JSON
    json_blocks = re.findall(r'window\.__\w+__\s*=\s*({.*?});\s*</', html, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            events = find_events_in_json(data)
            for ev in events:
                race = json_to_race(ev)
                if race:
                    races.append(race)
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse event links from rendered HTML
    seen = {r["id"] for r in races}
    event_links = set()

    # Pattern: /event/slug or full URLs
    for m in re.finditer(r'href="(/[^"]*?/event/([^"]+))"', html):
        event_links.add((m.group(1), m.group(2)))
    for m in re.finditer(r'href="(https?://race\.thai\.run/([^/"]+)/?)"', html):
        slug = m.group(2)
        if slug not in ("", "login", "register", "faq", "about"):
            event_links.add((m.group(1), slug))

    # Also look for event cards with names and dates
    card_races = parse_cards_from_html(html)
    for cr in card_races:
        if cr["id"] not in seen:
            races.append(cr)
            seen.add(cr["id"])

    for link, slug in list(event_links)[:30]:
        rid = f"thairun-race-{slug}"
        if rid in seen:
            continue
        seen.add(rid)

        ev_url = link if link.startswith("http") else BASE_URL + link
        ev_html = fetch_js(ev_url, wait_for="h1, .event-name")
        if not ev_html:
            continue

        race = parse_event_page(ev_html, slug, ev_url)
        if race:
            races.append(race)

    print(f"    [race.thai.run] Found {len(races)} races")
    return races


def find_events_in_json(data, depth=0):
    if depth > 5:
        return []
    events = []
    if isinstance(data, dict):
        if ("name" in data or "title" in data) and ("date" in data or "startDate" in data or "eventDate" in data):
            events.append(data)
        for v in data.values():
            events.extend(find_events_in_json(v, depth + 1))
    elif isinstance(data, list):
        for item in data:
            events.extend(find_events_in_json(item, depth + 1))
    return events


def json_to_race(ev):
    name = ev.get("name", "") or ev.get("title", "") or ""
    if not name:
        return None
    date_str = (ev.get("date", "") or ev.get("startDate", "") or ev.get("eventDate", "") or "")[:10]
    slug = ev.get("slug", "") or ev.get("id", "") or name[:30].lower().replace(" ", "-")
    location = ev.get("location", "") or ev.get("venue", "") or ""
    image = ev.get("image", "") or ev.get("coverImage", "") or ""

    # Convert Buddhist year
    if date_str and len(date_str) >= 4:
        try:
            y = int(date_str[:4])
            if y > 2500:
                date_str = str(y - 543) + date_str[4:]
        except ValueError:
            pass

    return {
        "id": f"thairun-race-{slug}",
        "name": name,
        "date": date_str or "TBA",
        "location": str(location),
        "province": detect_province(name + " " + str(location)),
        "type": detect_type(name),
        "distances": [],
        "url": f"{BASE_URL}/{slug}" if slug else BASE_URL,
        "image": image,
        "source": "race.thai.run",
        "tags": [],
    }


def parse_cards_from_html(html):
    """Parse event info from rendered card elements."""
    races = []
    # Look for structured event data in the rendered HTML
    # Common patterns: event name in h2/h3/strong, date nearby, image

    # Try finding event blocks with Thai text
    blocks = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>.*?'
        r'(?:<(?:h[1-5]|strong|b)[^>]*>([^<]{4,80})</(?:h[1-5]|strong|b)>)'
        r'.*?(?:(\d{1,2})\s+(?:' + '|'.join(re.escape(k) for k in THAI_MONTHS.keys()) + r')\s+(\d{4}))?',
        html, re.DOTALL
    )

    for match in blocks:
        link, name, day, year_str = match if len(match) == 4 else (*match, "", "")
        if not name or len(name) < 4:
            continue

        slug = link.rstrip("/").split("/")[-1] if link else name[:20].lower().replace(" ", "-")
        rid = f"thairun-race-{slug}"

        date_str = ""
        if day and year_str:
            year = int(year_str)
            if year > 2500:
                year -= 543
            # Find which month matched
            context = html[html.find(match[0]):html.find(match[0]) + 200] if match[0] in html else ""
            for tm, mn in THAI_MONTHS.items():
                if tm in context:
                    date_str = f"{year}-{mn}-{day.zfill(2)}"
                    break

        races.append({
            "id": rid,
            "name": name.strip(),
            "date": date_str or "TBA",
            "location": "",
            "province": detect_province(name),
            "type": detect_type(name),
            "distances": [],
            "url": (BASE_URL + link) if link.startswith("/") else (link or BASE_URL),
            "image": "",
            "source": "race.thai.run",
            "tags": [],
        })

    return races


def parse_event_page(html, slug, url):
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    name = title_m.group(1).strip() if title_m else slug.replace("-", " ")

    date_str = parse_thai_date(html)

    location = ""
    loc_m = re.search(r'(?:สถานที่|location|venue|จังหวัด)[:\s]*([^<\n]{5,80})', html, re.IGNORECASE)
    if loc_m:
        location = re.sub(r'<[^>]+>', '', loc_m.group(1)).strip()

    image = ""
    og_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if og_m:
        image = og_m.group(1)

    distances = []
    for d in re.findall(r'(\d+(?:\.\d+)?)\s*(?:km|K|กม)\b', html, re.IGNORECASE):
        ds = f"{d}K"
        if ds not in distances and 0.5 <= float(d) <= 200:
            distances.append(ds)

    return {
        "id": f"thairun-race-{slug}",
        "name": name,
        "date": date_str or "TBA",
        "location": location,
        "province": detect_province(name + " " + location + " " + html[:2000]),
        "type": detect_type(name),
        "distances": distances[:8],
        "url": url,
        "image": image,
        "source": "race.thai.run",
        "tags": [],
    }


def parse_thai_date(html):
    for tm, mn in THAI_MONTHS.items():
        pat = rf'(\d{{1,2}})\s*{re.escape(tm)}\s*(\d{{4}})'
        m = re.search(pat, html)
        if m:
            day = m.group(1).zfill(2)
            year = int(m.group(2))
            if year > 2500:
                year -= 543
            return f"{year}-{mn}-{day}"
    # English fallback
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
        "ชลบุรี": "Chon Buri", "chon buri": "Chon Buri",
        "นครราชสีมา": "Nakhon Ratchasima",
        "ขอนแก่น": "Khon Kaen", "เชียงราย": "Chiang Rai",
        "กระบี่": "Krabi", "สุราษฎร์ธานี": "Surat Thani",
        "ประจวบ": "Prachuap Khiri Khan", "หัวหิน": "Prachuap Khiri Khan",
        "บุรีรัมย์": "Buriram", "ราชบุรี": "Ratchaburi",
        "อุดรธานี": "Udon Thani", "สงขลา": "Songkhla",
        "กาญจนบุรี": "Kanchanaburi", "ลำปาง": "Lampang",
        "น่าน": "Nan", "นครสวรรค์": "Nakhon Sawan",
        "ปราจีนบุรี": "Prachin Buri", "เพชรบูรณ์": "Phetchabun",
    }
    for key, prov in provinces.items():
        if key in text_lower:
            return prov
    return ""
