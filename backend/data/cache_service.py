"""Cache orchestration: two-level read-through and invalidation logic.

This module implements the full cache stack for each data type:

    L1 (Redis, short TTL) → L2 (PostgreSQL, long TTL) → nba_api

On a read:
  1. Check L1 (Redis). Return immediately on hit.
  2. Check L2 (PostgreSQL, ``expires_at > now``). Populate L1 and return on hit.
  3. Fetch from nba_api. Write to L2 then L1. Return.

On a write (after API fetch):
  Always write L2 first, then L1. A crash between the two leaves L2 as the
  source of truth — the next request re-populates L1 from L2 at the cost of
  one extra database round-trip.

AI narrative invalidation uses a different rule: the narrative is considered
stale when ``player_game_logs.last_game_date`` is newer than the narrative's
``generated_at``. This comparison happens in ``is_narrative_stale()`` and the
caller (FastAPI endpoint) decides whether to regenerate.
"""

import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_postgres as pg
from backend.data import cache_redis as redis_cache
from backend.data import nba_client
from backend.data.models import PlayerGameLogs

logger = logging.getLogger(__name__)


# ── Unit conversion helpers ───────────────────────────────────────────────


def _feet_inches_to_cm(height_str: str | None) -> float | None:
    """Convert a feet-inches string (e.g. '6-7') to centimetres.

    nba_api returns player height as a string like '6-7'. The UI and all
    downstream logic work in metric units exclusively.
    """
    if not height_str:
        return None
    try:
        parts = height_str.split("-")
        feet = int(parts[0])
        inches = int(parts[1]) if len(parts) > 1 else 0
        return round((feet * 12 + inches) * 2.54, 1)
    except (ValueError, IndexError):
        logger.warning("Cannot parse height string: %r", height_str)
        return None


def _lbs_to_kg(weight_str: str | None) -> float | None:
    """Convert a weight string in pounds (e.g. '220') to kilograms."""
    if not weight_str:
        return None
    try:
        return round(float(weight_str) * 0.453592, 1)
    except ValueError:
        logger.warning("Cannot parse weight string: %r", weight_str)
        return None


# ── Game logs ─────────────────────────────────────────────────────────────


