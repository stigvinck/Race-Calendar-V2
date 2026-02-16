"""
Scraper: GoToRace.com — All Thailand races
Uses the /all-event-2/ page which is server-side rendered (WordPress).
Pagination via ?paged34178=N
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

BASE = "https://www.gotorace.com"
ALL_EVENTS_URL = BASE + "/all-event-2/"
MAX_PAGES = 5

PROVINCE_KEYWORDS = {
    "chiang mai": "Chiang Mai", "chiangmai": "Chiang Mai", "chiang dao": "Chiang Mai",
    "mae rim": "Chiang Mai", "doi suthep": "Chiang Mai",
    "bangkok": "Bangkok", "phuket": "Phuket", "chiang rai": "Chiang Rai",
    "khon kaen": "Khon Kaen", "nakhon ratchasima": "Nakhon Ratchasima",
    "korat": "Nakhon Ratchasima", "songkhla": "Songkhla", "chonburi": "Chonburi",
    "pattaya": "Chonburi", "bangsaen": "Chonburi",
    "surat thani": "Surat Thani", "samui": "Surat Thani",
    "krabi": "Krabi", "nan ": "Nan", ", nan": "Nan",
    "phrae": "Phrae", "trat": "Trat",
    "hua hin": "Prachuap Khiri Khan", "prachuap": "Prachuap Khiri Khan",
    "sam roi yod": "Prachuap Khiri Khan", "samroiyod": "Prachuap Khiri Khan",
    "phetchabun": "Phetchabun", "khao kho": "Phetchabun",
    "lampang": "Lampang", "lamphun": "Lamphun", "sukhothai": "Sukhothai",
    "kanchanaburi": "Kanchanaburi", "rayong": "Rayong", "phang nga": "Phang Nga",
    "mae hong son": "Mae Hong Son", "pai ": "Mae Hong Son",
    "yala": "Yala", "betong": "Yala", "nong khai": "Nong Khai",
    "udon thani": "Udon Thani", "nakhon nayok": "Nakhon Nayok",
    "nakhonnayok": "Nakhon Nayok",
    "chachoengsao": "Chachoengsao", "chanthaburi": "Chanthaburi",
    "nakhon phanom": "Nakhon Phanom", "satun": "Satun",
    "loei": "Loei", "chiang khan": "Loei", "chaiyaphum": "Chaiyaphum",
    "buriram": "Buri Ram", "sa kaeo": "Sa Kaeo",
}

TYPE_MAP = {
    "road run": "run", "road-run": "run", "fun run": "run",
    "vertical marathon": "run",
    "trail": "trail",
    "triathlon": "triathlon",
    "cycling": "cycling", "bike": "cycling",
    "swim": "swim", "open water": "swim",
    "obstacle": "obstacle",
}

THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def detect_province(text):
    lower = text.lower()
    for kw, prov in PROVINCE_KEYWORDS.items():
        if kw in lower:
            return prov
    return "Other"


def detect_type(text):
    lower = text.lower().strip()
    for kw, rtype in TYPE_MAP.items():
        if kw in lower:
            return rtype
    return "run"


def parse_date(text):
    """Parse dates like '21-22 March 2026', '11 January 2026', '9 November 2025'"""
    text = text.strip()
    # "DD Month YYYY" or "DD-DD Month YYYY"
    m = re.match(r"(\d{1,2})(?:-\d{1,2})?\s+(\w+)\s+(\d{4})", text)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2).lower()
        year = int(m.group(3))
        month = EN_MONTHS.get(mon_str, 0)
        if month:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d"), text
            except ValueError:
                pass
    return "", text


class GoToRaceParser(HTMLParser):
    """Parse the all-event WordPress page."""
    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None
        self.in_h3 = False
        self.in_h3_a = False
        self.collect_text = False
        self.text_buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = d.get("href", "")
        src = d.get("src", "")

        # Each race card starts with an <a> containing an <img>
        if tag == "img" and src and "wp-content/uploads" in src:
            if self.current is None:
                self.current = {
                    "image": src,
                    "name": "", "url": "", "date": "", "dateDisplay": "",
                    "location": "", "type_raw": "",
                }

        # The title link: <h3><a href="...">Name</a></h3>
        if tag == "h3":
            self.in_h3 = True
        if tag == "a" and self.in_h3 and href and self.current:
            self.current["url"] = href
            self.in_h3_a = True

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self.in_h3_a and self.current:
            self.current["name"] = text

        if self.current and not self.in_h3_a:
            # Type line: "Road Run", "Trail", "Triathlon" etc.
            lower = text.lower().strip()
            if lower in ("road run", "trail", "triathlon", "cycling", "road-run",
                         "vertical marathon", "obstacle", "swim", "fun run",
                         "road run  ", "road run"):
                self.current["type_raw"] = text.strip()
                return

            # Date line: contains month names + year
            if re.search(r"(?:January|February|March|April|May|June|July|August|"
                         r"September|October|November|December)\s+\d{4}", text):
                d, dd = parse_date(text)
                if d:
                    self.current["date"] = d
                    self.current["dateDisplay"] = dd
                return

            # Location line: everything else with comma or province info
            if len(text) > 5 and not self.current["location"]:
                self.current["location"] = text

    def handle_endtag(self, tag):
        if tag == "a" and self.in_h3_a:
            self.in_h3_a = False
        if tag == "h3":
            self.in_h3 = False

        # A race card ends — check if we have enough data
        # We commit when we see the next image or at end
        pass

    def flush_current(self):
        """Call after parsing to commit the last race."""
        if self.current and self.current["name"] and self.current["date"]:
            self.races.append(self.current)
        self.current = None


def fetch_page(page_num):
    """Fetch one page of the all-events list."""
    url = ALL_EVENTS_URL if page_num <= 1 else f"{ALL_EVENTS_URL}?paged34178={page_num}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    return html


def parse_races_from_html(html):
    """
    Parse race cards from the GoToRace HTML.
    Each card has: image, h3>a (name+url), then text lines for type, location, date.
    """
    races = []
    # Use regex to find each card block since HTMLParser state tracking is tricky
    # Each card is between <article> or between race images
    # Actually, from the HTML we see: img → h3>a → text lines (type, location, date)

    # Find all h3 > a links (race titles)
    title_links = re.findall(
        r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>\s*(.+?)\s*</a>\s*</h3>',
        html, re.DOTALL)

    # Find all event images
    images = re.findall(
        r'<img[^>]*src="(https://www\.gotorace\.com/wp-content/uploads/[^"]+)"',
        html)

    # Find the text blocks between titles — they contain type, location, date
    # Split by the h3 tags to get the text after each title
    parts = re.split(r'<h3[^>]*>.*?</h3>', html, flags=re.DOTALL)

    for i, (url, name) in enumerate(title_links):
        name = re.sub(r'<[^>]+>', '', name).strip()
        if not name:
            continue

        # Get the text block after this title
        block = parts[i + 1] if i + 1 < len(parts) else ""
        # Strip HTML and get lines
        block_text = re.sub(r'<[^>]+>', '\n', block)
        lines = [l.strip() for l in block_text.split('\n') if l.strip()]

        type_raw = ""
        location = ""
        date_str = ""
        date_display = ""

        for line in lines[:8]:  # only check first few lines
            lower = line.lower().strip()
            # Type detection
            if lower in ("road run", "trail", "triathlon", "cycling",
                         "vertical marathon", "obstacle", "swim", "fun run"):
                type_raw = line.strip()
                continue
            # Date detection
            dm = re.search(
                r"(\d{1,2})(?:-\d{1,2})?\s+"
                r"(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+(\d{4})", line)
            if dm:
                d, dd = parse_date(line)
                if d:
                    date_str = d
                    date_display = dd
                continue
            # Location: anything else that's long enough
            if len(line) > 5 and not location:
                location = line

        if not date_str:
            continue

        image = images[i] if i < len(images) else ""

        races.append({
            "name": name, "url": url, "image": image,
            "date": date_str, "dateDisplay": date_display,
            "location": location, "type_raw": type_raw,
        })

    return races


def scrape():
    """Fetch all pages and return races."""
    all_races = []

    for page in range(1, MAX_PAGES + 1):
        try:
            html = fetch_page(page)
            races = parse_races_from_html(html)
            print(f"    GoToRace page {page}: {len(races)} races")
            if not races:
                break
            all_races.extend(races)
        except Exception as e:
            print(f"    GoToRace page {page} error: {e}")
            break

    # Build full schema
    result = []
    seen = set()
    for r in all_races:
        slug = re.sub(r"[^a-z0-9]+", "-", r["name"].lower())[:40].strip("-")
        rid = f"gotorace:{slug}"
        if rid in seen:
            continue
        seen.add(rid)

        race_type = detect_type(r.get("type_raw", ""))
        loc = r.get("location", "")
        province = detect_province(f"{r['name']} {loc}")

        result.append({
            "id": rid,
            "name": r["name"],
            "url": r["url"],
            "image": r["image"],
            "date": r["date"],
            "dateDisplay": r["dateDisplay"],
            "location": loc or "Thailand",
            "province": province,
            "country": "Thailand",
            "source": "gotorace",
            "type": race_type,
            "distances": [],
            "tags": [],
            "organizer": None,
            "price": None,
        })

    return result


if __name__ == "__main__":
    races = scrape()
    print(f"\nFound {len(races)} races on GoToRace:")
    for r in races:
        print(f"  {r['date']} [{r['type']:10s}] [{r['province']:20s}] {r['name'][:50]}")
