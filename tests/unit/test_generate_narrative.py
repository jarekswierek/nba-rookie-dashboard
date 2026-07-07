"""Unit tests for generate_narrative node.

Split into three layers:
- _build_prompt_inputs — pure prompt composition
- generate_narrative happy path — mocked LLM
- generate_narrative guard — no-games short-circuit
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agent.nodes.generate_narrative import (
    _build_prompt_inputs,
    generate_narrative,
)
from backend.agent.state import AgentState
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
        w5=_empty_window(), w10=_empty_window(), w15=_empty_window()
    )


def _profile() -> PlayerProfile:
    return PlayerProfile(
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


def _stats(games_played: int) -> AggregatedStats:
    return AggregatedStats(
        player_id=1,
        season="2024-25",
        total_games=games_played,
        games_played=games_played,
        pts=_empty_stat_windows(),
        ast=_empty_stat_windows(),
        reb=_empty_stat_windows(),
        fg_pct=_empty_stat_windows(),
        fg3_pct=_empty_stat_windows(),
        min=_empty_stat_windows(),
        pts_season_avg=22.5 if games_played else None,
        ast_season_avg=4.2 if games_played else None,
        reb_season_avg=5.1 if games_played else None,
        fg_pct_season_avg=0.45 if games_played else None,
        fg3_pct_season_avg=0.36 if games_played else None,
        min_season_avg=28.4 if games_played else None,
    )


def _state(
    *,
    games_played: int = 20,
    trend_analysis: dict[str, Any] | None = None,
    context_events: list[dict[str, Any]] | None = None,
) -> AgentState:
    state: AgentState = {
        "player_id": 1,
        "season": "2024-25",
        "profile": _profile(),
        "stats": _stats(games_played=games_played),
        "gaps": [],
    }
    if trend_analysis is not None:
        state["trend_analysis"] = trend_analysis
    if context_events is not None:
        state["context_events"] = context_events
    return state


class TestBuildPromptInputs:
    def test_basic_fields_present(self) -> None:
        result = _build_prompt_inputs(_state())
        assert result["full_name"] == "Test Rookie"
        assert result["position"] == "G"
        assert result["season"] == "2024-25"
        assert result["games_played"] == "20"

    def test_missing_position_falls_back(self) -> None:
        state = _state()
        state["profile"] = PlayerProfile(
            player_id=1,
            full_name="No Position",
            position=None,
            height_cm=None,
            weight_kg=None,
            country=None,
            team_abbreviation=None,
            team_at_draft=None,
            overall_pick=1,
            round_number=1,
            round_pick=1,
            draft_year=2024,
        )
        assert _build_prompt_inputs(state)["position"] == "N/A"

    def test_stats_lines_formats_percentages(self) -> None:
        result = _build_prompt_inputs(_state())
        assert "PTS: 22.5" in result["stats_lines"]
        assert "3P%: 36.0%" in result["stats_lines"]

    def test_stats_lines_empty_when_no_averages(self) -> None:
        state = _state(games_played=0)
        result = _build_prompt_inputs(state)
        assert result["stats_lines"] == "- (no averages available)"

    def test_trend_lines_placeholder_when_missing(self) -> None:
        result = _build_prompt_inputs(_state())
        assert "no significant trends" in result["trend_lines"]

    def test_trend_lines_filters_stable_signals(self) -> None:
        state = _state(
            trend_analysis={
                "signals": [
                    {"display": "+3.4 PTS last 10G", "strength": "strong",
                     "direction": "up"},
                    {"display": "+0.1 AST last 5G", "strength": "weak",
                     "direction": "stable"},
                ],
                "summary": "PTS up, AST steady",
                "has_significant_trends": True,
            }
        )
        result = _build_prompt_inputs(state)
        assert "+3.4 PTS" in result["trend_lines"]
        assert "AST" not in result["trend_lines"]

    def test_context_lines_placeholder_when_empty(self) -> None:
        result = _build_prompt_inputs(_state(context_events=[]))
        assert "no notable context events" in result["context_lines"]

    def test_context_lines_uses_display_strings(self) -> None:
        state = _state(
            context_events=[
                {"type": "return_from_absence",
                 "display": "Returned from 3-game absence (Nov 15 - Nov 19)"},
            ]
        )
        result = _build_prompt_inputs(state)
        assert "Returned from 3-game absence" in result["context_lines"]


class TestNoGamesGuard:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_zero_games_skips_llm(self) -> None:
        state = _state(games_played=0)
        with patch(
            "backend.agent.nodes.generate_narrative.get_anthropic_client"
        ) as mock_client:
            result = await generate_narrative(state)
        mock_client.assert_not_called()
        narrative = result["narrative"]
        assert narrative["confidence"] == 0.0
        assert narrative["trend_direction"] == "stable"
        assert "not played" in narrative["summary"]
        assert "Test Rookie" in narrative["summary"]


class TestLLMCall:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_returns_llm_output_as_dict(self) -> None:
        fake_narrative = PlayerNarrative(
            summary="Test Rookie is averaging 22.5 PTS with rising 3P%.",
            trend_direction="up",
            confidence=0.85,
        )
        # Chain: prompt | llm.with_structured_output(...); chain.ainvoke() returns
        # the parsed PlayerNarrative. Mock the terminal ainvoke.
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=fake_narrative)

        with patch(
            "backend.agent.nodes.generate_narrative.ChatPromptTemplate"
        ) as mock_prompt_cls, patch(
            "backend.agent.nodes.generate_narrative.get_anthropic_client"
        ) as mock_client:
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            mock_llm = MagicMock()
            mock_client.return_value.with_structured_output.return_value = mock_llm
            mock_prompt.__or__.return_value = mock_chain

            result = await generate_narrative(_state())

        narrative = result["narrative"]
        assert narrative["summary"].startswith("Test Rookie")
        assert narrative["trend_direction"] == "up"
        assert narrative["confidence"] == 0.85
        mock_client.assert_called_once()
        mock_chain.ainvoke.assert_awaited_once()
