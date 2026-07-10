"""Type aliases shared across backend modules.

Domain-specific ``Literal`` sets that repeat across schemas and services live
here so mypy stays consistent and adding a value means editing one line. Single-
purpose enums (config env, tagged-union discriminators) stay where they are used.
"""

from typing import Literal

TrendDirection = Literal["up", "down", "stable"]
"""Direction of a rolling-window trend or a narrative summary."""

StatName = Literal["pts", "ast", "reb", "fg_pct", "fg3_pct", "min"]
"""Tracked box-score statistic.

All are "more is better" today.
"""

WindowSize = Literal[5, 10, 15]
"""Supported rolling-window sizes in games."""

TrendStrength = Literal["strong", "moderate", "weak"]
"""Categorical magnitude classification for a single trend signal."""
