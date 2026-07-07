"""Generate the natural-language narrative from trends and context."""

from typing import Any

from backend.agent.state import AgentState


async def generate_narrative(state: AgentState) -> dict[str, Any]:
    """Return the narrative string built from prior nodes' output.

    Skeleton returns a marker sentinel string so tests can assert the node fired;
    real logic calls Claude Haiku with structured output.
    """
    return {"narrative": "__skeleton__"}
