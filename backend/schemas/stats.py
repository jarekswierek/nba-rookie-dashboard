"""Pydantic schemas for player statistics data."""

import datetime
from typing import Literal

from pydantic import BaseModel, computed_field


class PlayerProfile(BaseModel):
    player_id: int
    full_name: str
    position: str | None
    height_cm: float | None
    weight_kg: float | None
    country: str | None
    team_abbreviation: str | None
    team_at_draft: str | None
    overall_pick: int
    round_number: int
    round_pick: int
    draft_year: int


class GameLog(BaseModel):
    game_id: str
    game_date: datetime.date
    matchup: str
    game_number: int
    pts: float | None
    ast: float | None
    reb: float | None
    fg_pct: float | None
    fg3_pct: float | None
    min: float | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_dnp(self) -> bool:
        return self.min is None


class RollingWindow(BaseModel):
    window_size: int
    avg: float | None
    delta: float | None
    direction: Literal["up", "down", "stable"]
    games_played: int


class StatWindows(BaseModel):
    w5: RollingWindow
    w10: RollingWindow
    w15: RollingWindow


class AggregatedStats(BaseModel):
    player_id: int
    season: str
    total_games: int
    games_played: int

    pts: StatWindows
    ast: StatWindows
    reb: StatWindows
    fg_pct: StatWindows
    fg3_pct: StatWindows
    min: StatWindows

    pts_season_avg: float | None
    ast_season_avg: float | None
    reb_season_avg: float | None
    fg_pct_season_avg: float | None
    fg3_pct_season_avg: float | None
    min_season_avg: float | None


class GameLogsResponse(BaseModel):
    player_id: int
    season: str
    game_logs: list[GameLog]
    fetched_at: datetime.datetime | None


class AggregatedStatsResponse(BaseModel):
    stats: AggregatedStats
    fetched_at: datetime.datetime | None
