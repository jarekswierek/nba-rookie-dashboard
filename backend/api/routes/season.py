"""Season status and draft year range endpoints."""

import datetime

from fastapi import APIRouter

from backend.data.season_detector import current_season_year
from backend.data.season_service import get_season_status
from backend.schemas.season import DraftYearRange, SeasonStatus

router = APIRouter()

_DRAFT_YEAR_MIN = 2000


@router.get("/current", response_model=SeasonStatus)
async def get_current_season() -> SeasonStatus:
    """Return the current NBA season status with today's game count."""
    return await get_season_status()


@router.get("/draft/years", response_model=DraftYearRange)
async def get_draft_years() -> DraftYearRange:
    """Return the allowed draft year range and the current default year."""
    today = datetime.date.today()
    return DraftYearRange(
        min_year=_DRAFT_YEAR_MIN,
        max_year=today.year,
        default_year=current_season_year(today),
    )
