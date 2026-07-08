"""Assemble AgentState from the data services.

Kept outside ``graph.py`` so the compiled graph stays a pure logic artifact —
batch jobs, tests, and the SSE endpoint can all build state here without pulling
in LangGraph.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.state import AgentState
from backend.data.aggregation_service import get_aggregated_stats
from backend.data.game_log_service import get_game_logs
from backend.data.gap_service import detect_gaps
from backend.data.player_service import get_player_profile


async def build_agent_state(
    session: AsyncSession,
    player_id: int,
    season: str,
    draft_year: int,
) -> AgentState:
    """Fetch profile + stats + gaps and package them as AgentState."""
    profile = await get_player_profile(session, player_id, draft_year)
    logs, _ = await get_game_logs(session, player_id, season)
    stats, _ = await get_aggregated_stats(session, player_id, season)
    gaps = detect_gaps(logs)

    return AgentState(
        player_id=player_id,
        season=season,
        profile=profile,
        stats=stats,
        gaps=gaps,
    )
