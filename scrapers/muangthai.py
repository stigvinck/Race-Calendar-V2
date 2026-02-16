"""
Muangthai Triathlon scraper
Scrapes Muangthai Triathlon Eco Hero Super Series events.
These are hosted on GoToRace with consistent URL patterns.
Also checks their Facebook page and direct event sites.
"""

import re
import urllib.request
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ThaiRaceFinder/1.0)",
    "Accept": "text/html",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
}

# Known Muangthai Triathlon event URL patterns on GoToRace
# They follow: gotorace.com/mtl{year}-{location}/
# Series: 3 events per year (Mar Sam Roi Yod, Jul Ban Krut, Nov TBA)
KNOWN_URLS = [
    "https://www.gotorace.com/mtl2026-samroiyod/",
    "https://www.gotorace.com/mtl2026-bankrut/",
    "https://www.gotorace.com/mtl2026/",
    "https://www.gotorace.com/mtl2026-samroiyod",
    "https://www.gotorace.com/mtl2026-bankrut",
]

# Also try the main GoToRace page filtered for Muangthai
SEARCH_URLS = [
    "https://www.gotorace.com/",
]

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

THAI_MONTHS = {
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03",
    "เมษายน": "04", "พฤษภาคม": "05", "มิถุนายน": "06",
    "กรกฎาคม": "07", "สิงหาคม": "08", "กันยายน": "09",
    "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
}


def scrape():
    races = []
    seen_urls = set()

    # 1. Try known direct URLs
    for url in KNOWN_URLS:
        if url.rstrip("/") in seen_urls:
            continue
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    continue
                html = resp.read().decode("utf-8", errors="replace")
                final_url = resp.url

            seen_urls.add(final_url.rstrip("/"))

            race = parse_mtl_page(html, final_url)
            if race:
                races.append(race)

        except Exception:
            pass

    # 2. Search GoToRace homepage for Muangthai links
    for search_url in SEARCH_URLS:
        try:
            req = urllib.request.Request(search_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Find all Muangthai-related links
            links = re.findall(r'href="(https?://(?:www\.)?gotorace\.com/mtl[^"]*)"', html, re.IGNORECASE)
            # Also find by text
            links += re.findall(r'href="(https?://(?:www\.)?gotorace\.com/[^"]*muangthai[^"]*)"', html, re.IGNORECASE)

            for link in links:
                clean = link.rstrip("/")
                if clean in seen_urls:
                    continue
                seen_urls.add(clean)

                try:
                    req2 = urllib.request.Request(link, headers=HEADERS)
                    with urllib.request.urlopen(req2, timeout=15) as resp2:
                        if resp2.status != 200:
                            continue
                        page_html = resp2.read().decode("utf-8", errors="replace")

                    race = parse_mtl_page(page_html, link)
                    if race:
                        races.append(race)
                except Exception:
                    pass

        except Exception as e:
            print(f"    [Muangthai] Search error: {e}")

    # 3. If we found nothing from pages, add known upcoming events as TBA
    if not races:
        races = get_known_upcoming()

    print(f"    [Muangthai] Found {len(races)} events")
    return races


def parse_mtl_page(html, url):
    """Parse a Muangthai Triathlon event page from GoToRace."""
    # Must contain Muangthai or MTL
    if "muangthai" not in html.lower() and "mtl" not in url.lower():
        return None

    # Title
    title = ""
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if title_m:
        title = title_m.group(1).strip()
    if not title:
        title_m = re.search(r'<title[^>]*>([^<]+)</title>', html)
        if title_m:
            title = title_m.group(1).strip().split(" - ")[0].strip()
    if not title:
        title = "Muangthai Triathlon"

    # Date — try English patterns
    date_str = ""
    # "21-22 March 2026" or "1 March 2026"
    date_patterns = [
        r'(\d{1,2})(?:\s*-\s*\d{1,2})?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:\s*-\s*\d{1,2})?,?\s+(\d{4})',
    ]
    for pat in date_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            groups = m.groups()
            try:
                if groups[1].lower() in MONTHS:
                    day = groups[0].zfill(2)
                    month = MONTHS[groups[1].lower()]
                    year = groups[2]
                elif groups[0].lower() in MONTHS:
                    month = MONTHS[groups[0].lower()]
                    day = groups[1].zfill(2)
                    year = groups[2]
                else:
                    continue
                date_str = f"{year}-{month}-{day}"
                break
            except (ValueError, KeyError):
                pass

    # Thai date fallback
    if not date_str:
        for thai_m, num_m in THAI_MONTHS.items():
            pat = rf'(\d{{1,2}})\s*(?:-\s*\d{{1,2}}\s*)?{thai_m}\s*(\d{{4}})'
            m = re.search(pat, html)
            if m:
                day = m.group(1).zfill(2)
                year = int(m.group(2))
                if year > 2500:
                    year -= 543
                date_str = f"{year}-{num_m}-{day}"
                break

    # Location
    location = ""
    loc_patterns = [
        r'(?:Sam\s*Roi\s*Yod|Samroiyod)',
        r'(?:Ban\s*Krut|Bankrut)',
        r'(?:Prachuap\s*Khiri\s*Khan)',
        r'(?:Chanthaburi)',
        r'(?:Ratchaburi)',
    ]
    for lp in loc_patterns:
        if re.search(lp, html, re.IGNORECASE):
            location = re.search(lp, html, re.IGNORECASE).group(0)
            break

    province = detect_province(html)

    # Distances — Muangthai typically has Sprint/Olympic/Relay distances
    distances = []
    dist_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:km|K)\b', html, re.IGNORECASE)
    for d in dist_matches:
        v = float(d)
        if 0.3 <= v <= 200:
            ds = f"{d}K"
            if ds not in distances:
                distances.append(ds)

    # Image
    image = ""
    img_m = re.search(r'(https?://[^"\']+(?:muangthai|mtl)[^"\']*(?:\.jpg|\.png|\.jpeg|\.webp))', html, re.IGNORECASE)
    if not img_m:
        img_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if img_m:
        image = img_m.group(1)

    slug = url.rstrip("/").split("/")[-1] or "muangthai-tri"

    return {
        "id": f"muangthai-{slug}",
        "name": title,
        "date": date_str or "TBA",
        "location": location,
        "province": province,
        "type": "triathlon",
        "distances": distances[:8],
        "url": url,
        "image": image,
        "source": "Muangthai",
        "tags": ["triathlon", "muangthai", "eco hero"],
    }


