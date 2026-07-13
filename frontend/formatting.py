"""Value and delta formatters for Streamlit displays.

Keeps the formatting rules in one place so PTS/REB/AST/MIN and the two percentage
stats (FG%, 3P%) render consistently across sidebar and main views. Percentage
deltas are rendered as ``pp`` (percentage points) rather than ``%`` to avoid the
classic relative-vs-absolute misinterpretation (a shift from 45% to 48% is +3 pp,
not +3%).
"""

_MISSING_PLACEHOLDER = "—"


def season_string(year: int) -> str:
    """Return NBA season label for a draft/season year (2024 -> '2024-25')."""
    return f"{year}-{str(year + 1)[-2:]}"


def fmt_value(value: float | None, *, decimals: int = 1) -> str:
    """Format a counting-stat season average; empty state renders as '—'."""
    if value is None:
        return _MISSING_PLACEHOLDER
    return f"{value:.{decimals}f}"


def fmt_delta(value: float | None, *, decimals: int = 1) -> str | None:
    """Format a counting-stat delta with an explicit sign, or None to hide."""
    if value is None:
        return None
    return f"{value:+.{decimals}f}"


def fmt_pct_value(value: float | None, *, decimals: int = 1) -> str:
    """Format a 0.0-1.0 percentage as 'XX.X%'; empty state renders as '—'."""
    if value is None:
        return _MISSING_PLACEHOLDER
    return f"{value * 100:.{decimals}f}%"


def fmt_pct_delta(value: float | None, *, decimals: int = 1) -> str | None:
    """Format a 0.0-1.0 percentage delta as '+X.X pp' (percentage points)."""
    if value is None:
        return None
    return f"{value * 100:+.{decimals}f} pp"
