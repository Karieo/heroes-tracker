# Heroes Tracker

A Heroes of the Storm stats/builds tracker for Clay's personal battletag
(`karieo#1503`) and a small friend roster, feeding two Xeneon Edge widgets
(`HeroesDraft` and `HeroesLive` — see
[`XENEON-Edge-Widgets-`](https://github.com/Karieo/XENEON-Edge-Widgets-)).
Same shape as DATACORE → Supabase → STRATUM DM, but Flask/SQLite instead of
Supabase, matching the Remndrs precedent for services on `bastion`.

```
┌────────────────────┐      polls on a schedule       ┌──────────────────┐
│  HeroesProfile API  │ ─────────────────────────────▶ │  backend/ (Flask │
└────────────────────┘                                 │  + SQLite, on    │
                                                         │  bastion)        │
                                                         └──────────────────┘
                                                            │        │
                                          read-only fetch   │        │  read-only fetch
                                          ┌──────────────────┘        └──────────────────┐
                                          ▼                                               ▼
                                 frontend/ (React+Vite)                 XENEON-Edge-Widgets-/widgets/
                                 match history, hero stats,             HeroesDraft, HeroesLive
                                 talent builds, matchups, groups
```

The HeroesProfile API token lives only in `backend/.env` — never in the
frontend, never in a widget, never committed.

## Layout

```
backend/    Flask + SQLite + APScheduler — see backend/README.md
frontend/   React + Vite tracker app — see frontend/README.md
BASTION_SETUP.md   deploying backend/ to bastion (Jetson TX2)
```

## Quick start (local dev)

```bash
# backend
cd backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env   # set HEROESPROFILE_API_TOKEN
venv/bin/python app.py   # http://localhost:3001

# frontend, in another terminal
cd frontend
npm install
cp .env.example .env.local   # VITE_API_URL=http://localhost:3001
npm run dev   # http://localhost:5173
```

## Friend roster

Seeded on first run (`backend/database.py`'s `INITIAL_ROSTER`):
GamerinShade#1325, LoveSlug#11595, thatphilkid#1122, YodaFan#11454,
Griff17#1916, JuRJuR#1703, plus Karieo#1503 as the primary player. Add,
rename, or deactivate players any time from the tracker's **Friends & Groups**
tab, or directly against `/api/players` (see `backend/README.md`).

## Open decisions

These were called out in the build prompt as needing Clay's input — see
`BASTION_SETUP.md`'s final section for the full list:

- **Bastion port** — defaulted to 3001 (Remndrs owns 3000); confirm nothing
  else on bastion already claims it.
- **Frontend hosting** — dev-only on the Mac for now; trivial to containerize
  onto bastion later if you want it always-on.
- **HeroesProfile rate limits** — this sandbox couldn't reach
  api.heroesprofile.com or heroesprofile.com to read the live docs (network
  policy blocks those hosts), so `backend/heroesprofile_client.py`'s endpoint
  paths and the poll intervals in `.env.example` are best-effort and need a
  one-time check against your subscribed tier's actual API reference before
  the first real deploy.
