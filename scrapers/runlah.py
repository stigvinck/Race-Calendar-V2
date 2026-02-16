"""
Scraper: Runlah.com — All Thailand running races via province pages (EN + TH)
The week/calendar views are JS-rendered ("Loading...") so we must use
the province-specific location pages which server-render race cards.
"""

import re
import urllib.request
import time
from html.parser import HTMLParser
from datetime import datetime

BASE = "https://www.runlah.com"

# Complete list of all 77 Thai provinces as they appear in Runlah URLs
ALL_PROVINCES = [
    "Bangkok", "Chiang Mai", "Chiang Rai", "Chon Buri", "Nakhon Ratchasima",
    "Khon Kaen", "Phuket", "Songkhla", "Surat Thani", "Krabi",
    "Lampang", "Lamphun", "Nan", "Phrae", "Phayao",
    "Mae Hong Son", "Phitsanulok", "Sukhothai", "Uttaradit",
    "Kanchanaburi", "Kamphaeng Phet", "Phichit", "Phetchabun",
    "Suphan Buri", "Tak", "Uthai Thani",
    "Ang Thong", "Chai Nat", "Lop Buri", "Nakhon Nayok",
    "Prachin Buri", "Nakhon Sawan",
    "Phra Nakhon Si Ayutthaya", "Pathum Thani", "Sing Buri", "Saraburi",
    "Nonthaburi", "Nakhon Pathom", "Phetchaburi", "Prachuap Khiri Khan",
    "Ratchaburi", "Samut Prakarn", "Samut Sakhon", "Samut Songkhram",
    "Si Sa Ket", "Ubon Ratchathani", "Amnat Charoen", "Yasothon",
    "Chachoengsao", "Chanthaburi", "Sa Kaeo", "Rayong", "Trat",
    "Buri Ram", "Chaiyaphum", "Kalasin", "Maha Sarakham",
    "Roi Et", "Surin", "Loei", "Nong Khai",
    "Sakon Nakhon", "Udon Thani", "Nong Bua Lam Phu", "Nakhon Phanom",
    "Mukdahan", "Narathiwat", "Pattani", "Yala", "Bueng Kan",
    "Chumphon", "Nakhon Si Thammarat", "Phang-nga", "Phatthalung",
    "Ranong", "Satun", "Trang",
]

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


# Normalize province names from Runlah's URL format
def normalize_province(url_province):
    """Map Runlah URL province name to our canonical name."""
    mapping = {
        "Phang-nga": "Phang Nga",
        "Samut Prakarn": "Samut Prakan",
        "Chon Buri": "Chonburi",
    }
    return mapping.get(url_province, url_province)


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
                        "event_id": event_id,
                        "name": "", "url": BASE + "/en/" + event_id,
                        "image": "", "date": "", "dateDisplay": "",
                        "location": "",
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
            skip = {"Detail", "Register now!", "View all other events...",
                    "Please click on a province", "Loading..."}
            if text not in skip and not text.startswith("Bangkok and"):
                r["name"] = text

        # Date — English formats
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
                        month_idx = list(THAI_MONTHS.values()).index(eng_month) + 1
                        dt = datetime(ce_year, month_idx, day)
                        r["date"] = dt.strftime("%Y-%m-%d")
                        r["dateDisplay"] = f"{eng_month} {day}, {ce_year}"
                    except ValueError:
                        pass
                    break

        # Location text
        if not r["location"]:
            has_province = ("province" in text.lower() or
                           "จังหวัด" in text or "จ." in text)
            if has_province:
                r["location"] = (text.replace(" province", "")
                                 .replace("จังหวัด", "").replace("จ.", "").strip())

    def handle_endtag(self, tag):
        if self.current and self.current["name"] and self.current["date"]:
            ids = {r["event_id"] for r in self.races}
            if self.current["event_id"] not in ids:
                self.races.append(self.current)
            self.current = None


def fetch_province(province, lang="en"):
    """Fetch a single province page and return parsed races."""
    url_prov = province.replace(" ", "+")
    url = f"{BASE}/{lang}/calendar/location?province={url_prov}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8")
        parser = RunlahParser()
        parser.feed(html)
        return parser.races
    except Exception as e:
        return []


def scrape():
    """Fetch all province pages (EN + TH) and merge races."""
    all_races = {}  # keyed by event_id

    for province in ALL_PROVINCES:
        canonical = normalize_province(province)

        for lang in ["en", "th"]:
            races = fetch_province(province, lang)
            for r in races:
                eid = r["event_id"]
                if eid not in all_races:
                    all_races[eid] = {
                        "id": f"runlah:{eid}",
                        "name": r["name"],
                        "url": r["url"],
                        "image": r["image"],
                        "date": r["date"],
                        "dateDisplay": r["dateDisplay"],
                        "location": r["location"] or canonical,
                        "province": canonical,
                        "country": "Thailand",
                        "source": "runlah",
                        "type": detect_type(r["name"]),
                        "distances": detect_distances(r["name"]),
                        "tags": detect_tags(r["name"]),
                        "organizer": None,
                        "price": None,
                    }
                else:
                    # Update with English name if we had Thai first
                    existing = all_races[eid]
                    if lang == "en" and r["name"]:
                        existing["name"] = r["name"]
                    if not existing["image"] and r["image"]:
                        existing["image"] = r["image"]

            # Small delay to be polite
            time.sleep(0.3)

        if all_races:
            # Progress log every 10 provinces
            idx = ALL_PROVINCES.index(province)
            if (idx + 1) % 10 == 0:
                print(f"    Runlah: {idx + 1}/{len(ALL_PROVINCES)} provinces, {len(all_races)} races so far")

    result = sorted(all_races.values(), key=lambda x: x["date"])
    print(f"    Runlah: Done — {len(result)} races from {len(ALL_PROVINCES)} provinces")
    return result


if __name__ == "__main__":
    races = scrape()
    print(f"\nFound {len(races)} races on Runlah:")
    for r in races:
        print(f"  {r['date']} [{r['type']:8s}] [{r['province']:20s}] {r['name'][:50]}")
