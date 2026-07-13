"""Unit tests for frontend/formatting.py."""

from frontend.formatting import (
    fmt_delta,
    fmt_pct_delta,
    fmt_pct_value,
    fmt_value,
    season_string,
)


class TestSeasonString:
    def test_standard_year(self) -> None:
        assert season_string(2024) == "2024-25"

    def test_century_boundary(self) -> None:
        assert season_string(1999) == "1999-00"


class TestFmtValue:
    def test_normal_float(self) -> None:
        assert fmt_value(20.5) == "20.5"

    def test_none_returns_dash(self) -> None:
        assert fmt_value(None) == "—"

    def test_zero(self) -> None:
        assert fmt_value(0.0) == "0.0"

    def test_custom_decimals(self) -> None:
        assert fmt_value(3.14159, decimals=2) == "3.14"


class TestFmtDelta:
    def test_positive_has_explicit_sign(self) -> None:
        assert fmt_delta(3.4) == "+3.4"

    def test_negative_keeps_sign(self) -> None:
        assert fmt_delta(-2.1) == "-2.1"

    def test_zero_shows_plus(self) -> None:
        assert fmt_delta(0.0) == "+0.0"

    def test_none_returns_none(self) -> None:
        assert fmt_delta(None) is None


class TestFmtPctValue:
    def test_converts_to_percent(self) -> None:
        assert fmt_pct_value(0.354) == "35.4%"

    def test_none_returns_dash(self) -> None:
        assert fmt_pct_value(None) == "—"


class TestFmtPctDelta:
    def test_uses_pp_suffix(self) -> None:
        assert fmt_pct_delta(0.034) == "+3.4 pp"

    def test_negative_pp(self) -> None:
        assert fmt_pct_delta(-0.02) == "-2.0 pp"

    def test_none_returns_none(self) -> None:
        assert fmt_pct_delta(None) is None
