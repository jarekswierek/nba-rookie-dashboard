"""Per-season career statistics for a single player."""

from pydantic import BaseModel


class CareerSeasonRow(BaseModel):
    """Stats for one regular season."""

    season: str
    season_label: str
    team_abbreviation: str | None
    games_played: int
    pts: float
    reb: float
    ast: float


class CareerStatsResponse(BaseModel):
    player_id: int
    seasons: list[CareerSeasonRow]
    career_avg_total: float
