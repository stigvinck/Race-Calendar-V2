# CM Races — Chiang Mai Running Events

Auto-scraped running race calendar for Chiang Mai province, Thailand.

## How it works

- A lightweight Python server serves the static site
- Background scrapers run every 6 hours, fetching race data from multiple sources
- Results are merged into `public/races.json` which the frontend reads

## Project structure

```
├── server.py              ← Web server + scheduler
├── Dockerfile             ← For Render deployment
├── render.yaml            ← Render blueprint (one-click deploy)
├── scrapers/
│   ├── __init__.py
│   ├── runlah.py          ← Runlah.com scraper
│   └── (add more here)
└── public/
    ├── index.html          ← The frontend
    └── races.json          ← Auto-generated race data
```

## Deploy to Render

1. Push this repo to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects the Dockerfile — just click Create
5. Done! Your site is live at `https://cm-races.onrender.com`

## Adding a new scraper

1. Create a file in `scrapers/`, e.g. `scrapers/facebook.py`
2. It must export a `scrape()` function that returns a list of dicts:

```python
def scrape():
    return [
        {
            "name": "Race Name",
            "url": "https://...",
            "image": "https://...",
            "date": "2026-03-15",         # YYYY-MM-DD
            "dateDisplay": "March 15, 2026",
            "location": "Some Place, Chiang Mai",
            "source": "facebook",
        },
    ]
```

3. Register it in `server.py`:

```python
from scrapers.facebook import scrape as scrape_facebook

scrapers = [
    ("Runlah", scrape_runlah),
    ("Facebook", scrape_facebook),  # ← add this line
]
```

4. Push to GitHub — Render auto-deploys.

## Local development

```bash
python server.py
# Open http://localhost:10000
```
