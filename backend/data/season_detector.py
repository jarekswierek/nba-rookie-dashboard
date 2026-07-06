"""Current season detection from NBA scoreboard data."""

import datetime
from typing import Any

import pandas as pd


def season_string(year: int) -> str:
    """Return season string for the given draft/season year, e.g. 2024 →
    '2024-25'."""
    return f"{year}-{str(year + 1)[2:]}"


def current_season_year(today: datetime.date) -> int:
    """Return the calendar year the current NBA season started in.

    NBA seasons start in October. October–December of year X belongs to the
    X/(X+1) season, so we return X. January–September of year X belongs to the
    (X-1)/X season, so we return X-1.
    """
    return today.year if today.month >= 10 else today.year - 1


def detect_current_season(scoreboard_df: pd.DataFrame) -> dict[str, Any]:
    """Return a season status dict derived from today's scoreboard DataFrame.

    Args:
        scoreboard_df: First result-set DataFrame from ScoreboardV2 (one row
            per game scheduled today). Empty when there are no games today.

    Returns:
        Dict with keys: season, is_active, games_today, status_label.
    """
    today = datetime.date.today()
    season_year = current_season_year(today)
    season = season_string(season_year)

    # Season runs October through June (inclusive).
    is_active = today.month >= 10 or today.month <= 6

    games_today = len(scoreboard_df) if not scoreboard_df.empty else 0

    if is_active and games_today > 0:
        status_label = f"Season active · {games_today} games today"
    elif is_active:
        status_label = "Season active · no games today"
    else:
        status_label = "Off-season"

    return {
        "season": season,
        "is_active": is_active,
        "games_today": games_today,
        "status_label": status_label,
    }
