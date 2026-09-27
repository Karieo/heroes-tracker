"""Background polling: pulls fresh data from HeroesProfile on a schedule and
writes it into the local SQLite cache. Runs in-process alongside the Flask
server (see app.py) — same shape as Remndrs' reminder/digest scheduler."""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

import database as db
import heroesprofile_client as hp

log = logging.getLogger('heroes-tracker.scheduler')

# How often to pull match history for the tracked roster. HeroesProfile's own
# data only updates after Blizzard processes a replay (can lag 15-30+ min
# after a game ends), so polling faster than this just burns API calls.
MATCH_POLL_MINUTES = int(os.getenv('MATCH_POLL_MINUTES', '20'))

# How often to refresh hero/talent/matchup stat caches. These change slowly
# (they're rank-wide aggregates), so a long interval is fine and kinder to the
# rate limit — tighten once you've confirmed your tier's actual limits.
STATS_POLL_MINUTES = int(os.getenv('STATS_POLL_MINUTES', '360'))

# Rank/MMR bracket to filter hero/talent/matchup stats by. Must match one of
# HeroesProfile's tier labels for your subscribed endpoint (e.g. "Diamond",
# "Master", "Grandmaster") — set this to Clay's current bracket.
RANK_TIER = os.getenv('HEROESPROFILE_RANK_TIER', 'Diamond')

GAME_TYPES_FOR_STATS = ['Storm League', 'Quick Match']


def poll_match_history():
    players = db.list_players()
    if not players:
        return
    for player in players:
        try:
            matches = hp.get_player_match_history(player['battletag'])
        except Exception:
            log.exception('match history poll failed for %s', player['battletag'])
            continue
        for m in matches:
            db.upsert_match(
                m['match_id'], m['game_type'], m['game_map'], m['game_date'],
                m['game_length_seconds'], m['region'], m['winning_team'], m['players'],
            )
        db.set_sync_state(f"last_poll:{player['battletag']}", db.now_iso())
        log.info('%s: synced %d matches', player['battletag'], len(matches))


def poll_heroes():
    try:
        heroes = hp.get_heroes()
    except Exception:
        log.exception('heroes roster poll failed')
        return
    db.replace_heroes(heroes)
    log.info('synced %d heroes', len(heroes))
    return heroes


def poll_stats():
    heroes = db.list_heroes() or poll_heroes() or []
    hero_names = [h['name'] for h in heroes]

    for game_type in GAME_TYPES_FOR_STATS:
        try:
            rows = hp.get_hero_stats(game_type, RANK_TIER)
            db.replace_hero_stats(game_type, RANK_TIER, rows)
            log.info('hero stats: %s/%s -> %d heroes', game_type, RANK_TIER, len(rows))
        except Exception:
            log.exception('hero stats poll failed for %s', game_type)

        for hero in hero_names:
            try:
                builds = hp.get_talent_builds(hero, game_type, RANK_TIER)
                db.replace_talent_builds(hero, game_type, RANK_TIER, builds)
            except Exception:
                log.exception('talent build poll failed for %s/%s', hero, game_type)

            try:
                matchups = hp.get_matchups(hero, game_type, RANK_TIER)
                db.replace_matchups(hero, game_type, RANK_TIER, matchups)
            except Exception:
                log.exception('matchup poll failed for %s/%s', hero, game_type)

    db.set_sync_state('last_stats_poll', db.now_iso())


def start(scheduler=None):
    scheduler = scheduler or BackgroundScheduler(daemon=True)
    scheduler.add_job(poll_match_history, 'interval', minutes=MATCH_POLL_MINUTES,
                       next_run_time=None, id='poll_match_history', replace_existing=True)
    scheduler.add_job(poll_stats, 'interval', minutes=STATS_POLL_MINUTES,
                       id='poll_stats', replace_existing=True)
    scheduler.start()

    # Kick off an initial sync shortly after boot rather than waiting a full
    # interval, so a fresh container isn't empty for hours.
    scheduler.add_job(poll_heroes, id='initial_heroes')
    scheduler.add_job(poll_match_history, id='initial_match_history')
    scheduler.add_job(poll_stats, id='initial_stats')
    return scheduler
