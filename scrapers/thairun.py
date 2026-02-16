"""
Scraper: thai.run — Thai race registration platform
Scrapes event listings from the thai.run platform.
"""

import re
import json
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

CALENDAR_URL = "https://thai.run/events"

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

THAI_MONTHS = {
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03",
    "เมษายน": "04", "พฤษภาคม": "05", "มิถุนายน": "06",
    "กรกฎาคม": "07", "สิงหาคม": "08", "กันยายน": "09",
    "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
    "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
    "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
    "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
}

PROVINCE_KEYWORDS = {
    "Chiang Mai": ["chiang mai", "chiangmai", "เชียงใหม่"],
    "Bangkok": ["bangkok", "กรุงเทพ"],
    "Phuket": ["phuket", "ภูเก็ต"],
    "Chiang Rai": ["chiang rai", "เชียงราย"],
    "Chon Buri": ["chon buri", "chonburi", "pattaya", "ชลบุรี"],
    "Nakhon Ratchasima": ["nakhon ratchasima", "korat", "โคราช"],
    "Khon Kaen": ["khon kaen", "ขอนแก่น"],
    "Surat Thani": ["surat thani", "samui", "สุราษฎร์ธานี"],
    "Krabi": ["krabi", "กระบี่"],
    "Prachuap Khiri Khan": ["prachuap", "hua hin", "หัวหิน", "ประจวบคีรีขันธ์"],
    "Songkhla": ["songkhla", "สงขลา"],
    "Phetchabun": ["phetchabun", "khao kho", "เพชรบูรณ์"],
    "Nan": ["nan", "น่าน"],
    "Lampang": ["lampang", "ลำปาง"],
    "Sukhothai": ["sukhothai", "สุโขทัย"],
    "Trang": ["trang", "ตรัง"],
    "Rayong": ["rayong", "ระยอง"],
    "Trat": ["trat", "ตราด"],
    "Phrae": ["phrae", "แพร่"],
    "Nong Khai": ["nong khai", "หนองคาย"],
    "Nakhon Sawan": ["nakhon sawan", "นครสวรรค์"],
    "Mae Hong Son": ["mae hong son", "pai", "แม่ฮ่องสอน"],
    "Yala": ["yala", "betong", "ยะลา"],
    "Nakhon Pathom": ["nakhon pathom", "นครปฐม"],
    "Prachin Buri": ["prachin buri", "ปราจีนบุรี"],
}


def detect_province(text):
    lower = text.lower()
    for province, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return province
    return None


def detect_type(text):
    lower = text.lower()
    if "trail" in lower or "ultra" in lower:
        return "trail"
    if "triathlon" in lower or "tri " in lower or "duathlon" in lower:
        return "triathlon"
    if "cycling" in lower or "bike" in lower or "fondo" in lower:
        return "cycling"
    if "swim" in lower or "open water" in lower or "aqua" in lower:
        return "swim"
    if "obstacle" in lower or "ocr" in lower or "spartan" in lower:
        return "obstacle"
    return "run"


def parse_date(text):
    if not text:
        return None
    text = text.strip()

    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)

    # DD Month YYYY
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)

    # Thai date: DD เดือน YYYY
    for thai_month, mm in THAI_MONTHS.items():
        if thai_month in text:
            m = re.search(r'(\d{1,2})\s*' + re.escape(thai_month), text)
            if m:
                day = int(m.group(1))
                year_m = re.search(r'(\d{4})', text)
                if year_m:
                    year = int(year_m.group(1))
                    # Convert Buddhist year if needed
                    if year > 2500:
                        year -= 543
                    return "%d-%s-%02d" % (year, mm, day)

    return None


