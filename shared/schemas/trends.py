"""Trend signal schemas produced by the analyze_trends node."""

from pydantic import BaseModel

from shared.types import (
    StatName,
    TrendDirection,
    TrendStrength,
    WindowSize,
)


class TrendSignal(BaseModel):
    """One trend on one stat over one rolling window, ready for prompting."""

    stat: StatName
    window: WindowSize
    direction: TrendDirection
    delta: float
    strength: TrendStrength
    display: str
    rank: int


class TrendAnalysis(BaseModel):
    """Ranked trend signals plus a headline summary.

    ``has_significant_trends`` lets the narrative node switch tone between
    "consistent performance" and trend-driven prose without re-scanning the
    signal list.
    """

    signals: list[TrendSignal]
    summary: str
    has_significant_trends: bool
