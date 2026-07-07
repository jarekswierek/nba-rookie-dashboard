"""Generate the 2-3 sentence player narrative via Claude Haiku."""

from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate

from backend.agent.client import get_anthropic_client
from backend.agent.prompts.narrative import HUMAN_TEMPLATE, SYSTEM_PROMPT
from backend.agent.state import AgentState
from backend.schemas.narrative import PlayerNarrative
from backend.schemas.stats import AggregatedStats

_STAT_LABELS: dict[str, str] = {
    "pts": "PTS",
    "ast": "AST",
    "reb": "REB",
    "fg_pct": "FG%",
    "fg3_pct": "3P%",
    "min": "MIN",
}


def _format_season_average(stat: str, value: float | None) -> str | None:
    if value is None:
        return None
    label = _STAT_LABELS[stat]
    if stat in ("fg_pct", "fg3_pct"):
        return f"- {label}: {value * 100:.1f}%"
    return f"- {label}: {value:.1f}"


def _stats_lines(stats: AggregatedStats) -> str:
    lines = [
        line
        for stat in ("pts", "ast", "reb", "fg_pct", "fg3_pct", "min")
        if (
            line := _format_season_average(
                stat, getattr(stats, f"{stat}_season_avg")
            )
        )
        is not None
    ]
    return "\n".join(lines) if lines else "- (no averages available)"


def _trend_lines(trend_analysis: dict[str, Any] | None) -> str:
    if not trend_analysis:
        return "- (no significant trends detected)"
    signals = trend_analysis.get("signals", [])
    non_stable = [s for s in signals if s.get("direction") != "stable"]
    if not non_stable:
        return "- (no significant trends detected)"
    return "\n".join(
        f"- {s['display']} ({s['strength']})" for s in non_stable[:5]
    )


def _context_lines(events: list[dict[str, Any]] | None) -> str:
    if not events:
        return "- (no notable context events)"
    return "\n".join(f"- {ev['display']}" for ev in events[:3])


def _build_prompt_inputs(state: AgentState) -> dict[str, str]:
    """Compose human-message variables from state — pure, no I/O."""
    profile = state["profile"]
    stats = state["stats"]
    trend = state.get("trend_analysis")
    events = state.get("context_events")

    trend_summary = (
        trend["summary"] if trend and trend.get("summary") else "no data"
    )

    return {
        "full_name": profile.full_name,
        "position": profile.position or "N/A",
        "season": state["season"],
        "games_played": str(stats.games_played),
        "stats_lines": _stats_lines(stats),
        "trend_lines": _trend_lines(trend),
        "context_lines": _context_lines(events),
        "trend_summary": trend_summary,
    }


def _no_games_narrative(full_name: str) -> PlayerNarrative:
    return PlayerNarrative(
        summary=f"{full_name} has not played any games this season.",
        trend_direction="stable",
        confidence=0.0,
    )


async def generate_narrative(state: AgentState) -> dict[str, Any]:
    """Return a PlayerNarrative for the current player as a serialised dict.

    Skips the LLM call when ``games_played == 0`` — a deterministic edge case
    shouldn't cost latency, tokens, or LangSmith noise.
    """
    if state["stats"].games_played == 0:
        narrative = _no_games_narrative(state["profile"].full_name)
        return {"narrative": narrative.model_dump()}

    inputs = _build_prompt_inputs(state)
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_TEMPLATE)]
    )
    llm = get_anthropic_client().with_structured_output(PlayerNarrative)
    chain = prompt | llm

    narrative = cast(PlayerNarrative, await chain.ainvoke(inputs))
    return {"narrative": narrative.model_dump()}
