"""Integration tests for the /api/players endpoints.

Validation classes use a synchronous TestClient and require no running
services — they cover FastAPI input constraints only.

Data-path classes require the full Docker Compose stack (PostgreSQL +
Redis). The nba_api layer is patched for determinism.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db_session
from backend.main import app

_SEASON = "2024-25"
_PLAYER_ID = 9999801

_FAKE_GAME_LOG_DF = pd.DataFrame(
    [
        {
            "GAME_ID": "0022400002",
            "GAME_DATE": "Jan 15, 2025",
            "MATCHUP": "NYK vs BOS",
            "MIN": 32,
            "PTS": 24,
            "REB": 5,
            "AST": 3,
            "FG_PCT": 0.511,
            "FG3_PCT": 0.400,
        },
        {
            "GAME_ID": "0022400001",
            "GAME_DATE": "Jan 12, 2025",
            "MATCHUP": "NYK vs MIA",
            "MIN": 28,
            "PTS": 18,
            "REB": 4,
            "AST": 5,
            "FG_PCT": 0.444,
            "FG3_PCT": 0.333,
        },
    ]
)


@pytest_asyncio.fixture
async def async_client(
    pg_session: AsyncSession,
    redis_client: aioredis.Redis,  # type: ignore[type-arg]
) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield pg_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestGameLogsValidation:
    """Input validation tests — no Docker stack required."""

    def test_invalid_season_format_returns_422(self, client: TestClient) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/game-logs",
            params={"season": "2024"},
        )
        assert response.status_code == 422

    def test_invalid_player_id_returns_422(self, client: TestClient) -> None:
        response = client.get(
            "/api/players/0/game-logs",
            params={"season": _SEASON},
        )
        assert response.status_code == 422

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        response = client.get(f"/api/players/{_PLAYER_ID}/game-logs")
        assert response.status_code == 422


class TestAggregatedStatsValidation:
    """Input validation tests for the aggregated-stats endpoint."""

    def test_invalid_season_format_returns_422(self, client: TestClient) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/aggregated-stats",
            params={"season": "abc"},
        )
        assert response.status_code == 422

    def test_invalid_player_id_returns_422(self, client: TestClient) -> None:
        response = client.get(
            "/api/players/0/aggregated-stats",
            params={"season": _SEASON},
        )
        assert response.status_code == 422

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/aggregated-stats"
        )
        assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
class TestGameLogsEndpoint:
    """Full data-path tests — requires Docker Compose stack."""

    async def test_returns_200_with_game_logs(
        self, async_client: AsyncClient
    ) -> None:
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            response = await async_client.get(
                f"/api/players/{_PLAYER_ID}/game-logs",
                params={"season": _SEASON},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["player_id"] == _PLAYER_ID
        assert data["season"] == _SEASON
        assert len(data["game_logs"]) == 2
        assert data["gaps"] == []

    async def test_game_logs_sorted_ascending(
        self, async_client: AsyncClient
    ) -> None:
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            response = await async_client.get(
                f"/api/players/{_PLAYER_ID}/game-logs",
                params={"season": _SEASON},
            )

        logs = response.json()["game_logs"]
        assert logs[0]["game_number"] == 1
        assert logs[0]["game_date"] == "2025-01-12"
        assert logs[1]["game_number"] == 2
        assert logs[1]["game_date"] == "2025-01-15"

    async def test_fetched_at_present_in_response(
        self, async_client: AsyncClient
    ) -> None:
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            response = await async_client.get(
                f"/api/players/{_PLAYER_ID}/game-logs",
                params={"season": _SEASON},
            )

        assert response.json()["fetched_at"] is not None


@pytest.mark.asyncio(loop_scope="session")
class TestAggregatedStatsEndpoint:
    """Full data-path tests for aggregated-stats — requires Docker stack."""

    async def test_returns_200_with_stats_shape(
        self, async_client: AsyncClient
    ) -> None:
        with patch(
            "backend.data.cache_service.nba_client.fetch_game_log",
            new=AsyncMock(return_value=_FAKE_GAME_LOG_DF),
        ):
            response = await async_client.get(
                f"/api/players/{_PLAYER_ID}/aggregated-stats",
                params={"season": _SEASON},
            )

        assert response.status_code == 200
        body = response.json()
        stats = body["stats"]
        assert stats["player_id"] == _PLAYER_ID
        assert stats["season"] == _SEASON
        assert stats["total_games"] == 2
        assert stats["games_played"] == 2
        # 2 games < 5 → all windows empty but shape present
        assert stats["pts"]["w5"]["avg"] is None
        assert stats["pts"]["w5"]["direction"] == "stable"
        assert stats["pts"]["w5"]["games_played"] == 2
        # Season average is populated from the 2 played games
        assert stats["pts_season_avg"] == pytest.approx(21.0)
        assert body["fetched_at"] is not None
