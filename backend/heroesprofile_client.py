"""Thin client for the HeroesProfile API (api.heroesprofile.com).

IMPORTANT — verify before first run: this sandbox's network policy blocks
api.heroesprofile.com and heroesprofile.com, so these endpoint paths and
parameter names were written from memory/documentation conventions, not
fetched live. Before the scheduler runs for real:

  1. Log into heroesprofile.com/Api with the subscribed account and open the
     interactive API docs.
  2. Compare every path/param below against what's documented for your tier
     (Basic vs Intermediate can expose different routes).
  3. Fix anything that doesn't match — everything HeroesProfile-specific is
     confined to this one file; database.py and app.py don't care how the
     data got here, only that these functions return the shapes described in
     each docstring.

Every method returns plain dicts/lists already normalized to what
database.py's upsert_*/replace_* functions expect, so a fix here never has to
ripple further.
"""

import os
import time

import requests

BASE_URL = os.getenv('HEROESPROFILE_BASE_URL', 'https://api.heroesprofile.com/api').rstrip('/')
API_TOKEN = os.getenv('HEROESPROFILE_API_TOKEN', '')

# Games marked "Custom" or "Brawl" etc. aren't useful for stats and are
# skipped when normalizing match history.
TRACKED_GAME_TYPES = {'Storm League', 'Quick Match', 'ARAM', 'Unranked Draft'}

_session = requests.Session()

# HeroesProfile asks subscribers to space out calls — this is a conservative
# floor, not a documented number. Tighten or loosen it once you've read the
# rate-limit section for your tier.
_MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv('HEROESPROFILE_MIN_INTERVAL', '1.0'))
_last_request_at = 0.0


class HeroesProfileError(RuntimeError):
    pass


def _get(path, params=None):
    global _last_request_at
    if not API_TOKEN:
        raise HeroesProfileError('HEROESPROFILE_API_TOKEN is not set')

    wait = _MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)

    params = dict(params or {})
    params['api_token'] = API_TOKEN

    resp = _session.get(f'{BASE_URL}{path}', params=params, timeout=30)
    _last_request_at = time.monotonic()

    if resp.status_code == 429:
        raise HeroesProfileError(f'rate limited on {path} (429)')
    resp.raise_for_status()
    return resp.json()


# ---- player match history --------------------------------------------------

def get_player_match_history(battletag, region='1'):
    """Recent replays for one battletag ("Name#1234").

    Expected upstream shape (per HeroesProfile's Player/Match_History-style
    endpoint): a list of match dicts, each with the replay/match id, game
    type, map, date, length, and a per-player breakdown including hero,
    team, win/loss, level, talents picked, and the raw stat block.

    Returns: list of normalized dicts —
      {match_id, game_type, game_map, game_date, game_length_seconds, region,
       winning_team, players: [{battletag, hero, team, won, hero_level,
       talents, stats}]}
    """
    name, _, tag = battletag.partition('#')
    raw = _get('/Player/Match_History', {
        'battletag': name,
        'battletag_id': tag,
        'region': region,
    })

    matches = []
    for m in raw if isinstance(raw, list) else raw.get('data', []):
        game_type = m.get('game_type') or m.get('type')
        if TRACKED_GAME_TYPES and game_type not in TRACKED_GAME_TYPES:
            continue
        players = []
        for p in m.get('players', []):
            players.append({
                'battletag': p.get('battletag') or battletag,
                'hero': p.get('hero'),
                'team': int(p.get('team', 0)),
                'won': bool(p.get('winner') or p.get('won')),
                'hero_level': p.get('hero_level'),
                'talents': p.get('talents', []),
                'stats': p.get('stats', p),
            })
        matches.append({
            'match_id': str(m.get('replayID') or m.get('match_id')),
            'game_type': game_type,
            'game_map': m.get('game_map') or m.get('map'),
            'game_date': m.get('game_date') or m.get('created_at'),
            'game_length_seconds': m.get('game_length'),
            'region': m.get('region', region),
            'winning_team': int(m.get('winning_team', 0)),
            'players': players,
        })
    return matches


# ---- hero roster ------------------------------------------------------------

def get_heroes():
    """Full hero roster. Returns list of {name, role}."""
    raw = _get('/Heroes')
    items = raw if isinstance(raw, list) else raw.values()
    return [{'name': h.get('name'), 'role': h.get('role') or h.get('type')} for h in items]


# ---- hero stats (win rate / pick rate / ban rate) ---------------------------

def get_hero_stats(game_type, rank_tier):
    """Aggregate hero stats at one rank bracket. Returns list of
    {hero, win_rate, pick_rate, ban_rate, games_played}."""
    raw = _get('/Heroes/Stats', {
        'game_type': game_type,
        'tier': rank_tier,
    })
    items = raw if isinstance(raw, list) else raw.values()
    return [{
        'hero': h.get('hero'),
        'win_rate': _pct(h.get('win_rate') or h.get('win_percent')),
        'pick_rate': _pct(h.get('pick_rate') or h.get('pick_percent')),
        'ban_rate': _pct(h.get('ban_rate') or h.get('ban_percent')),
        'games_played': h.get('games_played') or h.get('pick_rate_games_played'),
    } for h in items]


# ---- talent build win rates --------------------------------------------------

def get_talent_builds(hero, game_type, rank_tier):
    """Top talent combinations for one hero. Returns list of
    {build: [t1..t7], win_rate, games_played}."""
    raw = _get('/Talents/Builds', {
        'hero': hero,
        'game_type': game_type,
        'tier': rank_tier,
    })
    items = raw if isinstance(raw, list) else raw.values()
    return [{
        'build': b.get('build') or b.get('talents') or [],
        'win_rate': _pct(b.get('win_rate') or b.get('win_percent')),
        'games_played': b.get('games_played') or b.get('popularity_games_played'),
    } for b in items]


# ---- hero-vs-hero matchup win rates ------------------------------------------

def get_matchups(hero, game_type, rank_tier):
    """Win rate for `hero` against every other hero. Returns list of
    {opponent_hero, win_rate, games_played}."""
    raw = _get('/Matchups', {
        'hero': hero,
        'game_type': game_type,
        'tier': rank_tier,
    })
    items = raw if isinstance(raw, list) else raw.values()
    return [{
        'opponent_hero': m.get('opponent_hero') or m.get('enemy_hero'),
        'win_rate': _pct(m.get('win_rate') or m.get('win_percent')),
        'games_played': m.get('games_played') or m.get('matchup_games_played'),
    } for m in items]


def _pct(value):
    """HeroesProfile sometimes returns win rates as 0-1, sometimes 0-100.
    Normalize to a 0-100 float so the frontend/widgets don't have to guess."""
    if value is None:
        return None
    value = float(value)
    return value * 100 if value <= 1 else value
