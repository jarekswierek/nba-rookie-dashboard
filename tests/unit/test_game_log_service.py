"""Unit tests for game_log_service parsing logic.

Tests cover pure functions only — no I/O, no database, no Redis.
"""

import datetime

import pytest

from backend.data.game_log_service import (
    _parse_game_date,
    _parse_min,
    _parse_records,
)


class TestParseMin:
    def test_none_returns_none(self) -> None:
        assert _parse_min(None) is None

    def test_zero_float_returns_none(self) -> None:
        assert _parse_min(0.0) is None

    def test_zero_int_returns_none(self) -> None:
        assert _parse_min(0) is None

    def test_positive_float_returns_float(self) -> None:
        assert _parse_min(32.5) == 32.5

    def test_positive_int_returns_float(self) -> None:
        result = _parse_min(28)
        assert result == 28.0

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_min("DNP") is None


class TestParseGameDate:
    def test_parses_standard_format(self) -> None:
        result = _parse_game_date("Jan 15, 2025")
        assert result == datetime.date(2025, 1, 15)

    def test_parses_single_digit_day(self) -> None:
        result = _parse_game_date("Nov 3, 2024")
        assert result == datetime.date(2024, 11, 3)

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_game_date("2025-01-15")


class TestParseRecords:
    _BASE_RECORD = {
        "GAME_ID": "0022400001",
        "GAME_DATE": "Jan 15, 2025",
        "MATCHUP": "NYK vs BOS",
        "MIN": 32.0,
        "PTS": 24.0,
        "REB": 5.0,
        "AST": 3.0,
        "FG_PCT": 0.511,
        "FG3_PCT": 0.400,
    }

    def test_game_number_assigned_ascending(self) -> None:
        records = [
            {**self._BASE_RECORD, "GAME_DATE": "Jan 15, 2025", "GAME_ID": "002"},
            {**self._BASE_RECORD, "GAME_DATE": "Jan 12, 2025", "GAME_ID": "001"},
        ]
        logs = _parse_records(records)
        assert logs[0].game_number == 1
        assert logs[0].game_date == datetime.date(2025, 1, 12)
        assert logs[1].game_number == 2
        assert logs[1].game_date == datetime.date(2025, 1, 15)

    def test_nba_api_descending_order_reversed(self) -> None:
        # nba_api returns newest first; _parse_records must sort ascending
        records = [
            {**self._BASE_RECORD, "GAME_DATE": "Jan 20, 2025", "GAME_ID": "003"},
            {**self._BASE_RECORD, "GAME_DATE": "Jan 15, 2025", "GAME_ID": "002"},
            {**self._BASE_RECORD, "GAME_DATE": "Jan 12, 2025", "GAME_ID": "001"},
        ]
        logs = _parse_records(records)
        assert [g.game_number for g in logs] == [1, 2, 3]
        assert logs[0].game_date == datetime.date(2025, 1, 12)
        assert logs[2].game_date == datetime.date(2025, 1, 20)

    def test_dnp_row_has_all_stats_none(self) -> None:
        records = [
            {
                **self._BASE_RECORD,
                "MIN": 0,
                "PTS": 0,
                "REB": 0,
                "AST": 0,
                "FG_PCT": 0,
                "FG3_PCT": 0,
            }
        ]
        log = _parse_records(records)[0]
        assert log.is_dnp is True
        assert log.min is None
        assert log.pts is None
        assert log.reb is None
        assert log.ast is None
        assert log.fg_pct is None
        assert log.fg3_pct is None

    def test_played_game_stats_populated(self) -> None:
        log = _parse_records([self._BASE_RECORD])[0]
        assert log.is_dnp is False
        assert log.pts == 24.0
        assert log.reb == 5.0
        assert log.ast == 3.0
        assert log.fg_pct == pytest.approx(0.511)
        assert log.fg3_pct == pytest.approx(0.400)

    def test_fallback_game_id_when_missing(self) -> None:
        record = {k: v for k, v in self._BASE_RECORD.items() if k != "GAME_ID"}
        log = _parse_records([record])[0]
        assert "Jan 15, 2025" in log.game_id
        assert "NYK vs BOS" in log.game_id

    def test_empty_records_returns_empty_list(self) -> None:
        assert _parse_records([]) == []

    def test_game_id_used_when_present(self) -> None:
        log = _parse_records([self._BASE_RECORD])[0]
        assert log.game_id == "0022400001"
