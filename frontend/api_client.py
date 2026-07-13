"""Typed HTTP client for the FastAPI backend.

Sync httpx client because Streamlit is single-threaded and rerun-based — async
would only add friction. The client is cached so we reuse one connection pool
across Streamlit reruns.
"""

import os
from collections.abc import Iterator
from functools import lru_cache

import httpx

from frontend.sse import SSEEvent, iter_sse_events
from shared.schemas.career import CareerStatsResponse
from shared.schemas.draft import DraftClass
from shared.schemas.season import DraftYearRange, SeasonStatus
from shared.schemas.season_averages import SeasonAveragesResponse
from shared.schemas.stats import AggregatedStatsResponse, GameLogsResponse

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


def get_aggregated_stats(player_id: int, season: str) -> AggregatedStatsResponse:
    """Return rolling windows and season aggregates for *player_id*."""
    response = _client().get(
        f"/api/players/{player_id}/aggregated-stats",
        params={"season": season},
    )
    response.raise_for_status()
    return AggregatedStatsResponse.model_validate(response.json())


def get_game_logs(player_id: int, season: str) -> GameLogsResponse:
    """Return per-game statistics for *player_id* in *season*."""
    response = _client().get(
        f"/api/players/{player_id}/game-logs",
        params={"season": season},
    )
    response.raise_for_status()
    return GameLogsResponse.model_validate(response.json())


def get_career_stats(player_id: int) -> CareerStatsResponse:
    """Return per-season career averages for *player_id*."""
    response = _client().get(f"/api/players/{player_id}/career-stats")
    response.raise_for_status()
    return CareerStatsResponse.model_validate(response.json())


def stream_narrative(
    player_id: int, season: str, draft_year: int
) -> Iterator[SSEEvent]:
    """Yield SSE events (token/metadata/warning/done) for the player's
    narrative."""
    return iter_sse_events(
        f"/api/players/{player_id}/narrative",
        params={"season": season, "draft_year": draft_year},
    )
