"""Validation-only tests for the /api/players/{id}/narrative endpoint.

Only exercises FastAPI input constraints — no DB, no LLM, no Docker.
Full data-path integration will follow once the streaming plumbing has a
stable enough shape to justify the harness cost.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

_SEASON = "2024-25"
_PLAYER_ID = 9999801


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestNarrativeValidation:
    def test_invalid_season_format_returns_422(self, client: TestClient) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/narrative",
            params={"season": "abc", "draft_year": 2024},
        )
        assert response.status_code == 422

    def test_invalid_player_id_returns_422(self, client: TestClient) -> None:
        response = client.get(
            "/api/players/0/narrative",
            params={"season": _SEASON, "draft_year": 2024},
        )
        assert response.status_code == 422

    def test_missing_draft_year_returns_422(self, client: TestClient) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/narrative",
            params={"season": _SEASON},
        )
        assert response.status_code == 422

    def test_draft_year_below_range_returns_422(
        self, client: TestClient
    ) -> None:
        response = client.get(
            f"/api/players/{_PLAYER_ID}/narrative",
            params={"season": _SEASON, "draft_year": 1999},
        )
        assert response.status_code == 422
