# Changelog

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
