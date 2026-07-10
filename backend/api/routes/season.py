"""Season status, draft year range, and league-wide averages endpoints."""

import datetime

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db_session
from backend.core.consts import DRAFT_YEAR_MIN, SEASON_PATTERN
from backend.data.season_averages_service import get_season_averages
from backend.data.season_detector import current_season_year
from backend.data.season_service import get_season_status
from backend.schemas.season import DraftYearRange, SeasonStatus
from backend.schemas.season_averages import SeasonAveragesResponse

router = APIRouter()


@router.get("/current", response_model=SeasonStatus)
async def get_current_season() -> SeasonStatus:
    """Return the current NBA season status with today's game count."""
    return await get_season_status()


@router.get("/draft/years", response_model=DraftYearRange)
async def get_draft_years() -> DraftYearRange:
    """Return the allowed draft year range and the current default year."""
    today = datetime.date.today()
    return DraftYearRange(
        min_year=DRAFT_YEAR_MIN,
        max_year=today.year,
        default_year=current_season_year(today),
    )


@router.get("/{season}/averages", response_model=SeasonAveragesResponse)
async def get_league_season_averages(
    season: str = Path(..., pattern=SEASON_PATTERN),
    session: AsyncSession = Depends(get_db_session),
) -> SeasonAveragesResponse:
    """Return league-wide per-player season averages for *season*."""
    return await get_season_averages(session, season)
