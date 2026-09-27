"""SQLite schema and query functions for Heroes Tracker."""

import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'heroes-tracker.db')

SCHEMA = """
-- Friends/group roster. `active` lets Clay retire a tag without losing history.
CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  battletag TEXT NOT NULL UNIQUE,
  display_name TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  added_at TEXT NOT NULL
);

-- One row per HeroesProfile replay/match.
CREATE TABLE IF NOT EXISTS matches (
  match_id TEXT PRIMARY KEY,
  game_type TEXT NOT NULL,        -- Storm League | Quick Match | ARAM | Unranked Draft | ...
  game_map TEXT,
  game_date TEXT NOT NULL,        -- ISO 8601, UTC
  game_length_seconds INTEGER,
  region TEXT,
  winning_team INTEGER,           -- 0 or 1
  fetched_at TEXT NOT NULL
);

-- One row per (match, player). talents is a JSON array of talent names/ids by
-- tier (index 0 = level 1 tier ... index 6 = level 20 tier); stats is a JSON
-- blob of whatever per-player fields HeroesProfile returns (kills, deaths,
-- assists, hero damage, healing, siege damage, experience, etc.) so schema
-- changes upstream don't require a migration here.
CREATE TABLE IF NOT EXISTS match_players (
  match_id TEXT NOT NULL,
  battletag TEXT NOT NULL,
  hero TEXT NOT NULL,
  team INTEGER NOT NULL,
  won INTEGER NOT NULL,
  hero_level INTEGER,
  talents TEXT NOT NULL DEFAULT '[]',
  stats TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (match_id, battletag),
  FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Precomputed per-match group tags: one row per distinct set of tracked
-- players (from `players`) who were on the same team in that match. group_key
-- is the sorted, pipe-joined battletags, e.g. "Karieo#1503|Griff17#1916" — the
-- same group key across matches is the same friend combo, queried directly by
-- get_groups_summary() with no join-time set logic.
CREATE TABLE IF NOT EXISTS match_groups (
  match_id TEXT NOT NULL,
  group_key TEXT NOT NULL,
  won INTEGER NOT NULL,
  PRIMARY KEY (match_id, group_key),
  FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Cached HeroesProfile hero stats, filtered to one rank bracket at fetch time
-- (see HEROESPROFILE_RANK_TIER). Refreshed on a schedule, never computed from
-- local match data — this mirrors HeroesProfile's own numbers, not Clay's.
CREATE TABLE IF NOT EXISTS hero_stats_cache (
  hero TEXT NOT NULL,
  game_type TEXT NOT NULL,
  rank_tier TEXT NOT NULL,
  win_rate REAL,
  pick_rate REAL,
  ban_rate REAL,
  games_played INTEGER,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (hero, game_type, rank_tier)
);

-- Cached talent build win rates. build_key is the JSON array of the 7 talent
-- picks (level 1/4/7/10/13/16/20) that make up one build.
CREATE TABLE IF NOT EXISTS talent_build_cache (
  hero TEXT NOT NULL,
  game_type TEXT NOT NULL,
  rank_tier TEXT NOT NULL,
  build_key TEXT NOT NULL,
  win_rate REAL,
  games_played INTEGER,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (hero, game_type, rank_tier, build_key)
);

-- Cached hero-vs-hero matchup win rates.
CREATE TABLE IF NOT EXISTS matchup_cache (
  hero TEXT NOT NULL,
  opponent_hero TEXT NOT NULL,
  game_type TEXT NOT NULL,
  rank_tier TEXT NOT NULL,
  win_rate REAL,
  games_played INTEGER,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (hero, opponent_hero, game_type, rank_tier)
);

-- Full hero roster (name + role), refreshed occasionally. The widgets build
-- their hero picker from this instead of a hardcoded list, so a new hero
-- release doesn't need a widget update.
CREATE TABLE IF NOT EXISTS heroes_cache (
  name TEXT PRIMARY KEY,
  role TEXT,
  updated_at TEXT NOT NULL
);

-- Small key/value table for scheduler bookkeeping (last poll time per job,
-- last-seen match id per tracked player, etc).
CREATE TABLE IF NOT EXISTS sync_state (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT NOT NULL
);
"""


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    # Seed the roster on first run only — never overwrites rows Clay has since
    # edited or removed via the admin endpoints.
    seeded = conn.execute('SELECT COUNT(*) AS n FROM players').fetchone()['n']
    if seeded == 0:
        seed_roster(conn)
    conn.close()


