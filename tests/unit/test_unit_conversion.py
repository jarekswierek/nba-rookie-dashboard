"""Unit tests for imperial → metric conversion helpers in cache_service."""

import pytest

from backend.data.cache_service import _feet_inches_to_cm, _lbs_to_kg


class TestFeetInchesToCm:
    def test_six_foot_five(self) -> None:
        assert _feet_inches_to_cm("6-5") == pytest.approx(195.6, abs=0.1)

    def test_seven_foot_zero(self) -> None:
        assert _feet_inches_to_cm("7-0") == pytest.approx(213.4, abs=0.1)

    def test_six_foot_zero(self) -> None:
        assert _feet_inches_to_cm("6-0") == pytest.approx(182.9, abs=0.1)

    def test_empty_string_returns_none(self) -> None:
        assert _feet_inches_to_cm("") is None

    def test_none_returns_none(self) -> None:
        assert _feet_inches_to_cm(None) is None

    def test_malformed_string_returns_none(self) -> None:
        assert _feet_inches_to_cm("6'5\"") is None


class TestLbsToKg:
    def test_215_lbs(self) -> None:
        assert _lbs_to_kg("215") == pytest.approx(97.5, abs=0.1)

    def test_180_lbs(self) -> None:
        assert _lbs_to_kg("180") == pytest.approx(81.6, abs=0.1)

    def test_empty_string_returns_none(self) -> None:
        assert _lbs_to_kg("") is None

    def test_none_returns_none(self) -> None:
        assert _lbs_to_kg(None) is None

    def test_non_numeric_returns_none(self) -> None:
        assert _lbs_to_kg("N/A") is None
