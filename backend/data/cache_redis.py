"""Redis L1 cache for hot NBA data.

Sits in front of the PostgreSQL L2 cache and the nba_api client.
Keys are namespaced by data type to make bulk-invalidation easy
(e.g. flush all game-log keys without touching bio keys).

TTLs are defined per data type and match the invalidation strategy
documented in the project backlog:
  - game_log / season_averages : 4 hours  (updated after every game night)
  - draft / bio / roster       : 24 hours (changes only on trade / waiver)

The module never raises on cache misses — callers get ``None`` and are
expected to fall back to L2 / nba_api.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

# ── TTL constants (seconds) ────────────────────────────────────────────────
TTL_GAME_LOG: int = 4 * 3600  # 4 hours
TTL_SEASON_AVERAGES: int = 4 * 3600  # 4 hours
TTL_DRAFT: int = 24 * 3600  # 24 hours
TTL_BIO: int = 24 * 3600  # 24 hours
TTL_ROSTER: int = 24 * 3600  # 24 hours
TTL_SCOREBOARD: int = 1 * 3600  # 1 hour

# ── Key prefixes ───────────────────────────────────────────────────────────
_PREFIX_GAME_LOG = "nba:game_log"
_PREFIX_SEASON_AVG = "nba:season_avg"
_PREFIX_DRAFT = "nba:draft"
_PREFIX_BIO = "nba:bio"
_PREFIX_SCOREBOARD = "nba:scoreboard"


def _make_client() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return a new async Redis client from current settings.

    Called once at module import and reused. A single client is safe for
    concurrent coroutines — the redis-py async driver multiplexes over one
    connection pool internally.
    """
    settings = get_settings()
    return aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


# Module-level singleton — avoids re-creating the connection pool on every call.
_redis: aioredis.Redis = _make_client()  # type: ignore[type-arg]


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return the shared Redis client.

    Exposed for dependency injection in FastAPI routes and test fixtures.
    """
    return _redis


# ── Internal helpers ───────────────────────────────────────────────────────


async def _get(key: str) -> Any | None:
    """Return decoded JSON value or *None* on miss."""
    raw = await _redis.get(key)
    if raw is None:
        logger.debug("Cache miss: %s", key)
        return None
    logger.debug("Cache hit: %s", key)
    return json.loads(raw)


async def _set(key: str, value: Any, ttl: int) -> None:
    """Serialise *value* to JSON and store with *ttl* seconds expiry."""
    await _redis.setex(key, ttl, json.dumps(value))
    logger.debug("Cache set: %s (ttl=%ds)", key, ttl)


async def _delete(key: str) -> None:
    """Remove a single key — used for forced invalidation."""
    await _redis.delete(key)
    logger.debug("Cache deleted: %s", key)


# ── Public API ─────────────────────────────────────────────────────────────


async def get_game_log(player_id: int, season: str) -> Any | None:
    """Return cached game log records or *None* on miss."""
    return await _get(f"{_PREFIX_GAME_LOG}:{player_id}:{season}")


async def set_game_log(player_id: int, season: str, data: Any) -> None:
    """Cache game log records with the standard game-log TTL."""
    await _set(f"{_PREFIX_GAME_LOG}:{player_id}:{season}", data, TTL_GAME_LOG)


async def invalidate_game_log(player_id: int, season: str) -> None:
    """Force-expire a game log entry (e.g. after background refresh)."""
    await _delete(f"{_PREFIX_GAME_LOG}:{player_id}:{season}")


async def get_season_averages(player_id: int, season: str) -> Any | None:
    """Return cached season averages or *None* on miss."""
    return await _get(f"{_PREFIX_SEASON_AVG}:{player_id}:{season}")


async def set_season_averages(player_id: int, season: str, data: Any) -> None:
    """Cache season averages with the standard averages TTL."""
    await _set(
        f"{_PREFIX_SEASON_AVG}:{player_id}:{season}",
        data,
        TTL_SEASON_AVERAGES,
    )


async def get_draft_class(season_year: int) -> Any | None:
    """Return cached draft class data or *None* on miss."""
    return await _get(f"{_PREFIX_DRAFT}:{season_year}")


async def set_draft_class(season_year: int, data: Any) -> None:
    """Cache draft class data (picks, rounds, team at draft time)."""
    await _set(f"{_PREFIX_DRAFT}:{season_year}", data, TTL_DRAFT)


async def get_player_bio(player_id: int) -> Any | None:
    """Return cached player bio or *None* on miss."""
    return await _get(f"{_PREFIX_BIO}:{player_id}")


async def set_player_bio(player_id: int, data: Any) -> None:
    """Cache player bio (height, weight, position, nationality, team)."""
    await _set(f"{_PREFIX_BIO}:{player_id}", data, TTL_BIO)


async def invalidate_player_bio(player_id: int) -> None:
    """Force-expire bio — used after a confirmed trade or roster move."""
    await _delete(f"{_PREFIX_BIO}:{player_id}")


async def get_scoreboard() -> Any | None:
    """Return cached season status dict or *None* on miss."""
    return await _get(f"{_PREFIX_SCOREBOARD}:current")


async def set_scoreboard(data: Any) -> None:
    """Cache the processed season status for one hour."""
    await _set(f"{_PREFIX_SCOREBOARD}:current", data, TTL_SCOREBOARD)
