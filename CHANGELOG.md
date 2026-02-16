# Changelog

## v0.8.0 — 2026-02-16
- **Headless browser (Playwright)** — unlocks JS-rendered sites that were previously blocked
- Added **Checkrace** scraper (run.checkrace.com) — Thailand's #1 race registration platform, hundreds of Thai races
- Added **race.thai.run** scraper — Thai.Run active event listings via headless browser
- Added **Laguna Phuket Triathlon** scraper — triathlon, sprint, duathlon, fun run, open water swim
- Dockerfile updated with Chromium + system deps for headless browsing
- 16 active scrapers, 4 blocked sources
- Headless browser auto-starts on first use, auto-cleans on shutdown

## v0.7.0 — 2026-02-16
- Added Muangthai Triathlon scraper — Eco Hero Super Series (Blue Guardian, Solar Future, Green Genesis)
- Runlah now shows live province-by-province progress in status bar: "Runlah (23/77)"
- Progress updates every 5 provinces instead of every 15 — no more "stuck" feeling
- 13 active scrapers, 7 blocked sources

## v0.6.0 — 2026-02-16
- Added GranFondoGuide scraper (granfondoguide.com) — Dustman gravel, GFNY Krabi, Tour of Phuket, Chiang Mai Gran Fondo
- 12 active scrapers, 7 blocked sources tracked
- Removed AI enrichment module (simplifying stack)
- Added Checkrace and race.thai.run to blocked sources list (JS-rendered SPAs)

## v0.5.0 — 2026-02-16
- Added Spartan Thailand scraper (th.spartan.com) — OCR obstacle races
- Added RunningConnect scraper (runningconnect.com) — UTMB Thailand series, trail & ultra events
- 11 active scrapers, 4 blocked sources tracked (WorldsMarathons, Ahotu, IRONMAN, MarathonGuide)
- AI status badge now always visible: green "AI on" or red "AI off"
- Version number included in zip filename for easier tracking
- Improved scrape status bar with real-time source-by-source progress

## v0.4.0 — 2026-02-16
- Added version numbering + changelog (visible on frontend and GitHub)
- Live scrape status indicator — shows progress while scrapers run
- AI enrichment module (Claude Sonnet) — translates Thai names, deduplicates, improves type/province classification
- 9 active scrapers: Runlah, GoToRace, JogAndJoy, Thai.Run, Finishers, Pho3nix, CycloWorld, XRace, Oceanman
- Source tag moved from card image overlay to "View details on [source]" link
- Toggled-off filter buttons now visually faded (grey, 45% opacity)
- AI badge only shows when AI enrichment is actually enabled
- `/api/status` endpoint for monitoring

## v0.3.0 — 2026-02-16
- Expanded to 9 scrapers (added Pho3nix, CycloWorld, XRace, Oceanman)
- Past races automatically filtered out — only upcoming + TBA shown
- TBD/TBA date toggle filter
- Sources popup showing all tracked sites with active/blocked/planned status
- Self-ping keep-alive thread for Render free tier

## v0.2.0 — 2026-02-15
- Rebuilt Runlah scraper to cover all 77 Thai provinces (EN + TH)
- Rebuilt GoToRace scraper with correct WordPress pagination endpoint
- Removed WorldsMarathons and Ahotu scrapers (JS-rendered SPAs, need headless browser)
- Bilingual scraping for better coverage
- Province-based location detection

## v0.1.0 — 2026-02-14
- Initial release — Thailand Race Finder
- Card-based UI with type, location, and time filters
- Runlah + GoToRace scrapers
- Auto-scrape every 6 hours on Render