# Clay's own tag plus the initial friend roster from the build prompt. Edit
# freely after first run via the /api/players endpoints — this only seeds an
# empty table.
INITIAL_ROSTER = [
    ('karieo#1503', 'Karieo', 1),
    ('GamerinShade#1325', 'GamerinShade', 0),
    ('LoveSlug#11595', 'LoveSlug', 0),
    ('thatphilkid#1122', 'thatphilkid', 0),
    ('YodaFan#11454', 'YodaFan', 0),
    ('Griff17#1916', 'Griff17', 0),
    ('JuRJuR#1703', 'JuRJuR', 0),
]


def seed_roster(conn):
    ts = now_iso()
    for battletag, display_name, is_primary in INITIAL_ROSTER:
        conn.execute(
            'INSERT OR IGNORE INTO players (battletag, display_name, is_primary, active, added_at) '
            'VALUES (?, ?, ?, 1, ?)',
            (battletag, display_name, is_primary, ts),
        )
    conn.commit()


# ---- players ---------------------------------------------------------------

def list_players(include_inactive=False):
    conn = get_db()
    q = 'SELECT * FROM players'
    if not include_inactive:
        q += ' WHERE active = 1'
    q += ' ORDER BY is_primary DESC, display_name COLLATE NOCASE'
    rows = [dict(r) for r in conn.execute(q).fetchall()]
    conn.close()
    return rows


def get_primary_player():
    conn = get_db()
    row = conn.execute('SELECT * FROM players WHERE is_primary = 1 AND active = 1 LIMIT 1').fetchone()
    conn.close()
    return dict(row) if row else None


def add_player(battletag, display_name=None):
    conn = get_db()
    conn.execute(
        'INSERT INTO players (battletag, display_name, active, added_at) VALUES (?, ?, 1, ?)',
        (battletag, display_name or battletag.split('#')[0], now_iso()),
    )
    conn.commit()
    row = conn.execute('SELECT * FROM players WHERE battletag = ?', (battletag,)).fetchone()
    conn.close()
    return dict(row)


