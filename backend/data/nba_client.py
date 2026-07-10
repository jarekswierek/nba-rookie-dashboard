"""Unified NBA API client with built-in rate limiting.

All external calls to nba_api go through this module. Direct usage of nba_api
endpoints elsewhere in the codebase is prohibited — this single entry point makes
swapping the upstream source or adding a mock trivial.

Rate limit: nba_api's public endpoint tolerates ~0.5 req/s sustained. Exceeding
this causes 429s that are hard to recover from during demos.
"""

import asyncio
import logging
import time
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import (
    commonallplayers,
    commonplayerinfo,
    drafthistory,
    leaguedashplayerstats,
    playercareerstats,
    playergamelog,
    scoreboardv2,
)

logger = logging.getLogger(__name__)

# Minimum seconds between consecutive API calls.
# nba_api's CDN bans callers that exceed ~1 req/s; 0.5 req/s is safe.
_MIN_INTERVAL_SECONDS: float = 2.0

_last_call_ts: float = 0.0
_rate_limit_lock = asyncio.Lock()


async def _throttle() -> None:
    """Enforce the minimum inter-request interval.

    Uses a module-level lock so concurrent coroutines queue up rather than firing
    simultaneously and tripping the upstream rate limit.
    """
    global _last_call_ts
    async with _rate_limit_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL_SECONDS - (now - _last_call_ts)
        if wait > 0:
            logger.debug(
                "Rate limiting: sleeping %.2fs before NBA API call", wait
            )
            await asyncio.sleep(wait)
        _last_call_ts = time.monotonic()


def _run_endpoint(endpoint_cls: Any, **kwargs: Any) -> pd.DataFrame:
    """Instantiate an nba_api endpoint and return its first result set.

    nba_api is synchronous under the hood (requests library). This helper
    standardises the call pattern so each fetch function stays one-liner.
    """
    endpoint = endpoint_cls(timeout=30, **kwargs)
    return endpoint.get_data_frames()[0]


async def fetch_scoreboard() -> pd.DataFrame:
    """Return today's scoreboard data.

    Used to detect whether the current season is active and how many games have
    been played today.
    """
    await _throttle()
    return await asyncio.to_thread(_run_endpoint, scoreboardv2.ScoreboardV2)


async def fetch_draft_history(season_year: int) -> pd.DataFrame:
    """Return full draft history for *season_year* (e.g. 2024).

    Columns include: PERSON_ID, PLAYER_NAME, TEAM_ABBREVIATION,
    ROUND_NUMBER, ROUND_PICK, OVERALL_PICK, ORGANIZATION.
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        drafthistory.DraftHistory,
        league_id="00",
        season_year_nullable=season_year,
    )


async def fetch_player_info(player_id: int) -> pd.DataFrame:
    """Return biographical data for a single player.

    Includes height (HEIGHT — feet-inches string), weight (WEIGHT — lbs string),
    position, country, current team, jersey number, and draft year. Height/weight
    unit conversion (imperial → metric) is the caller's responsibility.
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        commonplayerinfo.CommonPlayerInfo,
        player_id=player_id,
    )


async def fetch_game_log(
    player_id: int,
    season: str,
) -> pd.DataFrame:
    """Return game-by-game stats for *player_id* in *season*.

    Args:
        player_id: NBA player ID.
        season: Season string in 'YYYY-YY' format, e.g. '2024-25'.

    Columns include: GAME_DATE, MATCHUP, WL, MIN, PTS, REB, AST,
    STL, BLK, FG_PCT, FG3_PCT, FT_PCT, PLUS_MINUS.
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        playergamelog.PlayerGameLog,
        player_id=player_id,
        season=season,
    )


async def fetch_career_stats(player_id: int) -> pd.DataFrame:
    """Return per-season career averages for *player_id*.

    Uses SeasonAll to get all regular-season rows. Columns include SEASON_ID,
    TEAM_ABBREVIATION, GP, PTS, REB, AST, FG_PCT, FG3_PCT.
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        playercareerstats.PlayerCareerStats,
        player_id=player_id,
        per_mode36="PerGame",
    )


async def fetch_league_dash_stats(season: str) -> pd.DataFrame:
    """Return per-game averages for all players in *season*.

    Used to populate the Draft Class Overview chart without fetching
    each player individually. One call for the entire draft class.

    Columns include: PLAYER_ID, PLAYER_NAME, TEAM_ABBREVIATION,
    GP, PTS, REB, AST, FG_PCT, FG3_PCT.
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        leaguedashplayerstats.LeagueDashPlayerStats,
        season=season,
        per_mode_detailed="PerGame",
    )


async def fetch_all_players(season: str) -> pd.DataFrame:
    """Return all players who appeared in *season*.

    Used for player-ID lookups and team mapping (a player's current team may
    differ from the team that drafted them).
    """
    await _throttle()
    return await asyncio.to_thread(
        _run_endpoint,
        commonallplayers.CommonAllPlayers,
        league_id="00",
        season=season,
        is_only_current_season=1,
    )
