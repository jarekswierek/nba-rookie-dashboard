"""PostgreSQL L2 cache for persisted NBA data.

Stores the same categories of data as the Redis L1 cache but with longer
TTLs and no eviction policy — rows persist until their ``expires_at``
timestamp passes or until a forced invalidation.

Callers follow this pattern:
  1. Check Redis (L1) — return if hit.
  2. Check PostgreSQL (L2) — return if fresh (``expires_at`` in the future).
  3. Fetch from nba_api — write to both L2 and L1, return.

This module only handles step 2 (read / write to PostgreSQL). The
orchestration logic lives in the service layer (TASK-204).

TTLs (PostgreSQL):
  - game_log / season_averages : 24 hours
  - draft / bio                : 7 days
"""

import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.models import (
    AiNarratives,
    DraftClasses,
    PlayerBios,
    PlayerGameLogs,
    SeasonAverages,
)

logger = logging.getLogger(__name__)

# ── TTL constants ─────────────────────────────────────────────────────────
_TTL_GAME_LOG = datetime.timedelta(hours=24)
_TTL_SEASON_AVERAGES = datetime.timedelta(hours=24)
_TTL_DRAFT = datetime.timedelta(days=7)
_TTL_BIO = datetime.timedelta(days=7)
_TTL_NARRATIVE = datetime.timedelta(hours=24)


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


# ── Player game logs ──────────────────────────────────────────────────────


