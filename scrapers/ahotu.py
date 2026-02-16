"""
Scraper: ahotu.com — Thailand endurance races (all sports)
Ahotu covers running, trail, cycling, triathlon, swimming, obstacle races.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

# Ahotu Thailand pages by sport
URLS = [
    ("running", "https://www.ahotu.com/calendar/running/thailand"),
    ("trail", "https://www.ahotu.com/calendar/trail-running/thailand"),
    ("triathlon", "https://www.ahotu.com/calendar/triathlon/thailand"),
    ("cycling", "https://www.ahotu.com/calendar/cycling/thailand"),
    ("swimming", "https://www.ahotu.com/calendar/swimming/thailand"),
]
BASE = "https://www.ahotu.com"

PROVINCE_KEYWORDS = {
    "chiang mai": "Chiang Mai", "chiangmai": "Chiang Mai", "chiang dao": "Chiang Mai",
    "mae rim": "Chiang Mai", "doi suthep": "Chiang Mai",
    "bangkok": "Bangkok", "phuket": "Phuket", "chiang rai": "Chiang Rai",
    "khon kaen": "Khon Kaen", "nakhon ratchasima": "Nakhon Ratchasima",
    "korat": "Nakhon Ratchasima", "songkhla": "Songkhla", "chonburi": "Chonburi",
    "pattaya": "Chonburi", "bangsaen": "Chonburi", "bang saen": "Chonburi",
    "surat thani": "Surat Thani", "samui": "Surat Thani",
    "krabi": "Krabi", "nan": "Nan", "phrae": "Phrae", "trat": "Trat",
    "hua hin": "Prachuap Khiri Khan", "prachuap": "Prachuap Khiri Khan",
    "sam roi yod": "Prachuap Khiri Khan",
    "phetchabun": "Phetchabun", "khao kho": "Phetchabun",
    "lampang": "Lampang", "lamphun": "Lamphun", "sukhothai": "Sukhothai",
    "kanchanaburi": "Kanchanaburi", "rayong": "Rayong", "phang nga": "Phang Nga",
    "mae hong son": "Mae Hong Son", "pai": "Mae Hong Son",
    "yala": "Yala", "betong": "Yala", "nong khai": "Nong Khai",
    "udon thani": "Udon Thani", "ayutthaya": "Phra Nakhon Si Ayutthaya",
    "nakhon pathom": "Nakhon Pathom", "nakhon sawan": "Nakhon Sawan",
    "prachin buri": "Prachin Buri", "trang": "Trang",
    "phitsanulok": "Phitsanulok",
}

AHOTU_TYPE_MAP = {
    "running": "run", "trail": "trail", "trail-running": "trail",
    "triathlon": "triathlon", "cycling": "cycling", "swimming": "swim",
}

MONTHS_3 = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def detect_province(text):
    lower = text.lower()
    for kw, prov in PROVINCE_KEYWORDS.items():
        if kw in lower:
            return prov
    return "Other"


class AhotuParser(HTMLParser):
    """Parse race listings from ahotu.com."""
    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None
        self.in_link = False
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = d.get("href", "")

        if tag == "a" and href and "/event/" in href:
            self.current = {
                "url": BASE + href if href.startswith("/") else href,
                "name": "",
                "date": "",
                "dateDisplay": "",
                "location": "",
            }
            self.in_link = True
            self.text_parts = []

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self.in_link and self.current:
            self.text_parts.append(text)

        if self.current and not self.current["date"]:
            # "DD Mon, YYYY" or "DD-DD Mon, YYYY"
            m = re.match(r"(\d{1,2})(?:-\d{1,2})?\s+(\w{3}),?\s+(\d{4})", text)
            if m:
                day, mon, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
                if mon in MONTHS_3:
                    try:
                        dt = datetime(year, MONTHS_3[mon], day)
                        self.current["date"] = dt.strftime("%Y-%m-%d")
                        self.current["dateDisplay"] = text
                    except ValueError:
                        pass

        # Location info (often after date, contains "Thailand")
        if self.current and "Thailand" in text and not self.current["location"]:
            self.current["location"] = text.replace(", Thailand", "").strip()

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            self.in_link = False
            if self.current and self.text_parts:
                self.current["name"] = " ".join(self.text_parts).strip()

        if self.current and self.current["name"] and self.current["date"]:
            urls = {r["url"] for r in self.races}
            if self.current["url"] not in urls:
                self.races.append(self.current)
            self.current = None


def scrape():
    """Fetch ahotu Thailand pages for all sports."""
    all_races = []

    for sport, url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")

            parser = AhotuParser()
            parser.feed(html)

            race_type = AHOTU_TYPE_MAP.get(sport, "run")
            for r in parser.races:
                name = r["name"]
                loc = r.get("location", "")
                province = detect_province(f"{name} {loc}")

                slug = re.sub(r"[^a-z0-9]+", "-", name.lower())[:50].strip("-")
                all_races.append({
                    "id": f"ahotu:{slug}",
                    "name": name,
                    "url": r["url"],
                    "image": "",
                    "date": r["date"],
                    "dateDisplay": r["dateDisplay"],
                    "location": loc or name,
                    "province": province,
                    "country": "Thailand",
                    "source": "ahotu",
                    "type": race_type,
                    "distances": [],
                    "tags": [],
                    "organizer": None,
                    "price": None,
                })

            print(f"    Ahotu [{sport}]: {len(parser.races)} races")
        except Exception as e:
            print(f"    Ahotu [{sport}] error: {e}")

    seen = set()
    unique = []
    for r in all_races:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


if __name__ == "__main__":
    races = scrape()
    print(f"Found {len(races)} Thailand races on Ahotu:")
    for r in races:
        print(f"  {r['date']} [{r['type']:10s}] [{r['province']:15s}] {r['name'][:50]}")
