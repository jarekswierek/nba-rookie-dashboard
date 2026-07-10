"""Unit tests for narrative_stream helpers.

Covers stream_summary and generate_metadata with a mocked LLM chain.
Test cases pair a canned stream of AIMessageChunks (or classification
result) with a minimal AgentState fixture — no real API traffic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessageChunk

from backend.agent.narrative_stream import generate_metadata, stream_summary
from backend.agent.state import AgentState
from shared.schemas.narrative import PlayerNarrativeMetadata
from shared.schemas.stats import (
    AggregatedStats,
    PlayerProfile,
    RollingWindow,
    StatWindows,
)


def _empty_window() -> RollingWindow:
    return RollingWindow(
        window_size=5, avg=None, delta=None, direction="stable", games_played=0
    )


def _empty_stat_windows() -> StatWindows:
    return StatWindows(
        w5=_empty_window(), w10=_empty_window(), w15=_empty_window()
    )


def _state(games_played: int = 10) -> AgentState:
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
        total_games=games_played,
        games_played=games_played,
        pts=_empty_stat_windows(),
        ast=_empty_stat_windows(),
        reb=_empty_stat_windows(),
        fg_pct=_empty_stat_windows(),
        fg3_pct=_empty_stat_windows(),
        min=_empty_stat_windows(),
        pts_season_avg=20.0,
        ast_season_avg=4.0,
        reb_season_avg=5.0,
        fg_pct_season_avg=0.45,
        fg3_pct_season_avg=0.36,
        min_season_avg=28.0,
    )
    return AgentState(
        player_id=1,
        season="2024-25",
        profile=profile,
        stats=stats,
        gaps=[],
    )


class _FakeAsyncIterator:
    def __init__(self, chunks: list[AIMessageChunk]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self) -> "_FakeAsyncIterator":
        return self

    async def __anext__(self) -> AIMessageChunk:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _mock_streaming_chain(chunks: list[AIMessageChunk]) -> MagicMock:
    """Patch ChatPromptTemplate | llm so astream yields *chunks*."""
    chain = MagicMock()
    chain.astream = MagicMock(return_value=_FakeAsyncIterator(chunks))
    prompt = MagicMock()
    prompt.__or__.return_value = chain
    prompt_cls = MagicMock()
    prompt_cls.from_messages.return_value = prompt
    return prompt_cls


class TestStreamSummary:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_yields_non_empty_string_chunks(self) -> None:
        chunks = [
            AIMessageChunk(content="Test "),
            AIMessageChunk(content="Rookie "),
            AIMessageChunk(content="showed improvement."),
        ]
        with patch(
            "backend.agent.narrative_stream.ChatPromptTemplate",
            _mock_streaming_chain(chunks),
        ), patch(
            "backend.agent.narrative_stream.get_anthropic_client"
        ) as mock_client:
            mock_client.return_value = MagicMock()
            result = [chunk async for chunk in stream_summary(_state())]
        assert result == ["Test ", "Rookie ", "showed improvement."]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_skips_empty_content_chunks(self) -> None:
        chunks = [
            AIMessageChunk(content=""),
            AIMessageChunk(content="Hello"),
            AIMessageChunk(content=""),
        ]
        with patch(
            "backend.agent.narrative_stream.ChatPromptTemplate",
            _mock_streaming_chain(chunks),
        ), patch(
            "backend.agent.narrative_stream.get_anthropic_client"
        ) as mock_client:
            mock_client.return_value = MagicMock()
            result = [chunk async for chunk in stream_summary(_state())]
        assert result == ["Hello"]


class TestGenerateMetadata:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_returns_metadata_from_structured_output(self) -> None:
        fake = PlayerNarrativeMetadata(trend_direction="up", confidence=0.82)
        chain = MagicMock()
        chain.ainvoke = AsyncMock(return_value=fake)
        prompt = MagicMock()
        prompt.__or__.return_value = chain
        prompt_cls = MagicMock()
        prompt_cls.from_messages.return_value = prompt

        with patch(
            "backend.agent.narrative_stream.ChatPromptTemplate", prompt_cls
        ), patch(
            "backend.agent.narrative_stream.get_anthropic_client"
        ) as mock_client:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            mock_client.return_value = mock_llm
            result = await generate_metadata(_state(), summary="Some prose.")

        assert result.trend_direction == "up"
        assert result.confidence == 0.82
        chain.ainvoke.assert_awaited_once()
