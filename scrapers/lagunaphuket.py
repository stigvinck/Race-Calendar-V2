"""
Laguna Phuket Triathlon scraper
Scrapes lagunaphukettri.com for event details.
Single-event site but covers triathlon, sprint, duathlon, fun run, open water swim.
SSR WordPress site — easy to parse.
"""

import re
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ThaiRaceFinder/1.0)",
    "Accept": "text/html",
    "Accept-Language": "en-US,en;q=0.9",
}

PAGES = [
    ("https://www.lagunaphukettri.com/", "main"),
    ("https://www.lagunaphukettri.com/lpt-individual/", "individual"),
    ("https://www.lagunaphukettri.com/sprint-triathlon/", "sprint"),
    ("https://www.lagunaphukettri.com/duathlon/", "duathlon"),
]

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def scrape():
    races = []
    main_date = ""
    main_image = ""
    year = ""

    # Fetch main page first to get the date
    try:
        req = urllib.request.Request(PAGES[0][0], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract date — patterns like "Sunday, 15 November 2026" or "November 15, 2026"
        date_patterns = [
            r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
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
                    main_date = f"{year}-{month}-{day}"
                    break
                except (ValueError, KeyError):
                    pass

        # OG image
        og_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_m:
            main_image = og_m.group(1)

        # Extract edition number
        edition = ""
        ed_m = re.search(r'(\d+)(?:st|nd|rd|th)\s+LAGUNA\s+PHUKET\s+TRIATHLON', html, re.IGNORECASE)
        if ed_m:
            edition = ed_m.group(1)

    except Exception as e:
        print(f"    [LagunaPhkTri] Main page error: {e}")

    if not main_date:
        # Known date: Sunday 15 November 2026 (30th edition)
        main_date = "2026-11-15"
        year = "2026"
        edition = "30"

    edition_str = f" ({edition}th edition)" if edition else ""

    # Main triathlon event
    races.append({
        "id": f"laguna-phuket-tri-{year or '2026'}",
        "name": f"Laguna Phuket Triathlon{edition_str}",
        "date": main_date,
        "location": "Laguna Phuket, Cherngtalay",
        "province": "Phuket",
        "type": "triathlon",
        "distances": ["1.8K swim", "50K bike", "12K run"],
        "url": "https://www.lagunaphukettri.com/",
        "image": main_image,
        "source": "LagunaPhkTri",
        "tags": ["triathlon", "laguna", "phuket"],
    })

    # Sprint triathlon
    races.append({
        "id": f"laguna-phuket-sprint-{year or '2026'}",
        "name": f"Laguna Phuket Sprint Triathlon{edition_str}",
        "date": main_date,
        "location": "Laguna Phuket, Cherngtalay",
        "province": "Phuket",
        "type": "triathlon",
        "distances": ["0.5K swim", "20K bike", "6K run"],
        "url": "https://www.lagunaphukettri.com/sprint-triathlon/",
        "image": main_image,
        "source": "LagunaPhkTri",
        "tags": ["triathlon", "sprint", "laguna", "phuket"],
    })

    # Duathlon
    races.append({
        "id": f"laguna-phuket-duathlon-{year or '2026'}",
        "name": f"Laguna Phuket Duathlon{edition_str}",
        "date": main_date,
        "location": "Laguna Phuket, Cherngtalay",
        "province": "Phuket",
        "type": "triathlon",
        "distances": ["3K run", "20K bike", "3K run"],
        "url": "https://www.lagunaphukettri.com/duathlon/",
        "image": main_image,
        "source": "LagunaPhkTri",
        "tags": ["duathlon", "laguna", "phuket"],
    })

    # Try to find Saturday Fun Run
    try:
        req = urllib.request.Request("https://www.lagunaphukettri.com/30-anniversary-charity-fun-run/", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            fr_html = resp.read().decode("utf-8", errors="replace")
        if "fun run" in fr_html.lower() or "6km" in fr_html.lower():
            # Fun run is day before main event
            races.append({
                "id": f"laguna-phuket-funrun-{year or '2026'}",
                "name": f"Laguna Phuket Saturday Fun Run{edition_str}",
                "date": main_date,  # Same weekend
                "location": "Laguna Phuket, Cherngtalay",
                "province": "Phuket",
                "type": "run",
                "distances": ["6K"],
                "url": "https://www.lagunaphukettri.com/",
                "image": main_image,
                "source": "LagunaPhkTri",
                "tags": ["fun run", "laguna", "phuket"],
            })
    except Exception:
        pass

    # Laguna Open Water Swim
    try:
        req = urllib.request.Request("https://www.lagunaphukettri.com/laguna-open-water-swim-by-trihub/", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            sw_html = resp.read().decode("utf-8", errors="replace")
        if "open water" in sw_html.lower() or "swim" in sw_html.lower():
            races.append({
                "id": f"laguna-phuket-ows-{year or '2026'}",
                "name": f"Laguna Phuket Open Water Swim{edition_str}",
                "date": main_date,
                "location": "Laguna Phuket, Cherngtalay",
                "province": "Phuket",
                "type": "swim",
                "distances": [],
                "url": "https://www.lagunaphukettri.com/",
                "image": main_image,
                "source": "LagunaPhkTri",
                "tags": ["open water", "swim", "laguna", "phuket"],
            })
    except Exception:
        pass

    print(f"    [LagunaPhkTri] Found {len(races)} events")
    return races
