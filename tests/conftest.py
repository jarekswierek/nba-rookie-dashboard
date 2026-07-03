"""Shared pytest fixtures for integration tests.

Fixtures connect to real running services (Redis, PostgreSQL) from the
Docker Compose stack. Tests using these fixtures require ``make dev``.

Isolation strategy:
- ``redis_client``: flushes test Redis DB (index 1) before and after each
  test; also redirects the module-level singleton in ``cache_redis`` so that
  service-layer writes land in the same database as test assertions.
- ``pg_session``: wraps every test in a transaction that is rolled back on
  teardown — schema persists, no data leaks between tests.
"""

import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import backend.data.cache_redis as _cache_redis
from backend.core.config import get_settings

_settings = get_settings()

_DATABASE_URL = _settings.database_url
# Use Redis DB index 1 for tests to avoid colliding with the app's DB 0.
_REDIS_URL = _settings.redis_url.rstrip("/0") + "/1"


# ── Redis fixture ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def redis_client() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return a connected async Redis client pointed at the test database (DB 1).

    Flushes DB 1 on setup (clears stale keys from prior runs) and teardown.
    Also redirects the module-level ``_redis`` singleton in ``cache_redis``
    so that service-layer writes land in DB 1 alongside test assertions.
    """
    client: aioredis.Redis = aioredis.from_url(  # type: ignore[type-arg]
        _REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    await client.flushdb()

    _original = _cache_redis._redis
    _cache_redis._redis = client

    yield client

    _cache_redis._redis = _original
    await client.flushdb()
    await client.aclose()


# ── PostgreSQL session fixture ────────────────────────────────────────────

@pytest_asyncio.fixture
async def pg_session() -> AsyncSession:
    """Yield an ``AsyncSession`` that rolls back after each test.

    The session is bound to a single connection whose transaction is never
    committed — only rolled back on teardown. This keeps the schema intact
    while preventing data from leaking between tests.
    """
    engine = create_async_engine(_DATABASE_URL, pool_pre_ping=True)

    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(conn, expire_on_commit=False) as session:
            yield session
        await conn.rollback()

    await engine.dispose()
