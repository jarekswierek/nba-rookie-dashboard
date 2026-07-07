"""Detect DNP gaps (absence spans) from game logs.

Pure ``detect_gaps`` runs the run-length encoding; async ``get_gaps`` wraps the
cache fetch. Cause classification (injury vs debut delay vs rest) belongs to the
narrative layer with access to draft dates and roster events — not here.
"""

import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.game_log_service import get_game_logs
from backend.schemas.gaps import GapEvent
from backend.schemas.stats import GameLog

logger = logging.getLogger(__name__)


def _build_gap(logs: list[GameLog], start_idx: int, end_idx: int) -> GapEvent:
    return GapEvent(
        start_game_number=logs[start_idx].game_number,
        end_game_number=logs[end_idx].game_number,
        start_date=logs[start_idx].game_date,
        end_date=logs[end_idx].game_date,
    )


def detect_gaps(game_logs: list[GameLog], min_length: int = 1) -> list[GapEvent]:
    """Return DNP runs as GapEvents, filtered by *min_length*.

    Logs must be sorted ascending by game_number — a loud ValueError beats silent
    wrong results when the invariant is broken upstream.
    """
    for i in range(len(game_logs) - 1):
        if game_logs[i].game_number > game_logs[i + 1].game_number:
            raise ValueError("game_logs must be sorted ascending by game_number")

    gaps: list[GapEvent] = []
    run_start: int | None = None

    for i, log in enumerate(game_logs):
        if log.is_dnp and run_start is None:
            run_start = i
        elif not log.is_dnp and run_start is not None:
            gaps.append(_build_gap(game_logs, run_start, i - 1))
            run_start = None

    if run_start is not None:
        gaps.append(_build_gap(game_logs, run_start, len(game_logs) - 1))

    return [g for g in gaps if g.length >= min_length]


async def get_gaps(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> tuple[list[GapEvent], datetime.datetime | None]:
    """Return detected gaps and the source game-log fetch timestamp."""
    logs, fetched_at = await get_game_logs(session, player_id, season)
    return detect_gaps(logs), fetched_at
