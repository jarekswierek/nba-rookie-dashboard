"""Pydantic schemas for draft class data."""

from pydantic import BaseModel, computed_field


class DraftPlayer(BaseModel):
    player_id: int
    full_name: str
    team_abbreviation: str | None
    team_at_draft: str | None
    overall_pick: int
    round_number: int
    round_pick: int
    position: str | None
    height_cm: float | None
    weight_kg: float | None
    country: str | None


class DraftClass(BaseModel):
    season_year: int
    season: str
    players: list[DraftPlayer]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def round_1(self) -> list[DraftPlayer]:
        return [p for p in self.players if p.round_number == 1]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def round_2(self) -> list[DraftPlayer]:
        return [p for p in self.players if p.round_number == 2]
