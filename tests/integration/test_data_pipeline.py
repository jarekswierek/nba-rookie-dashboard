"""Integration tests for the two-level data cache pipeline.

Tests run against real Redis and PostgreSQL instances (Docker Compose stack).
The nba_api layer is patched with a fake client so tests are deterministic
and do not depend on network access or NBA API availability.

Three scenarios covered:
  1. Cache miss path — data flows from (mocked) nba_api → PostgreSQL L2
     → Redis L1, and is returned to the caller.
  2. Cache hit path — a second request for the same data is served from
     Redis L1 without touching PostgreSQL or nba_api.
  3. Narrative staleness — ``is_narrative_stale()`` returns True when a
     game log has a newer ``last_game_date`` than the stored narrative.
"""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_postgres as pg
from backend.data import cache_service
from backend.data.models import AiNarratives, PlayerGameLogs

# All tests in this module share one event loop so that module-level
# singletons (Redis connection pool, SQLAlchemy engine) are not
# recreated mid-suite with connections tied to a closed loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Shared test data ──────────────────────────────────────────────────────

_SEASON = "2024-25"

# Each test class uses a distinct player ID to avoid cross-test cache hits.
_PLAYER_ID_MISS = 9999901    # TestCacheMissPath
_PLAYER_ID_HIT = 9999902     # TestCacheHitPath
_PLAYER_ID_STALE = 9999903   # TestNarrativeStaleness

_FAKE_GAME_LOG_DF = pd.DataFrame(
    [
        {
            "GAME_DATE": "Jan 15, 2025",
            "MATCHUP": "NYK vs BOS",
            "WL": "W",
            "MIN": 32,
            "PTS": 24,
            "REB": 5,
            "AST": 3,
            "STL": 1,
            "BLK": 0,
            "FG_PCT": 0.511,
            "FG3_PCT": 0.400,
            "FT_PCT": 0.875,
            "PLUS_MINUS": 8,
        },
        {
            "GAME_DATE": "Jan 12, 2025",
            "MATCHUP": "NYK vs MIA",
            "WL": "L",
            "MIN": 28,
            "PTS": 18,
            "REB": 4,
            "AST": 5,
            "STL": 0,
            "BLK": 1,
            "FG_PCT": 0.444,
            "FG3_PCT": 0.333,
            "FT_PCT": 1.000,
            "PLUS_MINUS": -3,
        },
    ]
)


# ── Scenario 1: cache miss → API → L2 → L1 ───────────────────────────────

