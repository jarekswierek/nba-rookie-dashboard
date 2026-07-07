"""Trend signal schemas produced by the analyze_trends node."""

from typing import Literal

from pydantic import BaseModel


class TrendSignal(BaseModel):
    """One trend on one stat over one rolling window, ready for prompting."""

    stat: Literal["pts", "ast", "reb", "fg_pct", "fg3_pct", "min"]
    window: Literal[5, 10, 15]
    direction: Literal["up", "down", "stable"]
    delta: float
    strength: Literal["strong", "moderate", "weak"]
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