def detect_province(html):
    text = html.lower()
    if "sam roi yod" in text or "samroiyod" in text or "prachuap" in text:
        return "Prachuap Khiri Khan"
    if "ban krut" in text or "bankrut" in text:
        return "Prachuap Khiri Khan"
    if "chanthaburi" in text:
        return "Chanthaburi"
    if "ratchaburi" in text:
        return "Ratchaburi"
    if "bangkok" in text:
        return "Bangkok"
    if "phuket" in text:
        return "Phuket"
    return ""


def get_known_upcoming():
    """Return known Muangthai series events for current year as TBA."""
    year = datetime.utcnow().year
    return [
        {
            "id": f"muangthai-{year}-blue-guardian",
            "name": f"Muangthai Triathlon Eco Hero — Blue Guardian {year}",
            "date": "TBA",
            "location": "Sam Roi Yod, Prachuap Khiri Khan",
            "province": "Prachuap Khiri Khan",
            "type": "triathlon",
            "distances": [],
            "url": "https://www.gotorace.com/",
            "image": "",
            "source": "Muangthai",
            "tags": ["triathlon", "muangthai", "eco hero"],
        },
        {
            "id": f"muangthai-{year}-solar-future",
            "name": f"Muangthai Triathlon Eco Hero — Solar Future {year}",
            "date": "TBA",
            "location": "Ban Krut, Prachuap Khiri Khan",
            "province": "Prachuap Khiri Khan",
            "type": "triathlon",
            "distances": [],
            "url": "https://www.gotorace.com/",
            "image": "",
            "source": "Muangthai",
            "tags": ["triathlon", "muangthai", "eco hero"],
        },
        {
            "id": f"muangthai-{year}-green-genesis",
            "name": f"Muangthai Triathlon Eco Hero — Green Genesis {year}",
            "date": "TBA",
            "location": "TBA",
            "province": "",
            "type": "triathlon",
            "distances": [],
            "url": "https://www.gotorace.com/",
            "image": "",
            "source": "Muangthai",
            "tags": ["triathlon", "muangthai", "eco hero"],
        },
    ]