async def get_game_log(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> dict[str, Any]:
    """Return game log data for *player_id* in *season*.

    Traverses the full cache stack (L1 → L2 → API). The returned dict always
    contains a ``records`` key with the list of per-game rows.
    """
    # L1 — Redis
    cached = await redis_cache.get_game_log(player_id, season)
    if cached is not None:
        return cached

    # L2 — PostgreSQL
    cached = await pg.get_game_log(session, player_id, season)
    if cached is not None:
        await redis_cache.set_game_log(player_id, season, cached)
        return cached

    # Fetch from nba_api
    logger.info(
        "Fetching game log from nba_api: player=%d season=%s", player_id, season
    )
    df = await nba_client.fetch_game_log(player_id, season)
    records = df.to_dict(orient="records")
    data = {"records": records}

    last_game_date: datetime.date | None = None
    if records:
        try:
            last_game_date = datetime.datetime.strptime(
                records[0]["GAME_DATE"], "%b %d, %Y"
            ).date()
        except (KeyError, ValueError):
            pass

    # Write L2 then L1
    await pg.upsert_game_log(session, player_id, season, data, last_game_date)
    await redis_cache.set_game_log(player_id, season, data)

    return data


async def invalidate_game_log(
    session: AsyncSession, player_id: int, season: str
) -> None:
    """Force-expire a game log from both cache layers.

    Used by the background refresh job to ensure the next read triggers a fresh
    API fetch.
    """
    await redis_cache.invalidate_game_log(player_id, season)
    # L2 invalidation: clear expires_at by setting it to now — the next
    # read will see expires_at <= now and treat it as a miss.
    await session.execute(
        PlayerGameLogs.__table__.update()
        .where(
            PlayerGameLogs.player_id == player_id,
            PlayerGameLogs.season == season,
        )
        .values(expires_at=datetime.datetime.now(tz=datetime.timezone.utc))
    )
    logger.info(
        "Cache invalidated: game_log player=%d season=%s", player_id, season
    )


# ── Player bio ────────────────────────────────────────────────────────────


async def get_player_bio(
    session: AsyncSession,
    player_id: int,
) -> dict[str, Any]:
    """Return player bio data with height/weight in metric units.

    Conversion from feet-inches / pounds happens here, once, on the first API
    fetch. All subsequent reads serve the already-converted values.
    """
    # L1 — Redis
    cached = await redis_cache.get_player_bio(player_id)
    if cached is not None:
        return cached

    # L2 — PostgreSQL
    cached = await pg.get_player_bio(session, player_id)
    if cached is not None:
        await redis_cache.set_player_bio(player_id, cached)
        return cached

    # Fetch from nba_api
    logger.info("Fetching bio from nba_api: player=%d", player_id)
    df = await nba_client.fetch_player_info(player_id)
    row = df.iloc[0]

    bio: dict[str, Any] = {
        "player_id": player_id,
        "full_name": str(row.get("DISPLAY_FIRST_LAST", "")),
        "position": str(row.get("POSITION", "")) or None,
        "height_cm": _feet_inches_to_cm(str(row.get("HEIGHT", "")) or None),
        "weight_kg": _lbs_to_kg(str(row.get("WEIGHT", "")) or None),
        "country": str(row.get("COUNTRY", "")) or None,
        "team_abbreviation": str(row.get("TEAM_ABBREVIATION", "")) or None,
        "jersey_number": str(row.get("JERSEY", "")) or None,
    }

    await pg.upsert_player_bio(session, **bio)  # type: ignore[arg-type]
    await redis_cache.set_player_bio(player_id, bio)

    return bio


# ── Draft class ───────────────────────────────────────────────────────────


async def get_draft_class(
    session: AsyncSession,
    season_year: int,
) -> dict[str, Any]:
    """Return draft class data for *season_year*.

    The ``records`` key contains a list of all picks (both rounds).
    """
    # L1
    cached = await redis_cache.get_draft_class(season_year)
    if cached is not None:
        return cached

    # L2
    cached = await pg.get_draft_class(session, season_year)
    if cached is not None:
        await redis_cache.set_draft_class(season_year, cached)
        return cached

    # Fetch
    logger.info("Fetching draft class from nba_api: year=%d", season_year)
    df = await nba_client.fetch_draft_history(season_year)
    data = {"records": df.to_dict(orient="records")}

    await pg.upsert_draft_class(session, season_year, data)
    await redis_cache.set_draft_class(season_year, data)

    return data


# ── Season averages ───────────────────────────────────────────────────────


async def get_season_averages(
    session: AsyncSession,
    season: str,
) -> dict[str, Any]:
    """Return league-wide season averages for *season*.

    Backs the Draft Class Overview chart — one API call for the entire draft
    class instead of per-player calls.
    """
    # L1 — Redis uses season as key; player_id is 0 (sentinel for league-wide data)
    _LEAGUE_SENTINEL = 0
    cached = await redis_cache.get_season_averages(_LEAGUE_SENTINEL, season)
    if cached is not None:
        return cached

    # L2
    cached = await pg.get_season_averages(session, season)
    if cached is not None:
        await redis_cache.set_season_averages(_LEAGUE_SENTINEL, season, cached)
        return cached

    # Fetch
    logger.info("Fetching season averages from nba_api: season=%s", season)
    df = await nba_client.fetch_league_dash_stats(season)
    data = {"records": df.to_dict(orient="records")}

    await pg.upsert_season_averages(session, season, data)
    await redis_cache.set_season_averages(_LEAGUE_SENTINEL, season, data)

    return data


# ── Narrative staleness check ─────────────────────────────────────────────


async def is_narrative_stale(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> bool:
    """Return True when the cached narrative predates the latest game.

    The narrative is stale if:
      - No narrative exists in the database, OR
      - ``player_game_logs.last_game_date`` > ``ai_narratives.generated_at``

    This check is intentionally separate from the TTL-based expiry so that
    a narrative generated at noon is not regenerated just because 24 hours
    pass — it is only stale when new game data arrives.
    """
    generated_at = await pg.get_narrative_generated_at(
        session, player_id, season
    )
    if generated_at is None:
        return True

    result = await session.execute(
        select(PlayerGameLogs.last_game_date).where(
            PlayerGameLogs.player_id == player_id,
            PlayerGameLogs.season == season,
        )
    )
    last_game_date = result.scalar_one_or_none()
    if last_game_date is None:
        return False

    # Compare dates: last_game_date is a naive datetime stored as DATE.
    # generated_at is timezone-aware (UTC). Normalise before comparing.
    if isinstance(last_game_date, datetime.datetime):
        last_game_dt = last_game_date.replace(tzinfo=datetime.timezone.utc)
    else:
        last_game_dt = datetime.datetime(
            last_game_date.year,
            last_game_date.month,
            last_game_date.day,
            tzinfo=datetime.timezone.utc,
        )

    return last_game_dt > generated_at
