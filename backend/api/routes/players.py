"""Player statistics endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db_session
from backend.data.game_log_service import get_game_logs
from backend.schemas.stats import GameLogsResponse

router = APIRouter()


@router.get("/{player_id}/game-logs", response_model=GameLogsResponse)
async def get_player_game_logs(
    player_id: int = Path(..., gt=0),
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    session: AsyncSession = Depends(get_db_session),
) -> GameLogsResponse:
    """Return game-by-game statistics for *player_id* in *season*."""
    logs, fetched_at = await get_game_logs(session, player_id, season)
    return GameLogsResponse(
        player_id=player_id,
        season=season,
        game_logs=logs,
        fetched_at=fetched_at,
    )
