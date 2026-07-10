"""Pydantic schemas for season status and draft year range."""

from pydantic import BaseModel


class SeasonStatus(BaseModel):
    season: str
    is_active: bool
    games_today: int
    status_label: str


class DraftYearRange(BaseModel):
    min_year: int
    max_year: int
    default_year: int