class ThaiRunParser(HTMLParser):
    """Parse thai.run events page."""

    def __init__(self):
        super().__init__()
        self.races = []
        self.in_event = False
        self.current_tag = None
        self.current_attrs = {}
        self.texts = []
        self.links = []
        self.images = []
        self.event_html = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")

        # Look for event cards/items
        if "event" in cls.lower() or "card" in cls.lower():
            self.in_event = True
            self.texts = []
            self.links = []
            self.images = []

        if self.in_event:
            if tag == "a":
                href = attr_dict.get("href", "")
                if href:
                    self.links.append(href)
            if tag == "img":
                src = attr_dict.get("src", "")
                if src:
                    self.images.append(src)

    def handle_data(self, data):
        if self.in_event:
            text = data.strip()
            if text:
                self.texts.append(text)

    def handle_endtag(self, tag):
        if tag in ("div", "article", "section", "li") and self.in_event and self.texts:
            self._try_extract()
            self.in_event = False

    def _try_extract(self):
        all_text = " ".join(self.texts)
        if len(all_text) < 5:
            return

        # Find longest text as name
        name = max(self.texts, key=len) if self.texts else ""
        if len(name) < 3:
            return

        # Find date
        date_str = None
        for t in self.texts:
            d = parse_date(t)
            if d:
                date_str = d
                break

        # Find URL
        url = ""
        for link in self.links:
            if "thai.run" in link or link.startswith("/"):
                if link.startswith("/"):
                    url = "https://thai.run" + link
                else:
                    url = link
                break

        province = detect_province(all_text)
        race_type = detect_type(name)

        race = {
            "id": "thairun-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40]),
            "name": name,
            "date": date_str or "TBA",
            "type": race_type,
            "province": province or "Unknown",
            "location": "",
            "url": url,
            "image": self.images[0] if self.images else "",
            "source": "ThaiRun",
            "distances": [],
            "tags": [],
        }
        self.races.append(race)


def scrape():
    """Scrape thai.run events page."""
    print("    [ThaiRun] Fetching events page...")
    races = []

    try:
        req = urllib.request.Request(CALENDAR_URL, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Check if page is SSR or SPA
        if "Loading" in html and len(html) < 5000:
            print("    [ThaiRun] Page appears to be JS-rendered, trying alternate approach...")
            # Try API endpoint
            return scrape_api()

        parser = ThaiRunParser()
        parser.feed(html)
        races = parser.races

        # Also try regex-based extraction for robustness
        if len(races) < 3:
            races = scrape_regex(html)

        print("    [ThaiRun] Parsed %d races" % len(races))

    except Exception as e:
        print("    [ThaiRun] Error: %s" % e)

    return races


def scrape_api():
    """Try to hit thai.run API directly."""
    races = []
    try:
        # thai.run uses /event/ paths for individual events
        # Try to find a list/API endpoint
        api_urls = [
            "https://thai.run/api/events",
            "https://thai.run/api/v1/events",
        ]
        for api_url in api_urls:
            try:
                req = urllib.request.Request(api_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, list):
                        for item in data:
                            race = parse_api_item(item)
                            if race:
                                races.append(race)
                    elif isinstance(data, dict) and "data" in data:
                        for item in data["data"]:
                            race = parse_api_item(item)
                            if race:
                                races.append(race)
                    if races:
                        break
            except Exception:
                continue
    except Exception as e:
        print("    [ThaiRun] API error: %s" % e)
    return races


def parse_api_item(item):
    """Parse a single API response item."""
    if not isinstance(item, dict):
        return None
    name = item.get("name", "") or item.get("title", "")
    if not name:
        return None

    date_str = item.get("date", "") or item.get("start_date", "") or item.get("event_date", "")
    if date_str:
        date_str = parse_date(date_str) or date_str[:10]

    province = detect_province(name + " " + str(item.get("location", "")))

    return {
        "id": "thairun-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40]),
        "name": name,
        "date": date_str or "TBA",
        "type": detect_type(name),
        "province": province or "Unknown",
        "location": item.get("location", ""),
        "url": item.get("url", "") or ("https://thai.run/event/" + str(item.get("slug", ""))),
        "image": item.get("image", "") or item.get("cover", ""),
        "source": "ThaiRun",
        "distances": [],
        "tags": [],
    }


def scrape_regex(html):
    """Fallback regex extraction from HTML."""
    races = []
    # Look for event links with dates
    pattern = re.compile(
        r'<a[^>]*href=["\']([^"\']*(?:event|race)[^"\']*)["\'][^>]*>.*?'
        r'([\w\s]+(?:run|marathon|trail|race|triathlon)[\w\s]*)',
        re.IGNORECASE | re.DOTALL
    )
    for match in pattern.finditer(html):
        url = match.group(1)
        name = match.group(2).strip()
        if len(name) > 3 and len(name) < 100:
            province = detect_province(name)
            races.append({
                "id": "thairun-" + re.sub(r'[^a-z0-9]', '', name.lower()[:40]),
                "name": name,
                "date": "TBA",
                "type": detect_type(name),
                "province": province or "Unknown",
                "location": "",
                "url": url if url.startswith("http") else "https://thai.run" + url,
                "image": "",
                "source": "ThaiRun",
                "distances": [],
                "tags": [],
            })
    return races
