"""Rolling averages and season aggregates over player game logs.

Pure ``aggregate_stats`` runs the maths; async ``get_aggregated_stats`` wraps the
cache fetch. Windows are computed over PLAYED games only, so "last 5" means five
most recent appearances, not five calendar games. Delta compares the last N to
the previous N; ``direction`` applies a per-stat dead-band to ignore single-game
noise.
"""

import datetime
import logging
from statistics import fmean

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.types import TrendDirection
from backend.data.game_log_service import get_game_logs
from backend.schemas.stats import (
    AggregatedStats,
    GameLog,
    RollingWindow,
    StatWindows,
)

logger = logging.getLogger(__name__)

# Per-statistic dead-band for direction. Delta magnitudes at or below the
# threshold are reported as "stable" — small swings from a single hot or
# cold game should not flip a trend indicator.
_DELTA_THRESHOLDS: dict[str, float] = {
    "pts": 1.0,
    "ast": 0.5,
    "reb": 0.5,
    "fg_pct": 0.02,
    "fg3_pct": 0.02,
    "min": 1.0,
}


def _compute_direction(delta: float | None, stat_name: str) -> TrendDirection:
    """Classify *delta* against the per-stat dead-band.

    A missing delta reports "stable"; dead-band absorbs single-game noise that
    would otherwise flip the trend.
    """
    if delta is None:
        return "stable"
    threshold = _DELTA_THRESHOLDS[stat_name]
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "stable"


def _stat_values(played: list[GameLog], stat_name: str) -> list[float]:
    """Return non-None values for *stat_name* across played games, in order.

    Values may be None even outside DNPs (e.g. ``fg3_pct`` when no threes were
    attempted), so ``games_played`` is per-stat, not per-player.
    """
    return [
        value for g in played if (value := getattr(g, stat_name)) is not None
    ]


def _rolling_window(
    values: list[float], window_size: int, stat_name: str
) -> RollingWindow:
    """Build a RollingWindow over the trailing *window_size* values.

    Values must be non-None and ordered oldest-first. Missing avg stays None
    (never 0.0) so downstream trend analysis does not mistake insufficient sample
    for decline.
    """
    if len(values) < window_size:
        return RollingWindow(
            window_size=window_size,
            avg=None,
            delta=None,
            direction="stable",
            games_played=len(values),
        )

    last = values[-window_size:]
    avg = fmean(last)

    if len(values) < 2 * window_size:
        return RollingWindow(
            window_size=window_size,
            avg=avg,
            delta=None,
            direction="stable",
            games_played=window_size,
        )

    prev = values[-2 * window_size : -window_size]
    delta = avg - fmean(prev)
    return RollingWindow(
        window_size=window_size,
        avg=avg,
        delta=delta,
        direction=_compute_direction(delta, stat_name),
        games_played=window_size,
    )


def _stat_windows(played: list[GameLog], stat_name: str) -> StatWindows:
    """Build all three rolling windows (5/10/15) for one statistic."""
    values = _stat_values(played, stat_name)
    return StatWindows(
        w5=_rolling_window(values, 5, stat_name),
        w10=_rolling_window(values, 10, stat_name),
        w15=_rolling_window(values, 15, stat_name),
    )


def _season_avg(played: list[GameLog], stat_name: str) -> float | None:
    """Return the season-wide mean, or None when no value is available."""
    values = _stat_values(played, stat_name)
    return fmean(values) if values else None


def aggregate_stats(
    game_logs: list[GameLog], player_id: int, season: str
) -> AggregatedStats:
    """Compute rolling windows and season averages from parsed game logs.

    Pure function — safe to call from a LangGraph node. Input must be sorted
    ascending by game_number; DNP entries are filtered here once.
    """
    played = [g for g in game_logs if not g.is_dnp]

    return AggregatedStats(
        player_id=player_id,
        season=season,
        total_games=len(game_logs),
        games_played=len(played),
        pts=_stat_windows(played, "pts"),
        ast=_stat_windows(played, "ast"),
        reb=_stat_windows(played, "reb"),
        fg_pct=_stat_windows(played, "fg_pct"),
        fg3_pct=_stat_windows(played, "fg3_pct"),
        min=_stat_windows(played, "min"),
        pts_season_avg=_season_avg(played, "pts"),
        ast_season_avg=_season_avg(played, "ast"),
        reb_season_avg=_season_avg(played, "reb"),
        fg_pct_season_avg=_season_avg(played, "fg_pct"),
        fg3_pct_season_avg=_season_avg(played, "fg3_pct"),
        min_season_avg=_season_avg(played, "min"),
    )


async def get_aggregated_stats(
    session: AsyncSession,
    player_id: int,
    season: str,
) -> tuple[AggregatedStats, datetime.datetime | None]:
    """Return aggregated stats and the source game-log fetch timestamp.

    Aggregates are computed on read (deterministic from cached logs), so
    ``fetched_at`` reflects the source data age, not compute time.
    """
    logs, fetched_at = await get_game_logs(session, player_id, season)
    stats = aggregate_stats(logs, player_id, season)
    return stats, fetched_at
