"""DNP gap event schema.

Separate from ``stats.py`` because gaps describe context events (absences,
returns), not numerical statistics.
"""

import datetime

from pydantic import BaseModel, computed_field


class GapEvent(BaseModel):
    start_game_number: int
    end_game_number: int
    start_date: datetime.date
    end_date: datetime.date

    @computed_field  # type: ignore[prop-decorator]
    @property
    def length(self) -> int:
        return self.end_game_number - self.start_game_number + 1
