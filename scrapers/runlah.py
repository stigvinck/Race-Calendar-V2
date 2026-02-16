"""
Scraper: Runlah.com — All Thailand running races (EN + TH pages)
Fetches the week-view calendar which lists all upcoming races nationwide.
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

# Week view shows all upcoming races across Thailand
URLS = [
    ("EN", "https://www.runlah.com/en/calendar/week"),
    ("TH", "https://www.runlah.com/th/calendar/week"),
]
BASE = "https://www.runlah.com"

THAI_MONTHS = {
    "มกราคม": "January", "กุมภาพันธ์": "February", "มีนาคม": "March",
    "เมษายน": "April", "พฤษภาคม": "May", "มิถุนายน": "June",
    "กรกฎาคม": "July", "สิงหาคม": "August", "กันยายน": "September",
    "ตุลาคม": "October", "พฤศจิกายน": "November", "ธันวาคม": "December",
}

# Province name normalization (Thai → English)
PROVINCE_MAP = {
    "เชียงใหม่": "Chiang Mai", "กรุงเทพ": "Bangkok", "กรุงเทพมหานคร": "Bangkok",
    "ภูเก็ต": "Phuket", "เชียงราย": "Chiang Rai", "ขอนแก่น": "Khon Kaen",
    "นครราชสีมา": "Nakhon Ratchasima", "สงขลา": "Songkhla", "ชลบุรี": "Chonburi",
    "สุราษฎร์ธานี": "Surat Thani", "กระบี่": "Krabi", "ลำปาง": "Lampang",
    "น่าน": "Nan", "แพร่": "Phrae", "ตราด": "Trat", "เพชรบุรี": "Phetchaburi",
    "ประจวบคีรีขันธ์": "Prachuap Khiri Khan", "ระยอง": "Rayong",
    "พังงา": "Phang Nga", "นครปฐม": "Nakhon Pathom", "สุโขทัย": "Sukhothai",
    "เพชรบูรณ์": "Phetchabun", "ลำพูน": "Lamphun", "แม่ฮ่องสอน": "Mae Hong Son",
    "ตรัง": "Trang", "กาญจนบุรี": "Kanchanaburi", "พิษณุโลก": "Phitsanulok",
    "อุดรธานี": "Udon Thani", "หนองคาย": "Nong Khai", "ยะลา": "Yala",
    "สมุทรปราการ": "Samut Prakan", "นนทบุรี": "Nonthaburi",
    "ปทุมธานี": "Pathum Thani", "ราชบุรี": "Ratchaburi",
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
        "cycling", "bicycle", "bike", "จักรยาน", "gravel", "gran fondo",
    ]),
    ("swim", [
        "swim", "ว่ายน้ำ", "open water", "oceanman",
    ]),
    ("obstacle", [
        "obstacle", "spartan", "mud", "xrace",
    ]),
]

TAG_RULES = {
    "night run": ["night", "กลางคืน", "midnight"],
    "charity": ["charity", "การกุศล", "เพื่อ"],
    "relay": ["relay", "ekiden", "เอกิเด็น"],
    "kids": ["kids", "เด็ก", "ลูก", "junior"],
    "walk & run": ["walk", "เดิน-วิ่ง", "เดินวิ่ง"],
    "ultra": ["ultra", "อัลตร้า"],
}


def detect_type(name):
    lower = name.lower()
    for race_type, keywords in TYPE_RULES:
        for kw in keywords:
            if kw in lower:
                return race_type
    return "run"


def detect_distances(name):
    distances = []
    lower = name.lower()
    for m in re.finditer(r"(\d+)\s*(?:km|k)\b", lower):
        distances.append(f"{m.group(1)}K")
    if re.search(r"(?:full\s*)?marathon|ฟูลมาราธอน", lower) and "half" not in lower:
        if "42K" not in distances:
            distances.append("42K")
    if re.search(r"half|ฮาล์ฟ", lower):
        if "21K" not in distances:
            distances.append("21K")
    if re.search(r"mini|มินิ", lower):
        if "10K" not in distances:
            distances.append("10K")
    return sorted(set(distances)) if distances else []


def detect_tags(name):
    lower = name.lower()
    tags = []
    for tag, keywords in TAG_RULES.items():
        for kw in keywords:
            if kw in lower:
                tags.append(tag)
                break
    return tags


def normalize_province(location_text):
    """Extract province name from location text."""
    # Check for English province names
    if "province" in location_text.lower():
        m = re.search(r"(.+?)\s+province", location_text, re.IGNORECASE)
        if m:
            return m.group(1).strip().replace(",", "").strip()

    # Check Thai province names
    for thai, eng in PROVINCE_MAP.items():
        if thai in location_text:
            return eng

    # Check English province names directly
    known_en = [
        "Chiang Mai", "Bangkok", "Phuket", "Chiang Rai", "Khon Kaen",
        "Nakhon Ratchasima", "Songkhla", "Chonburi", "Surat Thani",
        "Krabi", "Nan", "Phrae", "Trat", "Prachuap Khiri Khan",
        "Phetchabun", "Lampang", "Lamphun", "Mae Hong Son", "Rayong",
        "Kanchanaburi", "Sukhothai", "Nakhon Pathom", "Phang Nga",
        "Udon Thani", "Nong Khai", "Yala", "Samut Prakan", "Nonthaburi",
        "Phitsanulok", "Trang", "Ratchaburi", "Pathum Thani",
    ]
    for prov in known_en:
        if prov.lower() in location_text.lower():
            return prov

    return "Other"


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
                        "name": "", "url": BASE + "/en/" + event_id,
                        "image": "", "date": "", "dateDisplay": "",
                        "location": "", "province": "Other",
                        "country": "Thailand",
                        "source": "runlah", "type": "run",
                        "distances": [], "tags": [],
                        "organizer": None, "price": None,
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
                r"September|October|November|December)\s+\d{1,2},\s+\d{4})$", text)
            if m:
                r["dateDisplay"] = m.group(1)
                try:
                    r["date"] = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass

            m2 = re.match(
                r"^(\d{1,2})(?:-\d{1,2})?\s+"
                r"((?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{4})$", text)
            if m2 and not r["date"]:
                r["dateDisplay"] = text
                try:
                    r["date"] = datetime.strptime(
                        f"{m2.group(1)} {m2.group(2)}", "%d %B %Y").strftime("%Y-%m-%d")
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

        # Location — capture any location text with province info
        if not r["location"] or r["province"] == "Other":
            # Check if text contains province-like info
            has_province = ("province" in text.lower() or
                           "จังหวัด" in text or "จ." in text or
                           any(thai in text for thai in PROVINCE_MAP))
            has_english_prov = any(p in text for p in [
                "Chiang Mai", "Bangkok", "Phuket", "Chiang Rai",
                "Khon Kaen", "Chonburi", "Songkhla", "Krabi",
            ])
            if has_province or has_english_prov:
                r["location"] = (text.replace(" province", "")
                                 .replace("จังหวัด", "").replace("จ.", "").strip())
                r["province"] = normalize_province(text)

    def handle_endtag(self, tag):
        if self.current and self.current["name"] and self.current["date"]:
            ids = {r["id"] for r in self.races}
            if self.current["id"] not in ids:
                r = self.current
                if not r["location"]:
                    r["location"] = "Thailand"
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
    """Fetch EN + TH week views, merge, return all Thailand races."""
    all_races = []
    for label, url in URLS:
        try:
            races = fetch_and_parse(url)
            print(f"    Runlah [{label}]: {len(races)} races")
            all_races.extend(races)
        except Exception as e:
            print(f"    Runlah [{label}] error: {e}")

    # Also fetch province-specific pages for Chiang Mai and Bangkok
    # (week view may not show all future races)
    for prov in ["Chiang+Mai", "Bangkok"]:
        for lang in ["en", "th"]:
            url = f"{BASE}/{lang}/calendar/location?province={prov}"
            try:
                races = fetch_and_parse(url)
                print(f"    Runlah [{lang}/{prov}]: {len(races)} races")
                all_races.extend(races)
            except Exception as e:
                print(f"    Runlah [{lang}/{prov}] error: {e}")

    seen = set()
    unique = []
    for r in sorted(all_races, key=lambda x: x["date"]):
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


if __name__ == "__main__":
    races = scrape()
    print(f"\nFound {len(races)} races on Runlah:")
    for r in races:
        print(f"  {r['date']} [{r['type']:8s}] [{r['province']:15s}] {r['name'][:50]}")