def update_player(player_id, display_name=None, active=None):
    conn = get_db()
    if display_name is not None:
        conn.execute('UPDATE players SET display_name = ? WHERE id = ?', (display_name, player_id))
    if active is not None:
        conn.execute('UPDATE players SET active = ? WHERE id = ?', (1 if active else 0, player_id))
    conn.commit()
    row = conn.execute('SELECT * FROM players WHERE id = ?', (player_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_player(player_id):
    conn = get_db()
    conn.execute('DELETE FROM players WHERE id = ?', (player_id,))
    conn.commit()
    conn.close()


# ---- matches ----------------------------------------------------------------

def upsert_match(match_id, game_type, game_map, game_date, game_length_seconds, region, winning_team, players):
    """players: list of dicts with battletag, hero, team, won, hero_level, talents, stats."""
    conn = get_db()
    conn.execute(
        'INSERT INTO matches (match_id, game_type, game_map, game_date, game_length_seconds, region, winning_team, fetched_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?) '
        'ON CONFLICT(match_id) DO UPDATE SET fetched_at = excluded.fetched_at',
        (match_id, game_type, game_map, game_date, game_length_seconds, region, winning_team, now_iso()),
    )
    for p in players:
        conn.execute(
            'INSERT INTO match_players (match_id, battletag, hero, team, won, hero_level, talents, stats) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(match_id, battletag) DO UPDATE SET '
            'hero = excluded.hero, team = excluded.team, won = excluded.won, '
            'hero_level = excluded.hero_level, talents = excluded.talents, stats = excluded.stats',
            (match_id, p['battletag'], p['hero'], p['team'], int(p['won']), p.get('hero_level'),
             json.dumps(p.get('talents', [])), json.dumps(p.get('stats', {}))),
        )
    conn.commit()
    _recompute_match_groups(conn, match_id)
    conn.commit()
    conn.close()


def _recompute_match_groups(conn, match_id):
    """Tag this match with every 2+ subset of tracked players who shared a team."""
    tracked = {r['battletag'] for r in conn.execute('SELECT battletag FROM players').fetchall()}
    rows = conn.execute(
        'SELECT battletag, team, won FROM match_players WHERE match_id = ?', (match_id,)
    ).fetchall()
    conn.execute('DELETE FROM match_groups WHERE match_id = ?', (match_id,))

    by_team = {}
    for r in rows:
        if r['battletag'] not in tracked:
            continue
        by_team.setdefault(r['team'], []).append(r)

    from itertools import combinations
    for team_rows in by_team.values():
        if len(team_rows) < 2:
            continue
        tags = sorted(r['battletag'] for r in team_rows)
        won = team_rows[0]['won']
        for size in range(2, len(tags) + 1):
            for combo in combinations(tags, size):
                group_key = '|'.join(combo)
                conn.execute(
                    'INSERT OR IGNORE INTO match_groups (match_id, group_key, won) VALUES (?, ?, ?)',
                    (match_id, group_key, won),
                )


def get_matches(battletag=None, game_type=None, limit=50, offset=0):
    conn = get_db()
    q = (
        'SELECT m.*, mp.hero, mp.team, mp.won, mp.hero_level, mp.talents, mp.stats, mp.battletag '
        'FROM matches m JOIN match_players mp ON mp.match_id = m.match_id WHERE 1=1'
    )
    params = []
    if battletag:
        q += ' AND mp.battletag = ?'
        params.append(battletag)
    if game_type:
        q += ' AND m.game_type = ?'
        params.append(game_type)
    q += ' ORDER BY m.game_date DESC LIMIT ? OFFSET ?'
    params += [limit, offset]
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    for r in rows:
        r['talents'] = json.loads(r['talents'])
        r['stats'] = json.loads(r['stats'])
    return rows


def get_match_detail(match_id):
    conn = get_db()
    match = conn.execute('SELECT * FROM matches WHERE match_id = ?', (match_id,)).fetchone()
    if not match:
        conn.close()
        return None
    players = [dict(r) for r in conn.execute(
        'SELECT * FROM match_players WHERE match_id = ? ORDER BY team, hero', (match_id,)
    ).fetchall()]
    conn.close()
    for p in players:
        p['talents'] = json.loads(p['talents'])
        p['stats'] = json.loads(p['stats'])
    result = dict(match)
    result['players'] = players
    return result


def get_last_match_date(battletag):
    conn = get_db()
    row = conn.execute(
        'SELECT MAX(m.game_date) AS last_date FROM matches m '
        'JOIN match_players mp ON mp.match_id = m.match_id WHERE mp.battletag = ?',
        (battletag,),
    ).fetchone()
    conn.close()
    return row['last_date'] if row else None


# ---- groups -------------------------------------------------------------

def get_groups_summary(min_games=1):
    conn = get_db()
    rows = conn.execute(
        'SELECT group_key, COUNT(*) AS games_played, SUM(won) AS wins '
        'FROM match_groups GROUP BY group_key HAVING games_played >= ? '
        'ORDER BY games_played DESC', (min_games,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'players': r['group_key'].split('|'),
            'games_played': r['games_played'],
            'wins': r['wins'],
            'win_rate': round(r['wins'] / r['games_played'] * 100, 1) if r['games_played'] else 0,
        })
    return result


# ---- hero / talent / matchup caches -----------------------------------------

def replace_hero_stats(game_type, rank_tier, rows):
    """rows: list of {hero, win_rate, pick_rate, ban_rate, games_played}."""
    conn = get_db()
    ts = now_iso()
    conn.execute('DELETE FROM hero_stats_cache WHERE game_type = ? AND rank_tier = ?', (game_type, rank_tier))
    for r in rows:
        conn.execute(
            'INSERT INTO hero_stats_cache (hero, game_type, rank_tier, win_rate, pick_rate, ban_rate, games_played, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (r['hero'], game_type, rank_tier, r.get('win_rate'), r.get('pick_rate'), r.get('ban_rate'),
             r.get('games_played'), ts),
        )
    conn.commit()
    conn.close()


def get_hero_stats(hero=None, game_type=None, rank_tier=None):
    conn = get_db()
    q = 'SELECT * FROM hero_stats_cache WHERE 1=1'
    params = []
    for col, val in (('hero', hero), ('game_type', game_type), ('rank_tier', rank_tier)):
        if val:
            q += f' AND {col} = ?'
            params.append(val)
    q += ' ORDER BY win_rate DESC'
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return rows


def replace_talent_builds(hero, game_type, rank_tier, builds):
    """builds: list of {build: [...7 talents...], win_rate, games_played}."""
    conn = get_db()
    ts = now_iso()
    conn.execute(
        'DELETE FROM talent_build_cache WHERE hero = ? AND game_type = ? AND rank_tier = ?',
        (hero, game_type, rank_tier),
    )
    for b in builds:
        conn.execute(
            'INSERT INTO talent_build_cache (hero, game_type, rank_tier, build_key, win_rate, games_played, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (hero, game_type, rank_tier, json.dumps(b['build']), b.get('win_rate'), b.get('games_played'), ts),
        )
    conn.commit()
    conn.close()


def get_talent_builds(hero, game_type, rank_tier, limit=5):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM talent_build_cache WHERE hero = ? AND game_type = ? AND rank_tier = ? '
        'ORDER BY win_rate DESC LIMIT ?',
        (hero, game_type, rank_tier, limit),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['build'] = json.loads(d.pop('build_key'))
        result.append(d)
    return result


def replace_matchups(hero, game_type, rank_tier, matchups):
    """matchups: list of {opponent_hero, win_rate, games_played}."""
    conn = get_db()
    ts = now_iso()
    conn.execute(
        'DELETE FROM matchup_cache WHERE hero = ? AND game_type = ? AND rank_tier = ?',
        (hero, game_type, rank_tier),
    )
    for m in matchups:
        conn.execute(
            'INSERT INTO matchup_cache (hero, opponent_hero, game_type, rank_tier, win_rate, games_played, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (hero, m['opponent_hero'], game_type, rank_tier, m.get('win_rate'), m.get('games_played'), ts),
        )
    conn.commit()
    conn.close()


def get_matchup(hero, opponent_hero, game_type, rank_tier):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM matchup_cache WHERE hero = ? AND opponent_hero = ? AND game_type = ? AND rank_tier = ?',
        (hero, opponent_hero, game_type, rank_tier),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_matchups(hero, game_type, rank_tier):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM matchup_cache WHERE hero = ? AND game_type = ? AND rank_tier = ? ORDER BY win_rate DESC',
        (hero, game_type, rank_tier),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---- heroes list --------------------------------------------------------

def replace_heroes(heroes):
    """heroes: list of {name, role}."""
    conn = get_db()
    ts = now_iso()
    conn.execute('DELETE FROM heroes_cache')
    for h in heroes:
        conn.execute(
            'INSERT INTO heroes_cache (name, role, updated_at) VALUES (?, ?, ?)',
            (h['name'], h.get('role'), ts),
        )
    conn.commit()
    conn.close()


def list_heroes():
    conn = get_db()
    rows = [dict(r) for r in conn.execute('SELECT * FROM heroes_cache ORDER BY name').fetchall()]
    conn.close()
    return rows


# ---- sync state ------------------------------------------------------------

def get_sync_state(key, default=None):
    conn = get_db()
    row = conn.execute('SELECT value FROM sync_state WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_sync_state(key, value):
    conn = get_db()
    conn.execute(
        'INSERT INTO sync_state (key, value, updated_at) VALUES (?, ?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
        (key, value, now_iso()),
    )
    conn.commit()
    conn.close()
