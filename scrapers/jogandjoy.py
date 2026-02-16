"""
Scraper: JogAndJoy.com — Thailand running calendar
Scrapes the running calendar page for upcoming Thai races.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

URL = "https://www.jogandjoy.com/thailand-running-calender"
MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

PROVINCE_KEYWORDS = {
    "Chiang Mai": ["chiang mai", "chiangmai", "เชียงใหม่", "doi suthep", "mae rim"],
    "Bangkok": ["bangkok", "กรุงเทพ", "centralworld", "bkk"],
    "Phuket": ["phuket", "ภูเก็ต", "laguna", "patong"],
    "Chiang Rai": ["chiang rai", "chiangrai", "เชียงราย"],
    "Chon Buri": ["chon buri", "chonburi", "pattaya", "bangsaen", "bang saen", "si racha"],
    "Nakhon Ratchasima": ["nakhon ratchasima", "korat", "khao yai"],
    "Khon Kaen": ["khon kaen", "ขอนแก่น"],
    "Surat Thani": ["surat thani", "samui", "koh samui"],
    "Krabi": ["krabi", "กระบี่"],
    "Prachuap Khiri Khan": ["prachuap", "hua hin", "หัวหิน", "sam roi yod"],
    "Nan": ["nan province", "nan city", "น่าน"],
    "Mae Hong Son": ["mae hong son", "pai district", "pai,"],
    "Phetchabun": ["phetchabun", "khao kho"],
    "Trat": ["trat", "koh chang"],
    "Songkhla": ["songkhla", "hat yai"],
    "Yala": ["yala", "betong"],
    "Lampang": ["lampang"],
    "Sukhothai": ["sukhothai"],
    "Trang": ["trang"],
    "Rayong": ["rayong"],
    "Phang Nga": ["phang nga", "phang-nga"],
    "Nakhon Pathom": ["nakhon pathom"],
    "Prachin Buri": ["prachin buri", "prachinburi"],
    "Nakhon Sawan": ["nakhon sawan"],
    "Nong Khai": ["nong khai"],
    "Phrae": ["phrae"],
}

TYPE_MAP = {
    "run": "run", "running": "run", "marathon": "run", "mini marathon": "run",
    "half marathon": "run", "ultra": "trail", "trail": "trail",
    "triathlon": "triathlon", "tri": "triathlon", "duathlon": "triathlon",
    "cycling": "cycling", "bike": "cycling", "gran fondo": "cycling",
    "swim": "swim", "open water": "swim", "aquathlon": "swim",
    "obstacle": "obstacle", "ocr": "obstacle", "spartan": "obstacle",
}


def detect_province(text):
    """Detect province from race name/location text."""
    lower = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return province
    return None


def detect_type(text):
    """Detect race type from text."""
    lower = text.lower()
    for keyword, rtype in TYPE_MAP.items():
        if keyword in lower:
            return rtype
    return "run"


def parse_date(text):
    """Try to parse a date string into YYYY-MM-DD."""
    if not text:
        return None
    text = text.strip()

    # Pattern: "5 Sep 2026", "15 March 2026", etc.
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)

    # Pattern: "Sep 5, 2026"
    m = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)

    return None


class CalendarParser(HTMLParser):
    """Parse jogandjoy.com running calendar page."""

    def __init__(self):
        super().__init__()
        self.races = []
        self.in_row = False
        self.in_cell = False
        self.current_cells = []
        self.current_text = ""
        self.current_link = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "tr":
            self.in_row = True
            self.current_cells = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_text = ""
            self.current_link = None
        elif tag == "a" and self.in_cell:
            href = attr_dict.get("href", "")
            if href and href.startswith("http"):
                self.current_link = href

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.current_cells.append({
                "text": self.current_text.strip(),
                "link": self.current_link
            })
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if len(self.current_cells) >= 2:
                self._process_row(self.current_cells)

    def handle_data(self, data):
        if self.in_cell:
            self.current_text += data

    def _process_row(self, cells):
        """Try to extract a race from a table row."""
        # Typical format: Date | Name | Location | Distance | ...
        # Or: Date | Name | ...
        # Skip header rows
        first_text = cells[0]["text"].lower()
        if "date" in first_text or "event" in first_text:
            return

        date_str = None
        name = None
        url = None

        # Try first cell as date
        date_str = parse_date(cells[0]["text"])

        if date_str and len(cells) >= 2:
            name = cells[1]["text"]
            url = cells[1].get("link")
        elif len(cells) >= 3:
            # Maybe date in another position
            for c in cells:
                d = parse_date(c["text"])
                if d:
                    date_str = d
                    break
            # Name is usually the longest cell
            name = max(cells, key=lambda c: len(c["text"]))["text"]
            for c in cells:
                if c.get("link"):
                    url = c["link"]
                    break

        if not name or len(name) < 3:
            return

        province = None
        for c in cells:
            province = detect_province(c["text"])
            if province:
                break
        if not province:
            province = detect_province(name)

        race_type = detect_type(name)
        location = ""
        if len(cells) >= 3:
            for c in cells[2:]:
                prov = detect_province(c["text"])
                if prov or len(c["text"]) > 3:
                    location = c["text"]
                    if prov and not province:
                        province = prov
                    break

        distances = []
        for c in cells:
            if re.search(r'\d+\s*[kK]', c["text"]):
                distances.append(c["text"].strip())

        race = {
            "id": "jaj-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40]),
            "name": name,
            "date": date_str or "TBA",
            "type": race_type,
            "province": province or "Unknown",
            "location": location or "",
            "url": url or "",
            "image": "",
            "source": "JogAndJoy",
            "distances": distances,
            "tags": [],
        }
        self.races.append(race)


def scrape():
    """Scrape jogandjoy.com Thailand running calendar."""
    print("    [JogAndJoy] Fetching calendar page...")
    races = []

    try:
        req = urllib.request.Request(URL, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        parser = CalendarParser()
        parser.feed(html)
        races = parser.races
        print("    [JogAndJoy] Parsed %d races" % len(races))

    except Exception as e:
        print("    [JogAndJoy] Error: %s" % e)

    return races
