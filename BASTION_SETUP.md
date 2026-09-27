# Bastion Setup (Jetson TX2)

Runs the Heroes Tracker backend alongside Remndrs and the rest of the
homelab stack on `bastion`, using the same Docker + Cloudflare Tunnel +
Tailscale pattern.

**Open decision — confirm before deploying:** this uses port **3001** on the
assumption that Remndrs owns 3000 and nothing else on bastion has claimed
3001 yet. Check bastion's actual port registry (the comment block at the top
of `~/.cloudflared/config.yml`, per Remndrs' `PI_SETUP.md`) before you copy
these commands — bump `PORT` in `.env` and `docker-compose.yml` if 3001 is
taken.

## 1. Get the code onto bastion

```bash
ssh bastion   # or your Tailscale hostname for the Jetson
git clone https://github.com/Karieo/Heroes-Tracker.git ~/Heroes-Tracker
cd ~/Heroes-Tracker/backend
```

## 2. Configure

```bash
cp .env.example .env
nano .env   # set HEROESPROFILE_API_TOKEN and HEROESPROFILE_RANK_TIER
```

Get the token from [heroesprofile.com/Api](https://www.heroesprofile.com/Api/)
after registering, verifying, and subscribing (Basic or Intermediate covers
what this backend needs — see the caveat in `heroesprofile_client.py`'s
module docstring about confirming exact endpoint paths against your tier's
docs, since this was built without live access to fetch them).

## 3. Run it

```bash
docker compose up -d --build
curl -s localhost:3001/api/version   # should print {"name": "heroes-tracker", "status": "ok"}
```

State (the SQLite cache) lives in `./data` on the host — back it up the same
way `backup.sh` handles Remndrs' `data/remndrs.db`, or just delete it to force
a full HeroesProfile resync.

## 4. Expose it through the existing tunnel

Add one ingress rule to bastion's `~/.cloudflared/config.yml` (reusing the
tunnel Remndrs already set up — see Remndrs' `CLOUDFLARE_SETUP.md` for how
that tunnel was created):

```yaml
# ~/.cloudflared/config.yml — port registry:
tunnel: remndrs
credentials-file: /home/pi/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: remndrs.app          #   3000 remndrs
    service: http://localhost:3000
  - hostname: heroes.yourdomain.com #   3001 heroes-tracker
    service: http://localhost:3001
  - service: http_status:404       # catch-all, keep last
```

```bash
cloudflared tunnel route dns remndrs heroes.yourdomain.com
sudo systemctl restart cloudflared   # or the relevant service-manager command on bastion
```

The Heroes-Tracker frontend and both Xeneon Edge widgets should then point at
`https://heroes.yourdomain.com` (or bastion's Tailscale address, if you'd
rather keep this off the public internet entirely — it's read-only personal
game data, so either is reasonable; Tailscale-only avoids needing a public
hostname at all).

## 5. Updating later

```bash
ssh -t bastion 'cd ~/Heroes-Tracker && git pull && cd backend && docker compose up -d --build'
```

## Open decisions this build left for you

- **Port/subdomain** — see the note at the top of this file.
- **Frontend hosting** — the React/Vite tracker app (`frontend/`) is dev-only
  for now (`npm run dev` on the Mac, pointed at the bastion API via
  `VITE_API_URL`). It's a static build, so it's trivial to serve from bastion
  later (nginx, or a second small container) if you want it always-on instead
  of Mac-only — say the word and that's a quick follow-up.
- **Rate limits/poll frequency** — `MATCH_POLL_MINUTES` (default 20) and
  `STATS_POLL_MINUTES` (default 360) in `.env` are conservative guesses.
  Read the caching/rate-limit section for your subscribed HeroesProfile tier
  and tighten or loosen these to match.
