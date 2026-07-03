"""Integration test: FastAPI health endpoint.

Uses TestClient — no real Docker needed, but does instantiate the full
FastAPI app (including settings validation).  Requires env vars to be
set (CI sets them via workflow env: block).
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return TestClient with the real app instance."""
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"


def test_health_returns_env(client: TestClient) -> None:
    data = client.get("/health").json()
    assert "env" in data
