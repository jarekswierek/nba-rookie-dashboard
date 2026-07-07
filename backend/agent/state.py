"""Shared state schema for the narrative-generation graph.

Input fields (profile, stats, gaps) are populated by the caller before
``graph.ainvoke()``; nodes are pure transformations that read them and produce
the NotRequired output fields. I/O stays at the edges — DB and API calls live in
the endpoint, not in nodes.
"""

from typing import Any, NotRequired, TypedDict

from backend.schemas.gaps import GapEvent
from backend.schemas.stats import AggregatedStats, PlayerProfile


class AgentState(TypedDict):
    player_id: int
    season: str
    profile: PlayerProfile
    stats: AggregatedStats
    gaps: list[GapEvent]

    trend_analysis: NotRequired[dict[str, Any] | None]
    context_events: NotRequired[list[dict[str, Any]] | None]
    narrative: NotRequired[str | None]
