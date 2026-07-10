"""Service layer for game-by-game player statistics."""

import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_service
from backend.data.models import PlayerGameLogs
from shared.schemas.stats import GameLog

logger = logging.getLogger(__name__)

_GAME_DATE_FORMAT = "%b %d, %Y"


def _parse_min(raw: Any) -> float | None:
    """Return None for DNP (None or 0 minutes), else the float value."""
    if raw is None:
        return None
    try:
        val = float(raw)
        return None if val == 0.0 else val
    except TypeError, ValueError:
        return None


def _parse_optional_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except TypeError, ValueError:
        return None


def _parse_game_date(raw: str) -> datetime.date:
    return datetime.datetime.strptime(raw, _GAME_DATE_FORMAT).date()


def _parse_records(records: list[dict[str, Any]]) -> list[GameLog]:
    """Return GameLog list sorted ascending by date with 1-based game_number.

    nba_api returns records newest-first; we reverse so game_number=1 is the
    season opener. DNP rows (MIN None or 0) have all stat fields set to None.
    """
    sorted_records = sorted(
        records,
        key=lambda r: datetime.datetime.strptime(
            str(r["GAME_DATE"]), _GAME_DATE_FORMAT
        ).date(),
    )

    game_logs: list[GameLog] = []
    for idx, record in enumerate(sorted_records, start=1):
        min_val = _parse_min(record.get("MIN"))
        is_dnp = min_val is None

        game_id = str(
            record.get("GAME_ID", f"{record['GAME_DATE']}_{record['MATCHUP']}")
        )

        game_logs.append(
            GameLog(
                game_id=game_id,
                game_date=_parse_game_date(str(record["GAME_DATE"])),
                matchup=str(record.get("MATCHUP", "")),
                game_number=idx,
                min=min_val,
                pts=None if is_dnp else _parse_optional_float(record.get("PTS")),
                ast=None if is_dnp else _parse_optional_float(record.get("AST")),
                reb=None if is_dnp else _parse_optional_float(record.get("REB")),
                fg_pct=(
                    None
                    if is_dnp
                    else _parse_optional_float(record.get("FG_PCT"))
                ),
                fg3_pct=(
                    None
                    if is_dnp
                    else _parse_optional_float(record.get("FG3_PCT"))
                ),
            )
        )

    return game_logs


async def _get_fetched_at(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> datetime.datetime | None:
    result = await session.execute(
        select(PlayerGameLogs.fetched_at).where(
            PlayerGameLogs.player_id == player_id,
            PlayerGameLogs.season == season,
        )
    )
    return result.scalar_one_or_none()


async def get_game_logs(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> tuple[list[GameLog], datetime.datetime | None]:
    """Return parsed game logs and fetch timestamp for *player_id* in
    *season*."""
    data = await cache_service.get_game_log(session, player_id, season)
    records: list[dict[str, Any]] = data.get("records", [])

    game_logs = _parse_records(records)
    fetched_at = await _get_fetched_at(session, player_id, season)

    return game_logs, fetched_at
