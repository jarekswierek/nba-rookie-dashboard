"""Unit tests for frontend rolling_average helper."""

import pytest

from frontend.charts import rolling_average


class TestRollingAverage:
    def test_empty_returns_empty(self) -> None:
        assert rolling_average([], window=5) == []

    def test_all_none_returns_all_none(self) -> None:
        assert rolling_average([None, None, None], window=3) == [None, None, None]

    def test_fewer_than_window_pads_with_none(self) -> None:
        # First (window-1) positions cannot see a full window backward.
        result = rolling_average([10.0, 20.0, 30.0], window=5)
        assert result == [None, None, None]

    def test_full_window_computes_correctly(self) -> None:
        # 5-game window on 5 uniform values yields the same value.
        result = rolling_average([10.0, 10.0, 10.0, 10.0, 10.0], window=5)
        assert result == [None, None, None, None, 10.0]

    def test_trailing_window_updates_each_step(self) -> None:
        # Values 1..7, window 3: positions 0-1 None, then trailing 3-slot mean.
        result = rolling_average(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], window=3
        )
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(2.0)  # (1+2+3)/3
        assert result[3] == pytest.approx(3.0)  # (2+3+4)/3
        assert result[6] == pytest.approx(6.0)  # (5+6+7)/3

    def test_none_entries_skipped_and_do_not_advance_window(self) -> None:
        # Window 3 on [1, None, 2, 3, None, 4]; DNPs excluded per backend rule.
        result = rolling_average([1.0, None, 2.0, 3.0, None, 4.0], window=3)
        # Position 0: only 1 value seen, need 3 -> None
        assert result[0] is None
        # Position 1: None value itself is skipped; only 1 non-None seen -> None
        assert result[1] is None
        # Position 2: 3 non-None values seen (1, 2 - only 2 available) -> None
        assert result[2] is None
        # Position 3: [3, 2, 1] non-None trailing -> mean 2.0
        assert result[3] == pytest.approx(2.0)
        # Position 4: DNP itself, but trailing non-None slice is [3, 2, 1] -> 2.0
        assert result[4] == pytest.approx(2.0)
        # Position 5: [4, 3, 2] non-None -> mean 3.0
        assert result[5] == pytest.approx(3.0)

    def test_default_window_matches_module_constant(self) -> None:
        from frontend.charts import ROLLING_WINDOW

        # Default arg wires through the module constant.
        values = [1.0] * (ROLLING_WINDOW + 2)
        result = rolling_average(values)
        assert result[ROLLING_WINDOW - 1] is not None
