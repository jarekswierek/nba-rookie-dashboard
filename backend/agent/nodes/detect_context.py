"""Detect contextual events (gaps, streaks, role changes) around the trends."""

from typing import Any

from backend.agent.state import AgentState


async def detect_context_events(state: AgentState) -> dict[str, Any]:
    """Return the events that shape narrative framing.

    Skeleton returns an empty list — real logic populates events using
    ``state['gaps']`` and, eventually, external context sources.
    """
    return {"context_events": [{"_skeleton": True}]}
