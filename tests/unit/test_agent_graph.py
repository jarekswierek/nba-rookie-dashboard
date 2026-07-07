"""Smoke tests for the narrative graph skeleton.

Verifies wiring: all three nodes fire and their placeholder markers land
in the final state. Real behaviour ships in later tasks — this suite
only guards the shape of the pipeline.
"""

import datetime

import pytest

from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from backend.schemas.gaps import GapEvent
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
        total_games=0,
        games_played=0,
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


@pytest.mark.asyncio(loop_scope="function")
async def test_graph_runs_all_three_nodes(
    sample_state: AgentState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All three nodes fire and their skeleton markers appear in final state."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    graph = build_graph()
    result = await graph.ainvoke(sample_state)

    assert result["trend_analysis"] == {"_skeleton": True}
    assert result["context_events"] == [{"_skeleton": True}]
    assert result["narrative"] == "__skeleton__"


@pytest.mark.asyncio(loop_scope="function")
async def test_graph_preserves_input_fields(
    sample_state: AgentState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input state (profile, stats, gaps) passes through unchanged."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    graph = build_graph()
    result = await graph.ainvoke(sample_state)

    assert result["player_id"] == 1
    assert result["season"] == "2024-25"
    assert result["profile"].full_name == "Test Rookie"
    assert len(result["gaps"]) == 1
