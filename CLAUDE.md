# Twin Hub — CLAUDE.md

## What This Is
Family activity hub for dad + twin daughters. Hamilton challenges, message board, voice visualizer.
Port 5567.

## Architecture
- `app.py` — Flask server, raw sqlite3, Anthropic daily fact
- `challenges.json` — 20 Hamilton challenges (editable)
- `templates/index.html` — main hub (two-column message board + challenge spinner)
- `templates/visualizer.html` — Web Audio API mic visualizer
- `templates/admin.html` — dad-only controls

## Config (Railway env vars)
- `TWIN1_NAME` — left column name (default: Aria)
- `TWIN2_NAME` — right column name (default: Zara)
- `DAD_PASSWORD` — clears all notes (default: dad)
- `ANTHROPIC_API_KEY` — daily Hamilton fact via claude-haiku, cached 24h

## Daily Fact Logic
`get_daily_fact()` checks `data/daily_fact.json`. If older than 24h, calls Anthropic Haiku, re-caches.
Railway ephemeral disk means cache resets on redeploy — that's fine, one Haiku call per deploy.

## Database
SQLite at `data/hub.db`. Single `notes` table (id, author, content, timestamp).
Ephemeral on Railway — notes wipe on redeploy. Fine for a family toy.

## Status
🟢 Live on GitHub — papjamzzz/twin-hub

## Next Steps
- [ ] Persist DB via Railway Volume (if notes need to survive deploys)
- [ ] Add challenge history log (track which challenges have been completed)
- [ ] Add emoji reactions to notes
- [ ] Custom challenge editor in /admin
