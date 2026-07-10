"""Per-player season averages returned from league-wide leaderboard data."""

from pydantic import BaseModel


class PlayerSeasonAverage(BaseModel):
    """One row of season averages for a single player."""

    player_id: int
    full_name: str
    team_abbreviation: str | None
    games_played: int
    pts: float
    reb: float
    ast: float
    fg_pct: float
    fg3_pct: float


class SeasonAveragesResponse(BaseModel):
    season: str
    players: list[PlayerSeasonAverage]
