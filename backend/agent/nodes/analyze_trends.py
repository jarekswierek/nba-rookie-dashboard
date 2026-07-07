"""Analyze rolling-window trends across the rookie's game log."""

from typing import Any

from backend.agent.state import AgentState


async def analyze_trends(state: AgentState) -> dict[str, Any]:
    """Return trend analysis derived from ``state['stats']``.

    Skeleton returns a marker so tests can assert the node fired; real logic
    replaces the marker with a typed trend summary.
    """
    return {"trend_analysis": {"_skeleton": True}}