async def get_game_log(
    session: AsyncSession, player_id: int, season: str
) -> dict[str, Any] | None:
    """Return a fresh game log row or *None* if absent / stale."""
    result = await session.execute(
        select(PlayerGameLogs).where(
            PlayerGameLogs.player_id == player_id,
            PlayerGameLogs.season == season,
            PlayerGameLogs.expires_at > _now_utc(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.debug(
            "PG L2 miss: game_log player=%d season=%s", player_id, season
        )
        return None
    logger.debug("PG L2 hit: game_log player=%d season=%s", player_id, season)
    return dict(row.data)


async def upsert_game_log(
    session: AsyncSession,
    player_id: int,
    season: str,
    data: dict[str, Any],
    last_game_date: datetime.date | None = None,
) -> None:
    """Insert or update the game log row for *(player_id, season)*."""
    now = _now_utc()
    expires_at = now + _TTL_GAME_LOG

    await session.execute(
        PlayerGameLogs.__table__.delete().where(
            PlayerGameLogs.player_id == player_id,
            PlayerGameLogs.season == season,
        )
    )
    session.add(
        PlayerGameLogs(
            player_id=player_id,
            season=season,
            data=data,
            last_game_date=last_game_date,
            fetched_at=now,
            expires_at=expires_at,
        )
    )
    await session.flush()
    logger.debug("PG L2 write: game_log player=%d season=%s", player_id, season)


# ── Player bios ───────────────────────────────────────────────────────────


async def get_player_bio(
    session: AsyncSession, player_id: int
) -> dict[str, Any] | None:
    """Return a fresh player bio row or *None* if absent / stale."""
    result = await session.execute(
        select(PlayerBios).where(
            PlayerBios.player_id == player_id,
            PlayerBios.expires_at > _now_utc(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.debug("PG L2 miss: bio player=%d", player_id)
        return None
    logger.debug("PG L2 hit: bio player=%d", player_id)
    return {
        "player_id": row.player_id,
        "full_name": row.full_name,
        "position": row.position,
        "height_cm": row.height_cm,
        "weight_kg": row.weight_kg,
        "country": row.country,
        "team_abbreviation": row.team_abbreviation,
        "jersey_number": row.jersey_number,
    }


async def upsert_player_bio(
    session: AsyncSession,
    player_id: int,
    full_name: str,
    position: str | None,
    height_cm: float | None,
    weight_kg: float | None,
    country: str | None,
    team_abbreviation: str | None,
    jersey_number: str | None,
) -> None:
    """Insert or update the bio row for *player_id*.

    Uses PostgreSQL ``ON CONFLICT DO UPDATE`` on the ``player_id`` unique
    constraint so concurrent requests cannot create duplicate rows.
    """
    now = _now_utc()
    expires_at = now + _TTL_BIO

    stmt = (
        pg_insert(PlayerBios)
        .values(
            player_id=player_id,
            full_name=full_name,
            position=position,
            height_cm=height_cm,
            weight_kg=weight_kg,
            country=country,
            team_abbreviation=team_abbreviation,
            jersey_number=jersey_number,
            fetched_at=now,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            index_elements=["player_id"],
            set_={
                "full_name": full_name,
                "position": position,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "country": country,
                "team_abbreviation": team_abbreviation,
                "jersey_number": jersey_number,
                "fetched_at": now,
                "expires_at": expires_at,
            },
        )
    )
    await session.execute(stmt)
    logger.debug("PG L2 write: bio player=%d", player_id)


# ── Draft classes ─────────────────────────────────────────────────────────


async def get_draft_class(
    session: AsyncSession, season_year: int
) -> dict[str, Any] | None:
    """Return a fresh draft class row or *None* if absent / stale."""
    result = await session.execute(
        select(DraftClasses).where(
            DraftClasses.season_year == season_year,
            DraftClasses.expires_at > _now_utc(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.debug("PG L2 miss: draft year=%d", season_year)
        return None
    logger.debug("PG L2 hit: draft year=%d", season_year)
    return dict(row.data)


async def upsert_draft_class(
    session: AsyncSession, season_year: int, data: dict[str, Any]
) -> None:
    """Insert or update the draft class row for *season_year*."""
    now = _now_utc()
    stmt = (
        pg_insert(DraftClasses)
        .values(
            season_year=season_year,
            data=data,
            fetched_at=now,
            expires_at=now + _TTL_DRAFT,
        )
        .on_conflict_do_update(
            index_elements=["season_year"],
            set_={
                "data": data,
                "fetched_at": now,
                "expires_at": now + _TTL_DRAFT,
            },
        )
    )
    await session.execute(stmt)
    logger.debug("PG L2 write: draft year=%d", season_year)


# ── Season averages ───────────────────────────────────────────────────────


async def get_season_averages(
    session: AsyncSession, season: str
) -> dict[str, Any] | None:
    """Return a fresh season averages row or *None* if absent / stale."""
    result = await session.execute(
        select(SeasonAverages).where(
            SeasonAverages.season == season,
            SeasonAverages.expires_at > _now_utc(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.debug("PG L2 miss: season_averages season=%s", season)
        return None
    logger.debug("PG L2 hit: season_averages season=%s", season)
    return dict(row.data)


async def upsert_season_averages(
    session: AsyncSession, season: str, data: dict[str, Any]
) -> None:
    """Insert or update the league-wide season averages for *season*."""
    now = _now_utc()
    stmt = (
        pg_insert(SeasonAverages)
        .values(
            season=season,
            data=data,
            fetched_at=now,
            expires_at=now + _TTL_SEASON_AVERAGES,
        )
        .on_conflict_do_update(
            index_elements=["season"],
            set_={
                "data": data,
                "fetched_at": now,
                "expires_at": now + _TTL_SEASON_AVERAGES,
            },
        )
    )
    await session.execute(stmt)
    logger.debug("PG L2 write: season_averages season=%s", season)


# ── AI narratives ─────────────────────────────────────────────────────────


async def get_narrative(
    session: AsyncSession, player_id: int, season: str
) -> dict[str, Any] | None:
    """Return a cached narrative or *None* if absent / stale.

    Staleness here means ``expires_at`` is in the past — the caller is
    responsible for the secondary staleness check based on
    ``last_game_date`` vs ``generated_at`` (see cache invalidation layer).
    """
    result = await session.execute(
        select(AiNarratives).where(
            AiNarratives.player_id == player_id,
            AiNarratives.season == season,
            AiNarratives.expires_at > _now_utc(),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.debug(
            "PG L2 miss: narrative player=%d season=%s", player_id, season
        )
        return None
    logger.debug("PG L2 hit: narrative player=%d season=%s", player_id, season)
    return {
        "summary": row.summary,
        "trend_direction": row.trend_direction,
        "confidence": row.confidence,
        "generated_at": row.generated_at.isoformat(),
    }


async def get_narrative_generated_at(
    session: AsyncSession, player_id: int, season: str
) -> datetime.datetime | None:
    """Return the ``generated_at`` timestamp of the latest narrative.

    Used to compare against ``last_game_date`` in ``player_game_logs`` to decide
    whether regeneration is needed.
    """
    result = await session.execute(
        select(AiNarratives.generated_at).where(
            AiNarratives.player_id == player_id,
            AiNarratives.season == season,
        )
    )
    return result.scalar_one_or_none()


async def upsert_narrative(
    session: AsyncSession,
    player_id: int,
    season: str,
    summary: str,
    trend_direction: str,
    confidence: float,
) -> None:
    """Insert or update the AI narrative for *(player_id, season)*."""
    now = _now_utc()

    # Delete existing row then insert — simpler than a composite ON CONFLICT
    # because ai_narratives has no unique constraint on (player_id, season).
    await session.execute(
        AiNarratives.__table__.delete().where(
            AiNarratives.player_id == player_id,
            AiNarratives.season == season,
        )
    )
    session.add(
        AiNarratives(
            player_id=player_id,
            season=season,
            summary=summary,
            trend_direction=trend_direction,
            confidence=confidence,
            generated_at=now,
            expires_at=now + _TTL_NARRATIVE,
        )
    )
    await session.flush()
    logger.debug("PG L2 write: narrative player=%d season=%s", player_id, season)
