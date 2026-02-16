"""
Scraper: Runlah.com — Chiang Mai running races
"""

import re
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

URL = "https://www.runlah.com/en/calendar/location?province=Chiang+Mai"
BASE = "https://www.runlah.com"

SKIP_HREFS = {
    "/en", "/en/calendar", "/en/results", "/en/promote", "/en/about",
    "/en/terms", "/en/privacy", "/en/user/registers", "/en/user/settings",
}


class RunlahParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.races = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = d.get("href", "")
        src = d.get("src", "")

        if tag == "a" and href and re.match(r"^/en/[A-Za-z0-9_]+$", href):
            if "/teams/" not in href and href not in SKIP_HREFS:
                if self.current is None:
                    self.current = {
                        "name": "", "url": BASE + href,
                        "image": "", "date": "", "dateDisplay": "", "location": "",
                        "source": "runlah",
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

        # Location — match English "Chiang Mai" or Thai "เชียงใหม่"
        if not r["location"]:
            is_cm = ("Chiang Mai" in text and "province" in text.lower()) or \
                    ("เชียงใหม่" in text)
            if is_cm:
                r["location"] = text.replace(" province", "").replace("จังหวัด", "").strip()

    def handle_endtag(self, tag):
        if self.current and self.current["name"] and self.current["date"]:
            urls = {r["url"] for r in self.races}
            if self.current["url"] not in urls:
                if not self.current["location"]:
                    self.current["location"] = "Chiang Mai"
                self.races.append(self.current)
            self.current = None


def scrape():
    """Fetch Runlah Chiang Mai page and return list of race dicts."""
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CMRaces/1.0)"
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    parser = RunlahParser()
    parser.feed(html)

    # Sort + deduplicate
    seen = set()
    unique = []
    for r in sorted(parser.races, key=lambda x: x["date"]):
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    return unique


if __name__ == "__main__":
    races = scrape()
    print(f"Found {len(races)} Chiang Mai races on Runlah:")
    for r in races:
        print(f"  {r['date']} — {r['name']}")
