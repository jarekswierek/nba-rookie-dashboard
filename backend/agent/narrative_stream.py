"""Streaming narrative generation for the SSE endpoint.

Two LLM calls, both against Claude Haiku 4.5:

1. ``stream_summary`` — plain text, streamed token by token so the UI can
   render mid-generation. No structured output; validation is impossible
   until the stream ends.
2. ``generate_metadata`` — structured output. Runs after the summary is
   complete and classifies trend_direction and confidence against the
   same signals plus the freshly-written summary text.

Splitting the responsibilities lets us keep hard schema guarantees for
metadata (progress bar, badge) while still delivering real streaming to
the client. The alternative — streaming tokens through a tool call — hands
the client fragments of JSON, not prose.
"""

from collections.abc import AsyncIterator
from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate

from backend.agent.client import get_anthropic_client
from backend.agent.prompts.narrative import (
    HUMAN_TEMPLATE,
    METADATA_HUMAN_TEMPLATE,
    METADATA_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from backend.agent.state import AgentState
from shared.schemas.narrative import PlayerNarrativeMetadata
from shared.schemas.stats import AggregatedStats

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


def build_prompt_inputs(state: AgentState) -> dict[str, str]:
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


async def stream_summary(state: AgentState) -> AsyncIterator[str]:
    """Yield narrative tokens as Claude produces them."""
    inputs = build_prompt_inputs(state)
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_TEMPLATE)]
    )
    chain = prompt | get_anthropic_client()
    async for chunk in chain.astream(inputs):
        content = chunk.content
        if isinstance(content, str) and content:
            yield content


async def generate_metadata(
    state: AgentState, summary: str
) -> PlayerNarrativeMetadata:
    """Classify trend direction and confidence from state + finished summary."""
    inputs = build_prompt_inputs(state)
    inputs["summary"] = summary
    prompt = ChatPromptTemplate.from_messages(
        [("system", METADATA_SYSTEM_PROMPT), ("human", METADATA_HUMAN_TEMPLATE)]
    )
    llm = get_anthropic_client().with_structured_output(PlayerNarrativeMetadata)
    chain = prompt | llm
    return cast(PlayerNarrativeMetadata, await chain.ainvoke(inputs))
