"""Draft class endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db_session, valid_draft_year
from backend.data.draft_service import get_draft_class_with_bio
from shared.schemas.draft import DraftClass

router = APIRouter()


@router.get("/{year}/players", response_model=DraftClass)
async def get_draft_players(
    year: int = Depends(valid_draft_year),
    session: AsyncSession = Depends(get_db_session),
) -> DraftClass:
    """Return the full draft class for *year* with current team and bio data."""
    return await get_draft_class_with_bio(session, year)
