"""Heroes Tracker backend — Flask API + APScheduler poller, one process.

Talks to HeroesProfile (see heroesprofile_client.py) on a schedule and caches
everything in SQLite (see database.py). The tracker frontend and the Xeneon
Edge widgets only ever talk to this service — the HeroesProfile API token
never leaves this process.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request

import database as db
import scheduler as poller

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('heroes-tracker')

app = Flask(__name__)

RANK_TIER = os.getenv('HEROESPROFILE_RANK_TIER', 'Diamond')
DEFAULT_GAME_TYPE = 'Storm League'


@app.after_request
def add_edge_cors(resp):
    # The widgets load as local files inside iCUE, so /api/edge/* needs an
    # open CORS header (read-only public-to-Clay data — same call PIT WALL's
    # feed makes). Everything else stays same-origin only.
    if request.path.startswith('/api/edge/'):
        resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.get('/api/version')
def version():
    return jsonify({'name': 'heroes-tracker', 'status': 'ok'})


# ---- players / roster (admin) -----------------------------------------------

@app.get('/api/players')
def api_list_players():
    return jsonify(db.list_players(include_inactive=request.args.get('all') == '1'))


@app.post('/api/players')
def api_add_player():
    body = request.get_json(force=True) or {}
    battletag = (body.get('battletag') or '').strip()
    if '#' not in battletag:
        return jsonify({'error': 'battletag must look like Name#1234'}), 400
    try:
        return jsonify(db.add_player(battletag, body.get('display_name'))), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 409


@app.put('/api/players/<int:player_id>')
def api_update_player(player_id):
    body = request.get_json(force=True) or {}
    row = db.update_player(player_id, display_name=body.get('display_name'), active=body.get('active'))
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(row)


@app.delete('/api/players/<int:player_id>')
def api_delete_player(player_id):
    db.delete_player(player_id)
    return '', 204


# ---- match history -----------------------------------------------------------

@app.get('/api/matches')
def api_matches():
    battletag = request.args.get('battletag') or (db.get_primary_player() or {}).get('battletag')
    return jsonify(db.get_matches(
        battletag=battletag,
        game_type=request.args.get('game_type'),
        limit=int(request.args.get('limit', 50)),
        offset=int(request.args.get('offset', 0)),
    ))


@app.get('/api/matches/<match_id>')
def api_match_detail(match_id):
    match = db.get_match_detail(match_id)
    if not match:
        return jsonify({'error': 'not found'}), 404
    return jsonify(match)


# ---- hero stats / talents / matchups ------------------------------------------

@app.get('/api/heroes')
def api_heroes():
    return jsonify(db.list_heroes())


@app.get('/api/heroes/<hero>/stats')
def api_hero_stats(hero):
    game_type = request.args.get('game_type', DEFAULT_GAME_TYPE)
    rank_tier = request.args.get('rank_tier', RANK_TIER)
    rows = db.get_hero_stats(hero=hero, game_type=game_type, rank_tier=rank_tier)
    return jsonify(rows[0] if rows else {})


@app.get('/api/heroes/<hero>/talents')
def api_hero_talents(hero):
    game_type = request.args.get('game_type', DEFAULT_GAME_TYPE)
    rank_tier = request.args.get('rank_tier', RANK_TIER)
    limit = int(request.args.get('limit', 5))
    return jsonify(db.get_talent_builds(hero, game_type, rank_tier, limit=limit))


@app.get('/api/heroes/<hero>/matchups')
def api_hero_matchups(hero):
    game_type = request.args.get('game_type', DEFAULT_GAME_TYPE)
    rank_tier = request.args.get('rank_tier', RANK_TIER)
    return jsonify(db.get_matchups(hero, game_type, rank_tier))


# ---- friend groups ------------------------------------------------------------

@app.get('/api/groups')
def api_groups():
    min_games = int(request.args.get('min_games', 1))
    return jsonify(db.get_groups_summary(min_games=min_games))


# ---- Xeneon Edge widget feeds --------------------------------------------------
# Small, purpose-built JSON for the widgets — see
# XENEON-Edge-Widgets-/docs/heroes-edge-feed.md for the documented shape.

@app.get('/api/edge/heroes')
def edge_heroes():
    return jsonify({'heroes': db.list_heroes()})


@app.get('/api/edge/matchup')
def edge_matchup():
    hero = request.args.get('hero', '')
    enemy = request.args.get('enemy', '')
    game_type = request.args.get('game_type', DEFAULT_GAME_TYPE)
    rank_tier = request.args.get('rank_tier', RANK_TIER)
    if not hero or not enemy:
        return jsonify({'error': 'hero and enemy are required'}), 400
    matchup = db.get_matchup(hero, enemy, game_type, rank_tier)
    builds = db.get_talent_builds(hero, game_type, rank_tier, limit=3)
    return jsonify({
        'hero': hero,
        'enemy': enemy,
        'game_type': game_type,
        'rank_tier': rank_tier,
        'matchup': matchup,
        'top_builds': builds,
    })


@app.get('/api/edge/hero-reference')
def edge_hero_reference():
    hero = request.args.get('hero', '')
    game_type = request.args.get('game_type', DEFAULT_GAME_TYPE)
    rank_tier = request.args.get('rank_tier', RANK_TIER)
    if not hero:
        return jsonify({'error': 'hero is required'}), 400

    stats_rows = db.get_hero_stats(hero=hero, game_type=game_type, rank_tier=rank_tier)
    builds = db.get_talent_builds(hero, game_type, rank_tier, limit=5)

    battletag = (db.get_primary_player() or {}).get('battletag')
    personal_matches = [m for m in db.get_matches(battletag=battletag, game_type=game_type, limit=500)
                         if m['hero'] == hero] if battletag else []
    games = len(personal_matches)
    wins = sum(1 for m in personal_matches if m['won'])

    return jsonify({
        'hero': hero,
        'game_type': game_type,
        'rank_tier': rank_tier,
        'rank_stats': stats_rows[0] if stats_rows else None,
        'top_builds': builds,
        'personal': {
            'games_played': games,
            'win_rate': round(wins / games * 100, 1) if games else None,
        },
    })


if __name__ == '__main__':
    db.init_db()
    poller.start()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3001)))
