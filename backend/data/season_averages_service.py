"""Service layer for league-wide season averages."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_service
from backend.schemas.season_averages import (
    PlayerSeasonAverage,
    SeasonAveragesResponse,
)


def _parse_record(record: dict[str, Any]) -> PlayerSeasonAverage:
    return PlayerSeasonAverage(
        player_id=int(record["PLAYER_ID"]),
        full_name=str(record.get("PLAYER_NAME", "")),
        team_abbreviation=str(record.get("TEAM_ABBREVIATION", "")) or None,
        games_played=int(record.get("GP", 0)),
        pts=float(record.get("PTS", 0.0)),
        reb=float(record.get("REB", 0.0)),
        ast=float(record.get("AST", 0.0)),
        fg_pct=float(record.get("FG_PCT", 0.0)),
        fg3_pct=float(record.get("FG3_PCT", 0.0)),
    )


async def get_season_averages(
    session: AsyncSession, season: str
) -> SeasonAveragesResponse:
    """Return league-wide season averages for *season* as typed response."""
    data = await cache_service.get_season_averages(session, season)
    records: list[dict[str, Any]] = data.get("records", [])
    return SeasonAveragesResponse(
        season=season,
        players=[_parse_record(r) for r in records],
    )
