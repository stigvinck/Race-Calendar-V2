"""
Scraper: GoToRace.com — Thailand races, filtered for Chiang Mai
GoToRace is a curated national site. We scrape all pages and
filter for events mentioning Chiang Mai / เชียงใหม่.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

BASE = "https://www.gotorace.com"
PAGES = [
    BASE + "/",
    BASE + "/?paged34178=2",
    BASE + "/?paged34178=3",
    BASE + "/?paged34178=4",
    BASE + "/?paged34178=5",
]

CM_KEYWORDS = ["chiang mai", "เชียงใหม่", "chiangmai"]

PROVINCE_KEYWORDS = {
    "chiang mai": "Chiang Mai", "chiangmai": "Chiang Mai", "chiang dao": "Chiang Mai",
    "bangkok": "Bangkok", "phuket": "Phuket", "chiang rai": "Chiang Rai",
    "khon kaen": "Khon Kaen", "nakhon ratchasima": "Nakhon Ratchasima",
    "korat": "Nakhon Ratchasima", "songkhla": "Songkhla", "chonburi": "Chonburi",
    "pattaya": "Chonburi", "surat thani": "Surat Thani", "samui": "Surat Thani",
    "krabi": "Krabi", "nan": "Nan", "trat": "Trat",
    "hua hin": "Prachuap Khiri Khan", "prachuap": "Prachuap Khiri Khan",
    "sam roi yod": "Prachuap Khiri Khan", "samroiyod": "Prachuap Khiri Khan",
    "phetchabun": "Phetchabun", "lampang": "Lampang", "sukhothai": "Sukhothai",
    "kanchanaburi": "Kanchanaburi", "rayong": "Rayong", "phang nga": "Phang Nga",
    "mae hong son": "Mae Hong Son", "yala": "Yala", "betong": "Yala",
}

def detect_province(text):
    lower = text.lower()
    for kw, prov in PROVINCE_KEYWORDS.items():
        if kw in lower:
            return prov
    return "Other"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

TYPE_MAP = {
    "road run": "run",
    "road": "run",
    "vertical marathon": "run",
    "trail": "trail",
    "triathlon": "triathlon",
    "duathlon": "triathlon",
    "cycling": "cycling",
    "swim": "swim",
    "obstacle": "obstacle",
}


class GoToRaceParser(HTMLParser):
    """Parse GoToRace event cards from HTML."""

    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None
        self.capture_title = False
        self.capture_text = False
        self.text_buffer = ""
        self.in_card = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        href = d.get("href", "")
        src = d.get("src", "")

        # Event cards are in <h3> followed by metadata
        if tag == "h3":
            self.capture_title = True
            self.text_buffer = ""

        # Capture event link from <a> inside <h3>
        if tag == "a" and self.capture_title and href:
            if href.startswith("http") and "gotorace.com" in href:
                self.current = {
                    "url": href,
                    "name": "",
                    "image": "",
                    "date": "",
                    "dateDisplay": "",
                    "location": "",
                    "type_raw": "",
                    "source": "gotorace",
                }
            elif href.startswith("http"):
                # External link (like pho3nixkids)
                self.current = {
                    "url": href,
                    "name": "",
                    "image": "",
                    "date": "",
                    "dateDisplay": "",
                    "location": "",
                    "type_raw": "",
                    "source": "gotorace",
                }

        # Capture images
        if tag == "img" and src and "wp-content/uploads" in src:
            if self.current and not self.current["image"]:
                self.current["image"] = src

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self.capture_title:
            self.text_buffer += text

        if self.current:
            # Type detection (e.g., "Road Run", "Trail", "Triathlon")
            lower = text.lower().strip()
            if lower in TYPE_MAP:
                self.current["type_raw"] = lower

            # Date detection
            if not self.current["date"]:
                # "DD Month YYYY" or "DD-DD Month YYYY"
                m = re.match(
                    r"^(\d{1,2})(?:-\d{1,2})?\s+"
                    r"(January|February|March|April|May|June|July|August|"
                    r"September|October|November|December)\s+(\d{4})$",
                    text, re.IGNORECASE
                )
                if m:
                    day = int(m.group(1))
                    month = MONTHS.get(m.group(2).lower(), 0)
                    year = int(m.group(3))
                    if month:
                        try:
                            dt = datetime(year, month, day)
                            self.current["date"] = dt.strftime("%Y-%m-%d")
                            self.current["dateDisplay"] = text
                        except ValueError:
                            pass

                # "D Month YYYY"
                m2 = re.match(
                    r"^(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
                    r"September|October|November|December)\s+(\d{4})$",
                    text, re.IGNORECASE
                )
                if m2 and not self.current["date"]:
                    day = int(m2.group(1))
                    month = MONTHS.get(m2.group(2).lower(), 0)
                    year = int(m2.group(3))
                    if month:
                        try:
                            dt = datetime(year, month, day)
                            self.current["date"] = dt.strftime("%Y-%m-%d")
                            self.current["dateDisplay"] = text
                        except ValueError:
                            pass

            # Location: anything with a comma that looks like a place
            if not self.current["location"] and "," in text and len(text) > 10:
                if not re.match(r"^\d", text) and text[0].isupper():
                    self.current["location"] = text

    def handle_endtag(self, tag):
        if tag == "h3" and self.capture_title:
            self.capture_title = False
            if self.current and self.text_buffer:
                self.current["name"] = self.text_buffer.strip()

        # Finalize race when we hit structural boundaries
        if self.current and self.current["name"] and self.current["date"]:
            # Check for duplicates
            urls = {r["url"] for r in self.races}
            if self.current["url"] not in urls:
                self.races.append(self.current)
            self.current = None


def is_chiang_mai(race):
    """Check if race is in Chiang Mai based on name or location."""
    searchable = f"{race.get('name', '')} {race.get('location', '')}".lower()
    return any(kw in searchable for kw in CM_KEYWORDS)


def scrape():
    """Fetch all GoToRace pages, filter for Chiang Mai events."""
    all_races = []

    for url in PAGES:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")

            parser = GoToRaceParser()
            parser.feed(html)
            all_races.extend(parser.races)
        except Exception as e:
            print(f"    GoToRace page error ({url}): {e}")

    # Build full schema — all Thailand races (no CM filter)
    result = []
    for r in all_races:
        race_type = TYPE_MAP.get(r.get("type_raw", ""), "run")
        slug = re.sub(r"[^a-z0-9]+", "-", r["name"].lower())[:40].strip("-")
        loc = r.get("location", "")
        province = detect_province(f"{r['name']} {loc}")
        result.append({
            "id": f"gotorace:{slug}",
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
    print(f"Found {len(races)} Chiang Mai races on GoToRace:")
    for r in races:
        print(f"  {r['date']} [{r['type']}] {r['name']}")
    if not races:
        print("  (No Chiang Mai events found — this is normal, GoToRace is national)")
