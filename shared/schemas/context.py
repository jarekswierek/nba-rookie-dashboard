"""Context event schemas emitted by the detect_context_events node.

Tagged union of typed events lets mypy narrow the concrete type on
``event.type == ...`` and lets the narrative prompt loop consume ``display``
strings without knowing each variant's field shape.
"""

import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _ContextEventBase(BaseModel):
    model_config = ConfigDict(frozen=True)
    display: str


class ReturnFromAbsence(_ContextEventBase):
    type: Literal["return_from_absence"] = "return_from_absence"
    gap_length: int
    start_date: datetime.date
    end_date: datetime.date


class CurrentlyAbsent(_ContextEventBase):
    type: Literal["currently_absent"] = "currently_absent"
    games_missed: int
    since_date: datetime.date


class ExtendedAbsence(_ContextEventBase):
    type: Literal["extended_absence"] = "extended_absence"
    gap_length: int
    start_date: datetime.date
    end_date: datetime.date


ContextEvent = Annotated[
    ReturnFromAbsence | CurrentlyAbsent | ExtendedAbsence,
    Field(discriminator="type"),
]


class ContextEventList(BaseModel):
    model_config = ConfigDict(frozen=True)
    events: list[ContextEvent]
