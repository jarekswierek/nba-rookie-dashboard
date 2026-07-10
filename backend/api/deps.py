"""FastAPI dependency functions shared across routes."""

import datetime
from collections.abc import AsyncGenerator

from fastapi import HTTPException, Path
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import get_settings
from shared.consts import DRAFT_YEAR_MIN

_engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession with an auto-committed transaction per request."""

    async with _session_factory.begin() as session:
        yield session


async def valid_draft_year(
    year: int = Path(..., ge=DRAFT_YEAR_MIN),
) -> int:
    """Validate that *year* is within the allowed draft year range."""
    current_year = datetime.date.today().year
    if year > current_year:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Draft year {year} is in the future. "
                f"Valid range: {DRAFT_YEAR_MIN}–{current_year}."
            ),
        )
    return year
