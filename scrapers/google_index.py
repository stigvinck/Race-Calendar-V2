"""
Google search index scraper helper.
For JS-rendered sites (Checkrace, race.thai.run) that can't be scraped directly,
we use Google's search index which has already rendered the pages.

We parse event names, dates, provinces from search result titles and snippets.
"""

import re
import time
import random
import urllib.request
import urllib.parse
from html import unescape

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# Thai month abbreviations -> month numbers
THAI_MONTHS_ABBR = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4,
    "พ.ค.": 5, "มิ.ย.": 6, "ก.ค.": 7, "ส.ค.": 8,
    "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}

# Thai full month names -> month numbers
THAI_MONTHS_FULL = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}

# English month names
EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# Thai province names (common ones found in race events)
THAI_PROVINCES = {
    "กรุงเทพ": "Bangkok", "กรุงเทพมหานคร": "Bangkok", "Bangkok": "Bangkok",
    "เชียงใหม่": "Chiang Mai", "Chiang Mai": "Chiang Mai",
    "เชียงราย": "Chiang Rai", "Chiang Rai": "Chiang Rai",
    "ภูเก็ต": "Phuket", "Phuket": "Phuket",
    "นครราชสีมา": "Nakhon Ratchasima", "โคราช": "Nakhon Ratchasima",
    "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
    "สุราษฎร์ธานี": "Surat Thani",
    "ชลบุรี": "Chon Buri", "Chon Buri": "Chon Buri",
    "เพชรบุรี": "Phetchaburi",
    "กาญจนบุรี": "Kanchanaburi", "Kanchanaburi": "Kanchanaburi",
    "นครนายก": "Nakhon Nayok",
    "ระยอง": "Rayong",
    "จันทบุรี": "Chanthaburi",
    "ตราด": "Trat",
    "หัวหิน": "Prachuap Khiri Khan",
    "พัทยา": "Chon Buri",
    "เขาใหญ่": "Nakhon Ratchasima",
    "Khao Yai": "Nakhon Ratchasima",
    "สมุทรปราการ": "Samut Prakan",
    "ปทุมธานี": "Pathum Thani",
    "นนทบุรี": "Nonthaburi",
    "อุดรธานี": "Udon Thani",
    "ขอนแก่น": "Khon Kaen",
    "เลย": "Loei",
    "น่าน": "Nan",
    "ลำปาง": "Lampang",
    "ลำพูน": "Lamphun",
    "แม่ฮ่องสอน": "Mae Hong Son",
    "สุโขทัย": "Sukhothai",
    "อยุธยา": "Phra Nakhon Si Ayutthaya",
    "พระนครศรีอยุธยา": "Phra Nakhon Si Ayutthaya",
    "สงขลา": "Songkhla",
    "หาดใหญ่": "Songkhla",
    "นครปฐม": "Nakhon Pathom",
    "สมุทรสาคร": "Samut Sakhon",
    "ราชบุรี": "Ratchaburi",
    "นครพนม": "Nakhon Phanom",
    "อุบลราชธานี": "Ubon Ratchathani",
    "บุรีรัมย์": "Buriram",
    "สระบุรี": "Saraburi",
    "นครสวรรค์": "Nakhon Sawan",
    "พิษณุโลก": "Phitsanulok",
    "ตรัง": "Trang",
    "กระบี่": "Krabi",
    "พังงา": "Phang Nga",
    "สตูล": "Satun",
    "ยะลา": "Yala",
    "ปัตตานี": "Pattani",
    "นราธิวาส": "Narathiwat",
    "ชุมพร": "Chumphon",
    "ระนอง": "Ranong",
    "แพร่": "Phrae",
    "พะเยา": "Phayao",
    "ปราจีนบุรี": "Prachin Buri",
    "ฉะเชิงเทรา": "Chachoengsao",
    "สระแก้ว": "Sa Kaeo",
    "นครศรีธรรมราช": "Nakhon Si Thammarat",
    "ปราณบุรี": "Prachuap Khiri Khan",
    "Pranburi": "Prachuap Khiri Khan",
}


def google_search(query, num_results=30):
    """
    Search Google and return list of {title, url, snippet} dicts.
    Makes multiple paginated requests if needed.
    """
    results = []
    start = 0
    per_page = 10

    while len(results) < num_results:
        params = urllib.parse.urlencode({
            "q": query,
            "start": start,
            "num": per_page,
            "hl": "th",       # Thai language results
            "gl": "th",       # Thailand region
        })
        url = f"https://www.google.com/search?{params}"

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            page_results = parse_google_results(html)
            if not page_results:
                break  # No more results or blocked

            results.extend(page_results)
            start += per_page

            # Be polite - random delay between pages
            if len(results) < num_results:
                time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            print(f"    [GoogleSearch] Error at start={start}: {e}")
            break

    return results[:num_results]


