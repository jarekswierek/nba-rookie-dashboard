"""Smoke tests for the narrative graph wiring.

Verifies that all three nodes fire in order and their outputs land in
the final state. The LLM call in generate_narrative is mocked so the
suite runs without hitting Anthropic.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from backend.schemas.gaps import GapEvent
from backend.schemas.narrative import PlayerNarrative
from backend.schemas.stats import (
    AggregatedStats,
    PlayerProfile,
    RollingWindow,
    StatWindows,
)


def _empty_window() -> RollingWindow:
    return RollingWindow(
        window_size=5,
        avg=None,
        delta=None,
        direction="stable",
        games_played=0,
    )


def _empty_stat_windows() -> StatWindows:
    return StatWindows(
        w5=_empty_window(),
        w10=_empty_window(),
        w15=_empty_window(),
    )


@pytest.fixture
def sample_state() -> AgentState:
    profile = PlayerProfile(
        player_id=1,
        full_name="Test Rookie",
        position="G",
        height_cm=190.0,
        weight_kg=85.0,
        country="USA",
        team_abbreviation="NYK",
        team_at_draft="NYK",
        overall_pick=10,
        round_number=1,
        round_pick=10,
        draft_year=2024,
    )
    stats = AggregatedStats(
        player_id=1,
        season="2024-25",
        total_games=20,
        games_played=17,
        pts=_empty_stat_windows(),
        ast=_empty_stat_windows(),
        reb=_empty_stat_windows(),
        fg_pct=_empty_stat_windows(),
        fg3_pct=_empty_stat_windows(),
        min=_empty_stat_windows(),
        pts_season_avg=None,
        ast_season_avg=None,
        reb_season_avg=None,
        fg_pct_season_avg=None,
        fg3_pct_season_avg=None,
        min_season_avg=None,
    )
    gaps = [
        GapEvent(
            start_game_number=5,
            end_game_number=7,
            start_date=datetime.date(2025, 1, 5),
            end_date=datetime.date(2025, 1, 9),
        )
    ]
    return AgentState(
        player_id=1,
        season="2024-25",
        profile=profile,
        stats=stats,
        gaps=gaps,
    )


def _mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch generate_narrative's LLM chain to skip the real API call."""
    fake_narrative = PlayerNarrative(
        summary="Test Rookie is averaging modest numbers.",
        trend_direction="stable",
        confidence=0.5,
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=fake_narrative)
    mock_prompt = MagicMock()
    mock_prompt.__or__.return_value = mock_chain
    mock_prompt_cls = MagicMock()
    mock_prompt_cls.from_messages.return_value = mock_prompt
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock()
    monkeypatch.setattr(
        "backend.agent.nodes.generate_narrative.ChatPromptTemplate",
        mock_prompt_cls,
    )
    monkeypatch.setattr(
        "backend.agent.nodes.generate_narrative.get_anthropic_client",
        lambda: mock_llm,
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_graph_runs_all_three_nodes(
    sample_state: AgentState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All three nodes fire and each populates its expected slot in state."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    _mock_llm(monkeypatch)

    graph = build_graph()
    result = await graph.ainvoke(sample_state)

    assert result["trend_analysis"]["signals"] == []
    assert result["trend_analysis"]["has_significant_trends"] is False
    assert len(result["context_events"]) == 1
    assert result["context_events"][0]["type"] == "return_from_absence"
    narrative = result["narrative"]
    assert isinstance(narrative, dict)
    assert narrative["summary"].startswith("Test Rookie")
    assert narrative["trend_direction"] == "stable"


@pytest.mark.asyncio(loop_scope="function")
async def test_graph_preserves_input_fields(
    sample_state: AgentState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input state (profile, stats, gaps) passes through unchanged."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    _mock_llm(monkeypatch)

    graph = build_graph()
    result = await graph.ainvoke(sample_state)

    assert result["player_id"] == 1
    assert result["season"] == "2024-25"
    assert result["profile"].full_name == "Test Rookie"
    assert len(result["gaps"]) == 1
