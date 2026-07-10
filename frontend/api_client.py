"""Typed HTTP client for the FastAPI backend.

Sync httpx client because Streamlit is single-threaded and rerun-based — async
would only add friction. The client is cached so we reuse one connection pool
across Streamlit reruns.
"""

import os
from functools import lru_cache

import httpx

from backend.schemas.draft import DraftClass
from backend.schemas.season import DraftYearRange, SeasonStatus
from backend.schemas.season_averages import SeasonAveragesResponse

# Base URL of the FastAPI backend. Defaults to the Docker Compose service
# name; override via env for host-network dev or a deployed backend.
_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

_CONNECT_TIMEOUT_SECONDS = 5.0
_POOL_TIMEOUT_SECONDS = 5.0
_READ_TIMEOUT_SECONDS = 30.0
_WRITE_TIMEOUT_SECONDS = 30.0


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    """Return the shared httpx.Client, created lazily on first call."""
    return httpx.Client(
        base_url=_BASE_URL,
        timeout=httpx.Timeout(
            connect=_CONNECT_TIMEOUT_SECONDS,
            read=_READ_TIMEOUT_SECONDS,
            write=_WRITE_TIMEOUT_SECONDS,
            pool=_POOL_TIMEOUT_SECONDS,
        ),
    )


def get_season_status() -> SeasonStatus:
    """Return current NBA season status (active flag, games today, label)."""
    response = _client().get("/api/season/current")
    response.raise_for_status()
    return SeasonStatus.model_validate(response.json())


def get_draft_year_range() -> DraftYearRange:
    """Return the allowed draft year range and the current default year."""
    response = _client().get("/api/season/draft/years")
    response.raise_for_status()
    return DraftYearRange.model_validate(response.json())


def get_draft_class(year: int) -> DraftClass:
    """Return the full draft class for *year* with bio and current team data."""
    response = _client().get(f"/api/draft/{year}/players")
    response.raise_for_status()
    return DraftClass.model_validate(response.json())


def get_season_averages(season: str) -> SeasonAveragesResponse:
    """Return league-wide per-player season averages for *season*."""
    response = _client().get(f"/api/season/{season}/averages")
    response.raise_for_status()
    return SeasonAveragesResponse.model_validate(response.json())
