"""
Scraper: worldsmarathons.com — Thailand endurance races
Scrapes the Thailand country page for all race types.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

URLS = [
    "https://worldsmarathons.com/country/thailand",
]
BASE = "https://worldsmarathons.com"

# Province detection from location text
PROVINCE_KEYWORDS = {
    "chiang mai": "Chiang Mai", "chiangmai": "Chiang Mai", "chiang dao": "Chiang Mai",
    "mae rim": "Chiang Mai", "doi suthep": "Chiang Mai", "doi saket": "Chiang Mai",
    "bangkok": "Bangkok", "phuket": "Phuket", "chiang rai": "Chiang Rai",
    "khon kaen": "Khon Kaen", "nakhon ratchasima": "Nakhon Ratchasima",
    "korat": "Nakhon Ratchasima", "songkhla": "Songkhla", "chonburi": "Chonburi",
    "pattaya": "Chonburi", "bangsaen": "Chonburi", "bang saen": "Chonburi",
    "surat thani": "Surat Thani", "samui": "Surat Thani",
    "krabi": "Krabi", "nan": "Nan", "phrae": "Phrae", "trat": "Trat",
    "hua hin": "Prachuap Khiri Khan", "prachuap": "Prachuap Khiri Khan",
    "phetchabun": "Phetchabun", "khao kho": "Phetchabun",
    "lampang": "Lampang", "lamphun": "Lamphun", "sukhothai": "Sukhothai",
    "kanchanaburi": "Kanchanaburi", "rayong": "Rayong", "phang nga": "Phang Nga",
    "mae hong son": "Mae Hong Son", "pai": "Mae Hong Son",
    "yala": "Yala", "betong": "Yala", "nong khai": "Nong Khai",
    "udon thani": "Udon Thani", "ayutthaya": "Phra Nakhon Si Ayutthaya",
    "nakhon pathom": "Nakhon Pathom", "phitsanulok": "Phitsanulok",
    "nakhon sawan": "Nakhon Sawan", "trang": "Trang",
}

TYPE_MAP = {
    "marathon": "run", "half marathon": "run", "10k": "run", "5k": "run",
    "ultra": "trail", "trail": "trail", "ultramarathon": "trail",
    "triathlon": "triathlon", "duathlon": "triathlon",
    "cycling": "cycling", "bike": "cycling",
    "swimming": "swim", "open water": "swim",
    "obstacle": "obstacle",
}


def detect_province(text):
    lower = text.lower()
    for kw, prov in PROVINCE_KEYWORDS.items():
        if kw in lower:
            return prov
    return "Other"


def detect_type_from_text(text):
    lower = text.lower()
    for kw, rtype in TYPE_MAP.items():
        if kw in lower:
            return rtype
    return "run"


class WMParser(HTMLParser):
    """Parse race cards from worldsmarathons.com."""
    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None
        self.in_link = False
        self.text_buf = ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = d.get("href", "")

        if tag == "a" and href and "/marathon/" in href:
            self.current = {
                "url": BASE + href if href.startswith("/") else href,
                "name": "", "date": "", "dateDisplay": "",
                "location": "", "type_raw": "",
            }
            self.in_link = True
            self.text_buf = ""

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self.in_link:
            self.text_buf += " " + text
        if self.current:
            # Date patterns
            if not self.current["date"]:
                # "DD Mon YYYY" or "Mon DD, YYYY"
                for fmt in ["%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y"]:
                    try:
                        dt = datetime.strptime(text, fmt)
                        self.current["date"] = dt.strftime("%Y-%m-%d")
                        self.current["dateDisplay"] = text
                        break
                    except ValueError:
                        pass

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            self.in_link = False
            if self.current and self.text_buf.strip():
                self.current["name"] = self.text_buf.strip()

        if self.current and self.current["name"] and self.current["date"]:
            self.races.append(self.current)
            self.current = None


def scrape():
    """Fetch worldsmarathons Thailand page and extract races."""
    all_races = []

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")

            parser = WMParser()
            parser.feed(html)

            for r in parser.races:
                name = r["name"]
                province = detect_province(name + " " + r.get("location", ""))
                race_type = detect_type_from_text(name)

                slug = re.sub(r"[^a-z0-9]+", "-", name.lower())[:50].strip("-")
                all_races.append({
                    "id": f"wm:{slug}",
                    "name": name,
                    "url": r["url"],
                    "image": "",
                    "date": r["date"],
                    "dateDisplay": r["dateDisplay"],
                    "location": r.get("location", "") or name,
                    "province": province,
                    "country": "Thailand",
                    "source": "worldsmarathons",
                    "type": race_type,
                    "distances": [],
                    "tags": [],
                    "organizer": None,
                    "price": None,
                })

            print(f"    WorldsMarathons: {len(parser.races)} races")
        except Exception as e:
            print(f"    WorldsMarathons error: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for r in all_races:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


if __name__ == "__main__":
    races = scrape()
    print(f"Found {len(races)} races:")
    for r in races:
        print(f"  {r['date']} [{r['type']:8s}] {r['name'][:50]}")
