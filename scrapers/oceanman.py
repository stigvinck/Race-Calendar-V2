"""
Scraper: OceanmanSwim.com — Open water swimming events
Scrapes Thailand-based Oceanman events.
"""

import re
import urllib.request

BASE = "https://oceanmanswim.com"
URLS = [
    BASE + "/krabi-thailand/",
    BASE + "/events/",
]

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def parse_date(text):
    if not text:
        return None
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)
    m = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = m.group(3)
        month = MONTHS.get(month_str[:3])
        if month:
            return "%s-%s-%02d" % (year, month, day)
    return None


def scrape():
    """Scrape oceanmanswim.com for Thailand events."""
    print("    [Oceanman] Fetching pages...")
    races = []
    seen = set()

    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            if len(html) < 500:
                continue

            # Look for Thailand-specific event info
            is_thailand_page = "thailand" in html.lower() or "krabi" in html.lower()

            # Extract dates
            date_matches = re.findall(
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})',
                html, re.IGNORECASE
            )

            # Extract titles
            title_matches = re.findall(
                r'<h[1-3][^>]*>(.*?)</h[1-3]>',
                html, re.DOTALL | re.IGNORECASE
            )
            titles = [re.sub(r'<[^>]+>', '', t).strip() for t in title_matches]
            titles = [t for t in titles if len(t) > 5 and t.lower() != "menu"]

            # For the Krabi-specific page
            if "krabi" in url.lower() and titles:
                name = "Oceanman Krabi"
                for t in titles:
                    if "ocean" in t.lower():
                        name = t
                        break

                date_str = None
                for dm in date_matches:
                    d = parse_date(dm)
                    if d and d >= "2026":
                        date_str = d
                        break

                rid = "ocean-krabi-2026"
                if rid not in seen:
                    seen.add(rid)
                    # Look for distance info
                    dist_matches = re.findall(r'(\d+(?:\.\d+)?\s*[kK][mM]?)', html)
                    distances = list(set(dist_matches[:5])) if dist_matches else ["10K", "5K", "2K"]

                    races.append({
                        "id": rid,
                        "name": name,
                        "date": date_str or "TBA",
                        "type": "swim",
                        "province": "Krabi",
                        "location": "Klong Muang Beach, Krabi",
                        "url": url,
                        "image": "",
                        "source": "Oceanman",
                        "distances": distances,
                        "tags": ["open water", "swim"],
                    })

            # For events listing page, look for Thailand links
            elif is_thailand_page:
                thai_links = re.findall(
                    r'<a[^>]*href=["\'](https?://oceanmanswim\.com/[^"\']*(?:thai|krabi)[^"\']*)["\']\s*[^>]*>(.*?)</a>',
                    html, re.DOTALL | re.IGNORECASE
                )
                for link_url, inner in thai_links:
                    name = re.sub(r'<[^>]+>', ' ', inner).strip()
                    if len(name) < 4:
                        continue
                    rid = "ocean-" + re.sub(r'[^a-z0-9]', '', link_url.lower()[-30:])
                    if rid not in seen:
                        seen.add(rid)
                        races.append({
                            "id": rid,
                            "name": name or "Oceanman Thailand",
                            "date": "TBA",
                            "type": "swim",
                            "province": "Krabi",
                            "location": "",
                            "url": link_url,
                            "image": "",
                            "source": "Oceanman",
                            "distances": [],
                            "tags": ["open water", "swim"],
                        })

        except Exception as e:
            print("    [Oceanman] Error on %s: %s" % (url, e))

    print("    [Oceanman] Found %d events" % len(races))
    return races
