# Heroes Tracker — frontend

React + Vite. No auth, no Supabase — just a fetch layer (`src/api.js`) against
the `backend/` API. Dev-only for now (see the repo's root README "Open
decisions").

```bash
npm install
cp .env.example .env.local   # VITE_API_URL — point at the backend
npm run dev
```

## Views (`src/views/`)

- **MatchHistory** — personal/roster match history, filterable by player and game type.
- **HeroStats** — win/pick/ban rate per hero at the configured rank bracket.
- **TalentBuilds** — top talent builds per hero with win rate.
- **Matchups** — hero-vs-hero win rate lookup.
- **Groups** — roster admin (add/rename/deactivate/remove battletags) plus win rate by friend-group combo.
