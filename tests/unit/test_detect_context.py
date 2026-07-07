"""Unit tests for detect_context node (pure logic)."""

import datetime
from typing import Literal

import pytest

from backend.agent.nodes.detect_context import _detect_context
from backend.schemas.context import (
    CurrentlyAbsent,
    ExtendedAbsence,
    ReturnFromAbsence,
)
from backend.schemas.gaps import GapEvent
from backend.schemas.stats import AggregatedStats, RollingWindow, StatWindows


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


def _stats(total_games: int) -> AggregatedStats:
    return AggregatedStats(
        player_id=1,
        season="2024-25",
        total_games=total_games,
        games_played=total_games,
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


def _gap(
    start: int, end: int, *, start_month: int = 11, start_day: int = 15
) -> GapEvent:
    start_date = datetime.date(2024, start_month, start_day)
    end_date = start_date + datetime.timedelta(days=(end - start) * 2)
    return GapEvent(
        start_game_number=start,
        end_game_number=end,
        start_date=start_date,
        end_date=end_date,
    )


class TestEmpty:
    def test_no_gaps_returns_empty(self) -> None:
        assert _detect_context([], _stats(total_games=20)).events == []

    def test_zero_total_games_returns_empty(self) -> None:
        gap = _gap(1, 3)
        assert _detect_context([gap], _stats(total_games=0)).events == []


class TestSingleGap:
    def test_short_ended_gap_yields_return(self) -> None:
        gap = _gap(5, 7)  # length 3
        result = _detect_context([gap], _stats(total_games=20))
        assert len(result.events) == 1
        assert isinstance(result.events[0], ReturnFromAbsence)
        assert result.events[0].gap_length == 3

    def test_trailing_gap_yields_currently_absent(self) -> None:
        gap = _gap(18, 20)  # ends at total_games=20
        result = _detect_context([gap], _stats(total_games=20))
        assert len(result.events) == 1
        assert isinstance(result.events[0], CurrentlyAbsent)
        assert result.events[0].games_missed == 3

    def test_short_gap_below_threshold_no_extended(self) -> None:
        gap = _gap(5, 8)  # length 4 < 5 threshold
        result = _detect_context([gap], _stats(total_games=20))
        assert not any(isinstance(e, ExtendedAbsence) for e in result.events)


class TestExtendedAbsence:
    def test_long_ended_gap_yields_both_events(self) -> None:
        gap = _gap(5, 16)  # length 12 → extended AND return
        result = _detect_context([gap], _stats(total_games=25))
        types = {e.type for e in result.events}
        assert types == {"extended_absence", "return_from_absence"}

    def test_long_trailing_gap_yields_extended_and_currently(self) -> None:
        gap = _gap(9, 20)  # length 12, ends at total_games=20
        result = _detect_context([gap], _stats(total_games=20))
        types = {e.type for e in result.events}
        assert types == {"extended_absence", "currently_absent"}


class TestMultipleGaps:
    def test_only_latest_gap_yields_return_or_absent(self) -> None:
        gaps = [_gap(2, 3), _gap(8, 9), _gap(15, 16)]  # all length 2
        result = _detect_context(gaps, _stats(total_games=25))
        returns = [e for e in result.events if isinstance(e, ReturnFromAbsence)]
        assert len(returns) == 1
        assert returns[0].start_date == gaps[2].start_date

    def test_older_long_gap_still_yields_extended(self) -> None:
        # Early gap length 8 (extended), late gap length 2 (short return)
        gaps = [_gap(2, 9), _gap(20, 21)]
        result = _detect_context(gaps, _stats(total_games=25))
        extended = [e for e in result.events if isinstance(e, ExtendedAbsence)]
        returns = [e for e in result.events if isinstance(e, ReturnFromAbsence)]
        assert len(extended) == 1
        assert extended[0].start_date == gaps[0].start_date
        assert len(returns) == 1
        assert returns[0].start_date == gaps[1].start_date

    def test_unsorted_input_produces_same_result(self) -> None:
        gaps_sorted = [_gap(2, 3), _gap(8, 9), _gap(15, 16)]
        gaps_shuffled = [gaps_sorted[2], gaps_sorted[0], gaps_sorted[1]]
        sorted_result = _detect_context(gaps_sorted, _stats(total_games=25))
        shuffled_result = _detect_context(gaps_shuffled, _stats(total_games=25))
        assert sorted_result == shuffled_result


class TestDisplay:
    def test_return_display_format(self) -> None:
        gap = GapEvent(
            start_game_number=5,
            end_game_number=7,
            start_date=datetime.date(2024, 11, 15),
            end_date=datetime.date(2024, 11, 19),
        )
        result = _detect_context([gap], _stats(total_games=20))
        assert result.events[0].display == "Returned from 3-game absence (Nov 15 – Nov 19)"

    def test_currently_absent_display_format(self) -> None:
        gap = GapEvent(
            start_game_number=18,
            end_game_number=20,
            start_date=datetime.date(2024, 11, 20),
            end_date=datetime.date(2024, 11, 24),
        )
        result = _detect_context([gap], _stats(total_games=20))
        assert result.events[0].display == "Absent since Nov 20 (3 games missed)"

    def test_extended_display_format(self) -> None:
        gap = GapEvent(
            start_game_number=5,
            end_game_number=16,
            start_date=datetime.date(2025, 1, 5),
            end_date=datetime.date(2025, 1, 28),
        )
        result = _detect_context([gap], _stats(total_games=25))
        extended = next(e for e in result.events if isinstance(e, ExtendedAbsence))
        assert extended.display == "Extended 12-game absence (Jan 05 – Jan 28)"


@pytest.mark.asyncio(loop_scope="function")
async def test_node_returns_serialised_dicts() -> None:
    """detect_context_events must emit JSON-serialisable dicts."""
    from backend.agent.nodes.detect_context import detect_context_events
    from backend.agent.state import AgentState

    gap = _gap(5, 7)
    state = AgentState(
        player_id=1,
        season="2024-25",
        profile=None,  # type: ignore[typeddict-item]  # not used by this node
        stats=_stats(total_games=20),
        gaps=[gap],
    )
    result = await detect_context_events(state)
    assert "context_events" in result
    events = result["context_events"]
    assert isinstance(events, list)
    assert isinstance(events[0], dict)
    assert events[0]["type"] == "return_from_absence"
    assert isinstance(events[0]["start_date"], str)  # date serialised to ISO