class TestCacheMissPath:
    """Data flows from nba_api through both cache layers on a cold start."""

    async def test_data_stored_in_redis_after_api_fetch(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """After a cache miss, the game log must be findable in Redis L1."""
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            await cache_service.get_game_log(pg_session, _PLAYER_ID_MISS, _SEASON)

        key = f"nba:game_log:{_PLAYER_ID_MISS}:{_SEASON}"
        raw = await redis_client.get(key)
        assert raw is not None, "Game log was not written to Redis after API fetch"
        payload = json.loads(raw)
        assert "records" in payload
        assert len(payload["records"]) == 2

    async def test_data_stored_in_postgres_after_api_fetch(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """After a cache miss, the game log must be persisted in PostgreSQL L2."""
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            await cache_service.get_game_log(pg_session, _PLAYER_ID_MISS, _SEASON)

        # Bypass Redis to confirm the PostgreSQL row exists.
        pg_data = await pg.get_game_log(pg_session, _PLAYER_ID_MISS, _SEASON)
        assert pg_data is not None, "Game log was not written to PostgreSQL after API fetch"
        assert len(pg_data["records"]) == 2

    async def test_last_game_date_parsed_correctly(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """last_game_date must be extracted from the most-recent game row."""
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            await cache_service.get_game_log(pg_session, _PLAYER_ID_MISS, _SEASON)

        result = await pg_session.execute(
            select(PlayerGameLogs.last_game_date).where(
                PlayerGameLogs.player_id == _PLAYER_ID_MISS,
                PlayerGameLogs.season == _SEASON,
            )
        )
        last_game_date = result.scalar_one_or_none()
        assert last_game_date is not None
        # The first row in the fake DF is Jan 15 2025.
        assert last_game_date.month == 1
        assert last_game_date.day == 15
        assert last_game_date.year == 2025


# ── Scenario 2: cache hit path (L1 served from Redis) ────────────────────

class TestCacheHitPath:
    """A warm cache serves data from Redis without hitting nba_api or PostgreSQL."""

    async def test_second_request_served_from_redis(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """nba_api must be called exactly once even with two identical requests."""
        mock_fetch = AsyncMock(return_value=_FAKE_GAME_LOG_DF)
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=mock_fetch,
        ):
            # First request — cache miss, hits API.
            await cache_service.get_game_log(pg_session, _PLAYER_ID_HIT, _SEASON)
            # Second request — should be served from Redis L1.
            result = await cache_service.get_game_log(pg_session, _PLAYER_ID_HIT, _SEASON)

        mock_fetch.assert_called_once(), (
            "nba_api was called more than once — Redis L1 cache miss on second request"
        )
        assert result is not None
        assert len(result["records"]) == 2

    async def test_cache_hit_data_matches_original(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """Data returned from L1 must be identical to what was originally stored."""
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            first = await cache_service.get_game_log(pg_session, _PLAYER_ID_HIT, _SEASON)
            second = await cache_service.get_game_log(pg_session, _PLAYER_ID_HIT, _SEASON)

        assert first == second


# ── Scenario 3: narrative staleness ──────────────────────────────────────

class TestNarrativeStaleness:
    """Narrative is stale when a game has been played after it was generated."""

    async def test_narrative_stale_when_new_game_played(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """is_narrative_stale() must return True when game log is newer."""
        # Insert a game log with last_game_date = today.
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        yesterday = now - datetime.timedelta(days=1)

        # Game log — last game was today (after the narrative was generated).
        pg_session.add(
            PlayerGameLogs(
                player_id=_PLAYER_ID_STALE,
                season=_SEASON,
                data={"records": []},
                last_game_date=now.date(),
                fetched_at=now,
                expires_at=now + datetime.timedelta(hours=24),
            )
        )
        # Narrative generated yesterday — before the last game.
        pg_session.add(
            AiNarratives(
                player_id=_PLAYER_ID_STALE,
                season=_SEASON,
                summary="Test narrative",
                trend_direction="up",
                confidence=0.8,
                generated_at=yesterday,
                expires_at=now + datetime.timedelta(hours=24),
            )
        )
        await pg_session.flush()

        stale = await cache_service.is_narrative_stale(pg_session, _PLAYER_ID_STALE, _SEASON)
        assert stale is True, (
            "Narrative should be stale when last_game_date > generated_at"
        )

    async def test_narrative_fresh_when_no_new_games(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """is_narrative_stale() must return False when narrative is newer than last game."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        yesterday = now - datetime.timedelta(days=1)

        # Game log — last game was yesterday.
        pg_session.add(
            PlayerGameLogs(
                player_id=_PLAYER_ID_STALE,
                season=_SEASON,
                data={"records": []},
                last_game_date=yesterday.date(),
                fetched_at=now,
                expires_at=now + datetime.timedelta(hours=24),
            )
        )
        # Narrative generated now — after the last game.
        pg_session.add(
            AiNarratives(
                player_id=_PLAYER_ID_STALE,
                season=_SEASON,
                summary="Fresh narrative",
                trend_direction="stable",
                confidence=0.75,
                generated_at=now,
                expires_at=now + datetime.timedelta(hours=24),
            )
        )
        await pg_session.flush()

        stale = await cache_service.is_narrative_stale(pg_session, _PLAYER_ID_STALE, _SEASON)
        assert stale is False, (
            "Narrative should be fresh when generated_at >= last_game_date"
        )

    async def test_narrative_stale_when_no_narrative_exists(
        self,
        pg_session: AsyncSession,
        redis_client: aioredis.Redis,  # type: ignore[type-arg]
    ) -> None:
        """is_narrative_stale() must return True when there is no narrative at all."""
        stale = await cache_service.is_narrative_stale(
            pg_session,
            player_id=9999999,  # ID with no data in DB.
            season=_SEASON,
        )
        assert stale is True, (
            "Narrative should be stale (missing) when no row exists in ai_narratives"
        )