def parse_google_results(html):
    """Parse search results from Google HTML."""
    results = []

    # Clean up HTML entities
    html = unescape(html)

    # Pattern 1: Standard search result blocks
    # Look for <a href="/url?q=..."> followed by title and snippet
    blocks = re.findall(
        r'<a\s+href="/url\?q=([^"&]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?(?:<span[^>]*class="[^"]*"[^>]*>(.*?)</span>|<div[^>]*class="[^"]*"[^>]*>(.*?)</div>)',
        html, re.DOTALL
    )

    for block in blocks:
        url = urllib.parse.unquote(block[0])
        title = re.sub(r'<[^>]+>', '', block[1]).strip()
        snippet = re.sub(r'<[^>]+>', '', block[2] or block[3] or '').strip()

        if title and url.startswith('http'):
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
            })

    # Pattern 2: Simpler fallback - just find h3 titles with nearby links
    if not results:
        # Try to extract from cite + h3 patterns
        link_blocks = re.findall(
            r'<a[^>]+href="(/url\?q=([^"&]+)[^"]*)"[^>]*>[\s\S]*?<h3[^>]*>([\s\S]*?)</h3>',
            html
        )
        for _, url, title in link_blocks:
            url = urllib.parse.unquote(url)
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title and url.startswith('http'):
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": "",
                })

    return results


def extract_date_from_text(text):
    """
    Try to extract a date (YYYY-MM-DD) from Thai or English text.
    Handles Buddhist year (2568/2569 etc).
    Returns date string or "TBA".
    """
    if not text:
        return "TBA"

    # Pattern: DD ม.ค. YYYY or DD-DD ม.ค. YYYY (Thai abbreviated)
    for thai_m, num in THAI_MONTHS_ABBR.items():
        pat = rf'(\d{{1,2}})\s*(?:-\s*\d{{1,2}}\s*)?{re.escape(thai_m)}\s*(\d{{4}})'
        m = re.search(pat, text)
        if m:
            day = int(m.group(1))
            year = int(m.group(2))
            if year > 2500:
                year -= 543
            return f"{year}-{num:02d}-{day:02d}"

    # Pattern: DD MonthThai YYYY (Thai full month)
    for thai_m, num in THAI_MONTHS_FULL.items():
        pat = rf'(\d{{1,2}})\s+{re.escape(thai_m)}\s+(\d{{4}})'
        m = re.search(pat, text)
        if m:
            day = int(m.group(1))
            year = int(m.group(2))
            if year > 2500:
                year -= 543
            return f"{year}-{num:02d}-{day:02d}"

    # Pattern: DD Month YYYY (English)
    for en_m, num in EN_MONTHS.items():
        pat = rf'(\d{{1,2}})\s+{re.escape(en_m)}\s+(\d{{4}})'
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            year = int(m.group(2))
            return f"{year}-{num:02d}-{day:02d}"

    # Pattern: Month DD, YYYY (English)
    for en_m, num in EN_MONTHS.items():
        pat = rf'{re.escape(en_m)}\s+(\d{{1,2}}),?\s+(\d{{4}})'
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            year = int(m.group(2))
            return f"{year}-{num:02d}-{day:02d}"

    # Pattern: 📅 DD Month YYYY (with emoji)
    m = re.search(r'📅\s*(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        if month_name in EN_MONTHS:
            return f"{year}-{EN_MONTHS[month_name]:02d}-{day:02d}"

    return "TBA"


def extract_province_from_text(text):
    """Try to find a Thai province in the text."""
    if not text:
        return ""

    for thai_name, en_name in THAI_PROVINCES.items():
        if thai_name in text:
            return en_name

    return ""


def extract_distances_from_text(text):
    """Extract race distances from text like '42K', '21.1KM', '10K', '5K'."""
    if not text:
        return []

    distances = set()
    # Match patterns like 42K, 21.1KM, 10 KM, 5K, 100K
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:K|km|KM|กม)', text, re.IGNORECASE):
        d = float(m.group(1))
        if d <= 0.5:
            continue
        if d == int(d):
            distances.add(f"{int(d)}K")
        else:
            distances.add(f"{d}K")

    # Sort by distance descending
    return sorted(distances, key=lambda x: float(x.replace('K', '')), reverse=True)


def extract_year_from_text(text):
    """Extract year (2025/2026) from text. Handles Buddhist years."""
    # Look for 2025, 2026, 2568, 2569 etc
    m = re.search(r'(2[05]\d{2})', text)
    if m:
        year = int(m.group(1))
        if year > 2500:
            year -= 543
        return year
    return None


def detect_type(name):
    """Detect race type from name."""
    lower = name.lower()
    if any(w in lower for w in ["trail", "เทรล", "ultra trail"]):
        return "trail"
    if any(w in lower for w in ["triathlon", "ไตรกีฬา", "tri ", "duathlon"]):
        return "triathlon"
    if any(w in lower for w in ["cycling", "bike", "จักรยาน", "fondo", "gravel"]):
        return "cycling"
    if any(w in lower for w in ["swim", "ว่ายน้ำ", "aqua"]):
        return "swim"
    if any(w in lower for w in ["obstacle", "ocr", "spartan", "warrior"]):
        return "obstacle"
    return "run"
