"""
Checkrace scraper — uses the official API.
POST https://run.checkrace.com/api/app/eventController/listEventByEventType
Returns all events with full details: names (EN/TH), dates, provinces,
distances, images, and registration status.
"""

import requests
from datetime import datetime, timezone

API_URL = "https://run.checkrace.com/api/app/eventController/listEventByEventType"
BASE_URL = "https://run.checkrace.com"


def detect_type(name):
    """Detect race type from event name."""
    n = name.upper()
    if any(w in n for w in ["TRAIL", "เทรล"]):
        return "trail"
    if any(w in n for w in ["TRIATHLON", "TRI ", "ไตรกีฬา"]):
        return "triathlon"
    if any(w in n for w in ["CYCLING", "BIKE", "FONDO", "จักรยาน"]):
        return "cycling"
    if any(w in n for w in ["SWIM", "ว่ายน้ำ"]):
        return "swimming"
    if any(w in n for w in ["OBSTACLE", "SPARTAN", "XRACE"]):
        return "obstacle"
    if any(w in n for w in ["WALK", "เดิน"]):
        return "walking"
    return "run"


def parse_distances(tickets):
    """Extract distance list from ticket data."""
    distances = []
    if not tickets:
        return distances
    for t in tickets:
        name = (t.get("ticketNameEn") or t.get("ticketNameTh") or "").strip()
        if name:
            distances.append(name)
    return distances


def scrape():
    races = []
    now = datetime.now(timezone.utc)

    try:
        resp = requests.post(
            API_URL,
            json={"eventType": "", "registerStep": {"listStep": []}},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    [Checkrace] API error: {e}")
        return races

    events = data.get("data", [])
    print(f"    [Checkrace] API returned {len(events)} total events")

    for ev in events:
        # Skip past events
        status = (ev.get("eventStatus") or "").upper()
        if status == "PAST":
            continue

        # Also skip if event date is in the past
        date_str = ev.get("eventDate", "")
        date_display = "TBA"
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("+00:00", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < now:
                    continue
                date_display = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        name_en = (ev.get("eventNameEn") or "").strip()
        name_th = (ev.get("eventNameTh") or "").strip()
        name = name_en or name_th or "Unknown Event"

        event_url_slug = ev.get("eventUrl", "")
        url = f"{BASE_URL}/event/{event_url_slug}" if event_url_slug else BASE_URL

        province_en = (ev.get("eventProvinceEn") or "").strip()
        province_th = (ev.get("eventProvinceTh") or "").strip()
        location_en = (ev.get("eventLocationEn") or "").strip()

        # Image
        image = (ev.get("imageEventBannerUrl") or "").strip()

        # Distances from tickets
        distances = parse_distances(ev.get("listTicket", []))
        # Also check listTicketDistance as fallback
        if not distances:
            dist_list = ev.get("listTicketDistance", [])
            distances = [f"{d} KM" for d in dist_list if d and not d.startswith("+")]

        race_type = detect_type(name)

        race = {
            "id": f"checkrace-{ev.get('eventCode', ev.get('id', ''))}",
            "name": name,
            "nameTh": name_th,
            "date": date_display,
            "location": location_en or province_en or province_th or "",
            "province": province_en or province_th or "",
            "type": race_type,
            "distances": distances,
            "url": url,
            "image": image,
            "source": "Checkrace",
            "tags": [],
        }
        races.append(race)

    print(f"    [Checkrace] {len(races)} upcoming events")
    return races
