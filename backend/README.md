# Heroes Tracker — backend

Flask + SQLite + APScheduler, one process. Polls HeroesProfile on a schedule,
caches everything locally, and exposes a small read/write API for the
tracker frontend and the two Xeneon Edge widgets. The HeroesProfile API token
lives only here — the frontend and widgets never see it.

See `../BASTION_SETUP.md` for deploying this to bastion. For local dev:

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # set HEROESPROFILE_API_TOKEN
venv/bin/python app.py
```

**Before relying on live data**, read `heroesprofile_client.py`'s module
docstring — its endpoint paths/params were written without live access to
HeroesProfile's docs (this sandbox's network policy blocks
api.heroesprofile.com) and need a one-time check against your subscribed
tier's actual API reference.

## API

All routes return JSON.

| Route | Notes |
|---|---|
| `GET /api/version` | health check |
| `GET /api/players` | roster; `?all=1` includes inactive |
| `POST /api/players` | `{battletag, display_name?}` |
| `PUT /api/players/<id>` | `{display_name?, active?}` |
| `DELETE /api/players/<id>` | |
| `GET /api/matches` | `?battletag=&game_type=&limit=&offset=`; defaults to the roster's primary player |
| `GET /api/matches/<match_id>` | full per-player breakdown |
| `GET /api/heroes` | cached hero roster |
| `GET /api/heroes/<hero>/stats` | `?game_type=&rank_tier=` |
| `GET /api/heroes/<hero>/talents` | `?game_type=&rank_tier=&limit=` — top builds by win rate |
| `GET /api/heroes/<hero>/matchups` | `?game_type=&rank_tier=` — vs every other hero |
| `GET /api/groups` | friend-group win rates; `?min_games=` |

### Widget feeds (`/api/edge/*`)

CORS-open (`Access-Control-Allow-Origin: *`) since the widgets load as local
files inside iCUE — same call PIT WALL's dashboard feed makes. Read-only,
cached data only; no HeroesProfile token anywhere near these. Documented in
detail (with the exact JSON shape) in
`XENEON-Edge-Widgets-/docs/heroes-edge-feed.md`.

| Route | Used by |
|---|---|
| `GET /api/edge/heroes` | both widgets, to build the hero picker |
| `GET /api/edge/matchup?hero=&enemy=&game_type=&rank_tier=` | HEROES DRAFT |
| `GET /api/edge/hero-reference?hero=&game_type=&rank_tier=` | HEROES LIVE |

## Data model

See `database.py`'s `SCHEMA` — every table has a comment explaining what it
holds and why. Short version: `players` is the editable roster,
`matches`/`match_players` are raw synced match history, `match_groups` is a
precomputed tag per match for every 2+ tracked players who shared a team
(this is what powers `/api/groups`), and `hero_stats_cache` /
`talent_build_cache` / `matchup_cache` mirror HeroesProfile's own rank-filtered
aggregates — nothing here is computed from Clay's personal matches except the
group win rates and the "personal" block in `/api/edge/hero-reference`.
