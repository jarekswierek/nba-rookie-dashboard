"""Turn AggregatedStats into ranked TrendSignals for the narrative prompt.

Assumes every tracked stat is "more is better" (pts/ast/reb/fg_pct/fg3_pct/min).
Adding a stat where up is bad (e.g. turnovers) would require inverting the
direction-to-goodness mapping when building ``display`` strings.
"""

from typing import Literal, cast

from backend.schemas.stats import AggregatedStats, RollingWindow, StatWindows
from backend.schemas.trends import TrendAnalysis, TrendSignal

_StatName = Literal["pts", "ast", "reb", "fg_pct", "fg3_pct", "min"]

# Order also drives tie-breaking in ranking — headline stats first.
_STAT_PRIORITY: tuple[_StatName, ...] = (
    "pts",
    "fg3_pct",
    "ast",
    "reb",
    "fg_pct",
    "min",
)

# Fraction of a window that must be filled before we trust the average.
# A rookie with 4 games in a "10-game window" is noise, not signal.
_MIN_WINDOW_FILL_RATIO = 0.6

# Per-stat strength thresholds.
# For counting stats (pts/ast/reb/min) the metric is ratio |delta| / season_avg.
# For percentages (fg_pct/fg3_pct) the metric is absolute percentage points,
# because a 25% relative move on a 35% shooter is unusually rare and would
# always classify as weak under a ratio rule.
_STRENGTH_THRESHOLDS: dict[_StatName, tuple[float, float]] = {
    "pts": (0.25, 0.10),
    "ast": (0.25, 0.10),
    "reb": (0.25, 0.10),
    "min": (0.20, 0.08),
    "fg_pct": (0.06, 0.03),  # absolute pp
    "fg3_pct": (0.06, 0.03),  # absolute pp
}

_DISPLAY_STAT_LABEL: dict[_StatName, str] = {
    "pts": "PTS",
    "ast": "AST",
    "reb": "REB",
    "fg_pct": "FG%",
    "fg3_pct": "3P%",
    "min": "MIN",
}


def _pick_window(
    stat_windows: StatWindows,
) -> tuple[Literal[5, 10, 15], RollingWindow] | None:
    """Return the longest window that meets the fill-ratio threshold."""
    for size, window in (
        (15, stat_windows.w15),
        (10, stat_windows.w10),
        (5, stat_windows.w5),
    ):
        if window.avg is None:
            continue
        if window.games_played >= size * _MIN_WINDOW_FILL_RATIO:
            return cast(Literal[5, 10, 15], size), window
    return None


def _classify_strength(
    stat: _StatName, delta: float, season_avg: float | None
) -> Literal["strong", "moderate", "weak"]:
    """Bucket delta size relative to per-stat calibration."""
    strong_threshold, moderate_threshold = _STRENGTH_THRESHOLDS[stat]

    if stat in ("fg_pct", "fg3_pct"):
        magnitude = abs(delta)
    else:
        if season_avg is None or season_avg == 0:
            return "weak"
        magnitude = abs(delta) / abs(season_avg)

    if magnitude >= strong_threshold:
        return "strong"
    if magnitude >= moderate_threshold:
        return "moderate"
    return "weak"


def _format_display(
    stat: _StatName, window: Literal[5, 10, 15], delta: float
) -> str:
    """Build the prompt-ready delta string, e.g. '+3.4 PTS last 10G'.

    Percentages are rendered as absolute percentage points (``+3.4pp``) to
    prevent the LLM from framing an absolute shift as a relative one.
    """
    label = _DISPLAY_STAT_LABEL[stat]
    if stat in ("fg_pct", "fg3_pct"):
        magnitude = f"{delta * 100:+.1f}pp"
    else:
        magnitude = f"{delta:+.1f}"
    return f"{magnitude} {label} last {window}G"


def _rank_key(signal: TrendSignal) -> tuple[int, float, int]:
    """Sort key: strongest first, then largest delta, then hardcoded priority."""
    strength_order = {"strong": 0, "moderate": 1, "weak": 2}
    priority = _STAT_PRIORITY.index(signal.stat)
    return strength_order[signal.strength], -abs(signal.delta), priority


def _build_signal(
    stat: _StatName,
    window: Literal[5, 10, 15],
    rolling: RollingWindow,
    season_avg: float | None,
) -> TrendSignal:
    delta = rolling.delta if rolling.delta is not None else 0.0
    strength = (
        _classify_strength(stat, delta, season_avg)
        if rolling.direction != "stable"
        else "weak"
    )
    return TrendSignal(
        stat=stat,
        window=window,
        direction=rolling.direction,
        delta=delta,
        strength=strength,
        display=_format_display(stat, window, delta),
        rank=0,
    )


def _summary(signals: list[TrendSignal]) -> str:
    if not signals:
        return "No games played yet"
    parts: list[str] = []
    for s in signals[:3]:
        arrow = {"up": "up", "down": "down", "stable": "steady"}[s.direction]
        parts.append(f"{_DISPLAY_STAT_LABEL[s.stat]} {arrow}")
    return ", ".join(parts)


def _stat_windows_for(stats: AggregatedStats, name: _StatName) -> StatWindows:
    return cast(StatWindows, getattr(stats, name))


def _season_avg_for(stats: AggregatedStats, name: _StatName) -> float | None:
    return cast("float | None", getattr(stats, f"{name}_season_avg"))


def analyze_trends(stats: AggregatedStats) -> TrendAnalysis:
    """Rank the player's rolling-window signals into a TrendAnalysis."""
    if stats.games_played == 0:
        return TrendAnalysis(
            signals=[],
            summary="No games played yet",
            has_significant_trends=False,
        )

    signals: list[TrendSignal] = []
    for stat_name in _STAT_PRIORITY:
        picked = _pick_window(_stat_windows_for(stats, stat_name))
        if picked is None:
            continue
        window_size, rolling = picked
        signals.append(
            _build_signal(
                stat_name,
                window_size,
                rolling,
                _season_avg_for(stats, stat_name),
            )
        )

    signals.sort(key=_rank_key)
    for idx, signal in enumerate(signals, start=1):
        signal.rank = idx

    return TrendAnalysis(
        signals=signals,
        summary=_summary(signals),
        has_significant_trends=any(s.direction != "stable" for s in signals),
    )
