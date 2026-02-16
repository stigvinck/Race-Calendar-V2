"""
Scraper: Runlah.com — Chiang Mai running races (EN + TH pages)
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

URL_EN = "https://www.runlah.com/en/calendar/location?province=Chiang+Mai"
URL_TH = "https://www.runlah.com/th/calendar/location?province=Chiang+Mai"
BASE = "https://www.runlah.com"

THAI_MONTHS = {
    "มกราคม": "January", "กุมภาพันธ์": "February", "มีนาคม": "March",
    "เมษายน": "April", "พฤษภาคม": "May", "มิถุนายน": "June",
    "กรกฎาคม": "July", "สิงหาคม": "August", "กันยายน": "September",
    "ตุลาคม": "October", "พฤศจิกายน": "November", "ธันวาคม": "December",
}

SKIP_HREFS = {
    "/en", "/en/calendar", "/en/results", "/en/promote", "/en/about",
    "/en/terms", "/en/privacy", "/en/user/registers", "/en/user/settings",
    "/th", "/th/calendar", "/th/results", "/th/promote", "/th/about",
    "/th/terms", "/th/privacy", "/th/user/registers", "/th/user/settings",
}

# ── Race type detection ────────────────────────────
TYPE_RULES = [
    ("trail", [
        "trail", "เทรล", "cross country", "ครอสคันทรี",
        "mountain", "jungle", "doi", "ดอย", "เขา",
    ]),
    ("triathlon", [
        "triathlon", "ไตรกีฬา", "duathlon", "aquathlon",
    ]),
    ("cycling", [
        "cycling", "bicycle", "bike", "จักรยาน", "gravel",
    ]),
    ("swim", [
        "swim", "ว่ายน้ำ", "open water",
    ]),
    ("obstacle", [
        "obstacle", "spartan", "mud",
    ]),
]

# ── Distance detection ─────────────────────────────
DISTANCE_PATTERNS = [
    r"(\d+)\s*(?:km|K)\b",
    r"(?:fun\s*run|ฟันรัน)",
    r"(?:mini|มินิ)\s*(?:marathon|มาราธอน)",
    r"(?:half|ฮาล์ฟ)\s*(?:marathon|มาราธอน)",
    r"(?:full\s*)?(?:marathon|มาราธอน)",
    r"(?:ultra|อัลตร้า)",
    r"(?:ekiden|เอกิเด็น)",
]

# ── Tag detection ──────────────────────────────────
TAG_RULES = {
    "night run": ["night", "กลางคืน", "dusk", "dawn"],
    "charity": ["charity", "การกุศล", "เพื่อ"],
    "relay": ["relay", "ekiden", "เอกิเด็น"],
    "kids": ["kids", "เด็ก", "ลูก", "junior"],
    "walk & run": ["walk", "เดิน-วิ่ง", "เดินวิ่ง"],
    "ultra": ["ultra", "อัลตร้า"],
}


def detect_type(name):
    """Detect race type from name keywords."""
    lower = name.lower()
    for race_type, keywords in TYPE_RULES:
        for kw in keywords:
            if kw in lower:
                return race_type
    return "run"


def detect_distances(name):
    """Extract distance labels from race name."""
    distances = []
    lower = name.lower()

    # Numeric distances
    for m in re.finditer(r"(\d+)\s*(?:km|k)\b", lower):
        distances.append(f"{m.group(1)}K")

    # Named distances
    if re.search(r"(?:full\s*)?marathon|ฟูลมาราธอน", lower) and "half" not in lower:
        if "42K" not in distances:
            distances.append("42K")
    if re.search(r"half|ฮาล์ฟ", lower):
        if "21K" not in distances:
            distances.append("21K")
    if re.search(r"mini|มินิ", lower):
        if "10K" not in distances:
            distances.append("10K")
    if re.search(r"ultra|อัลตร้า", lower):
        distances.append("Ultra")

    return sorted(set(distances)) if distances else []


def detect_tags(name):
    """Detect tags from race name."""
    lower = name.lower()
    tags = []
    for tag, keywords in TAG_RULES.items():
        for kw in keywords:
            if kw in lower:
                tags.append(tag)
                break
    return tags


class RunlahParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = d.get("href", "")
        src = d.get("src", "")

        if tag == "a" and href and re.match(r"^/(en|th)/[A-Za-z0-9_]+$", href):
            if "/teams/" not in href and href not in SKIP_HREFS:
                if self.current is None:
                    event_id = href.split("/")[-1]
                    self.current = {
                        "id": f"runlah:{event_id}",
                        "name": "",
                        "url": BASE + "/en/" + event_id,
                        "image": "",
                        "date": "",
                        "dateDisplay": "",
                        "location": "",
                        "province": "Chiang Mai",
                        "source": "runlah",
                        "type": "run",
                        "distances": [],
                        "tags": [],
                        "organizer": None,
                        "price": None,
                    }

        if tag == "img" and self.current and not self.current["image"]:
            if src and "/images/event/" in src:
                self.current["image"] = (BASE + src) if src.startswith("/") else src

    def handle_data(self, data):
        text = data.strip()
        if not text or not self.current:
            return

        r = self.current

        # Name
        if not r["name"] and len(text) > 3:
            if text not in ("Detail", "Register now!", "View all other events..."):
                r["name"] = text

        # Date — "Month DD, YYYY"
        if not r["date"]:
            m = re.match(
                r"^((?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{1,2},\s+\d{4})$", text
            )
            if m:
                r["dateDisplay"] = m.group(1)
                try:
                    r["date"] = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass

            # "DD-DD Month YYYY" or "DD Month YYYY"
            m2 = re.match(
                r"^(\d{1,2})(?:-\d{1,2})?\s+"
                r"((?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{4})$", text
            )
            if m2 and not r["date"]:
                r["dateDisplay"] = text
                try:
                    r["date"] = datetime.strptime(
                        f"{m2.group(1)} {m2.group(2)}", "%d %B %Y"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass

            # Thai date: Buddhist year
            for thai_month, eng_month in THAI_MONTHS.items():
                pattern = rf"(\d{{1,2}})\s+{thai_month}\s+(\d{{4}})"
                m3 = re.search(pattern, text)
                if m3 and not r["date"]:
                    day = int(m3.group(1))
                    ce_year = int(m3.group(2)) - 543
                    try:
                        dt = datetime(ce_year, list(THAI_MONTHS.values()).index(eng_month) + 1, day)
                        r["date"] = dt.strftime("%Y-%m-%d")
                        r["dateDisplay"] = f"{eng_month} {day}, {ce_year}"
                    except ValueError:
                        pass
                    break

        # Location
        if not r["location"]:
            is_cm = ("Chiang Mai" in text and "province" in text.lower()) or \
                    ("เชียงใหม่" in text)
            if is_cm:
                r["location"] = text.replace(" province", "").replace("จังหวัด", "").strip()

    def handle_endtag(self, tag):
        if self.current and self.current["name"] and self.current["date"]:
            urls = {r["url"] for r in self.races}
            if self.current["url"] not in urls:
                r = self.current
                if not r["location"]:
                    r["location"] = "Chiang Mai"
                # Detect type, distances, tags from name
                r["type"] = detect_type(r["name"])
                r["distances"] = detect_distances(r["name"])
                r["tags"] = detect_tags(r["name"])
                self.races.append(r)
            self.current = None


def fetch_and_parse(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    parser = RunlahParser()
    parser.feed(html)
    return parser.races


def scrape():
    """Fetch EN + TH pages, merge, return race list."""
    all_races = []
    for url, label in [(URL_EN, "EN"), (URL_TH, "TH")]:
        try:
            races = fetch_and_parse(url)
            print(f"    Runlah [{label}]: {len(races)} races")
            all_races.extend(races)
        except Exception as e:
            print(f"    Runlah [{label}] error: {e}")

    seen = set()
    unique = []
    for r in sorted(all_races, key=lambda x: x["date"]):
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


if __name__ == "__main__":
    races = scrape()
    print(f"Found {len(races)} Chiang Mai races on Runlah:")
    for r in races:
        print(f"  {r['date']} [{r['type']}] {r['name']} {r['distances']}")
