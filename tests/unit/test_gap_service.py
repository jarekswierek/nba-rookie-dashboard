"""Unit tests for gap_service.detect_gaps pure function."""

import datetime

import pytest

from backend.data.gap_service import detect_gaps
from shared.schemas.stats import GameLog


def _log(game_number: int, *, is_dnp: bool = False) -> GameLog:
    """Build a GameLog with sensible defaults; set is_dnp via min=None."""
    return GameLog(
        game_id=f"g{game_number:04d}",
        game_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=game_number),
        matchup="NYK vs BOS",
        game_number=game_number,
        pts=None if is_dnp else 20.0,
        ast=None if is_dnp else 5.0,
        reb=None if is_dnp else 6.0,
        fg_pct=None if is_dnp else 0.45,
        fg3_pct=None if is_dnp else 0.35,
        min=None if is_dnp else 30.0,
    )


class TestDetectGaps:
    def test_no_dnp_returns_empty(self) -> None:
        logs = [_log(i) for i in range(1, 11)]
        assert detect_gaps(logs) == []

    def test_all_dnp_single_gap(self) -> None:
        logs = [_log(i, is_dnp=True) for i in range(1, 11)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 1
        assert gaps[0].end_game_number == 10
        assert gaps[0].length == 10

    def test_single_gap_in_middle(self) -> None:
        logs = [_log(i, is_dnp=i in {5, 6, 7}) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 5
        assert gaps[0].end_game_number == 7
        assert gaps[0].length == 3

    def test_leading_gap(self) -> None:
        logs = [_log(i, is_dnp=i in {1, 2}) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 1
        assert gaps[0].length == 2

    def test_trailing_gap(self) -> None:
        logs = [_log(i, is_dnp=i in {19, 20}) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 19
        assert gaps[0].end_game_number == 20
        assert gaps[0].length == 2

    def test_two_separate_gaps(self) -> None:
        dnp_positions = {5, 6, 7, 12, 13}
        logs = [_log(i, is_dnp=i in dnp_positions) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 2
        assert gaps[0].start_game_number == 5
        assert gaps[0].end_game_number == 7
        assert gaps[1].start_game_number == 12
        assert gaps[1].end_game_number == 13

    def test_single_game_dnp(self) -> None:
        logs = [_log(i, is_dnp=(i == 10)) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 10
        assert gaps[0].end_game_number == 10
        assert gaps[0].length == 1

    def test_empty_input_returns_empty(self) -> None:
        assert detect_gaps([]) == []

    def test_min_length_filters_short_gaps(self) -> None:
        dnp_positions = {5, 10, 11, 12}
        logs = [_log(i, is_dnp=i in dnp_positions) for i in range(1, 21)]
        gaps = detect_gaps(logs, min_length=2)
        assert len(gaps) == 1
        assert gaps[0].start_game_number == 10
        assert gaps[0].end_game_number == 12

    def test_unsorted_input_raises(self) -> None:
        logs = [_log(1), _log(3), _log(2)]
        with pytest.raises(ValueError, match="sorted ascending"):
            detect_gaps(logs)

    def test_dates_match_boundary_games(self) -> None:
        logs = [_log(i, is_dnp=i in {5, 6, 7}) for i in range(1, 21)]
        gaps = detect_gaps(logs)
        assert gaps[0].start_date == logs[4].game_date
        assert gaps[0].end_date == logs[6].game_date
