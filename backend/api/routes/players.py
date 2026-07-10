"""Player statistics endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db_session
from backend.data.aggregation_service import get_aggregated_stats
from backend.data.game_log_service import get_game_logs
from backend.data.gap_service import detect_gaps
from shared.consts import SEASON_PATTERN
from shared.schemas.stats import AggregatedStatsResponse, GameLogsResponse

router = APIRouter()


@router.get("/{player_id}/game-logs", response_model=GameLogsResponse)
async def get_player_game_logs(
    player_id: int = Path(..., gt=0),
    season: str = Query(..., pattern=SEASON_PATTERN),
    session: AsyncSession = Depends(get_db_session),
) -> GameLogsResponse:
    """Return game-by-game statistics for *player_id* in *season*."""
    logs, fetched_at = await get_game_logs(session, player_id, season)
    return GameLogsResponse(
        player_id=player_id,
        season=season,
        game_logs=logs,
        gaps=detect_gaps(logs),
        fetched_at=fetched_at,
    )


@router.get(
    "/{player_id}/aggregated-stats", response_model=AggregatedStatsResponse
)
async def get_player_aggregated_stats(
    player_id: int = Path(..., gt=0),
    season: str = Query(..., pattern=SEASON_PATTERN),
    session: AsyncSession = Depends(get_db_session),
) -> AggregatedStatsResponse:
    """Return rolling averages and season aggregates for *player_id*."""
    stats, fetched_at = await get_aggregated_stats(session, player_id, season)
    return AggregatedStatsResponse(stats=stats, fetched_at=fetched_at)
