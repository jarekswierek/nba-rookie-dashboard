"""Unit tests for fallback pure functions."""

import datetime

from backend.agent.fallback import (
    _confidence_from_games_played,
    _majority_direction,
    build_derived_metadata,
    build_fallback,
)
from shared.schemas.stats import PlayerProfile


def _profile(full_name: str = "Test Rookie") -> PlayerProfile:
    return PlayerProfile(
        player_id=1,
        full_name=full_name,
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


class TestMajorityDirection:
    def test_none_analysis_returns_stable(self) -> None:
        assert _majority_direction(None) == "stable"

    def test_empty_signals_returns_stable(self) -> None:
        assert _majority_direction({"signals": []}) == "stable"

    def test_up_majority(self) -> None:
        analysis = {
            "signals": [
                {"direction": "up"},
                {"direction": "up"},
                {"direction": "down"},
                {"direction": "stable"},
            ]
        }
        assert _majority_direction(analysis) == "up"

    def test_down_majority(self) -> None:
        analysis = {
            "signals": [
                {"direction": "down"},
                {"direction": "down"},
                {"direction": "up"},
            ]
        }
        assert _majority_direction(analysis) == "down"

    def test_tie_returns_stable(self) -> None:
        analysis = {
            "signals": [
                {"direction": "up"},
                {"direction": "down"},
            ]
        }
        assert _majority_direction(analysis) == "stable"

    def test_all_stable_returns_stable(self) -> None:
        analysis = {
            "signals": [
                {"direction": "stable"},
                {"direction": "stable"},
            ]
        }
        assert _majority_direction(analysis) == "stable"


class TestConfidenceFromGamesPlayed:
    def test_no_games_yields_floor(self) -> None:
        assert _confidence_from_games_played(0) == 0.5

    def test_grows_with_games(self) -> None:
        assert _confidence_from_games_played(10) == 0.7

    def test_caps_at_90(self) -> None:
        assert _confidence_from_games_played(100) == 0.9
        assert _confidence_from_games_played(1000) == 0.9


class TestBuildDerivedMetadata:
    def test_uses_majority_direction_and_capped_confidence(self) -> None:
        analysis = {
            "signals": [
                {"direction": "up"},
                {"direction": "up"},
                {"direction": "stable"},
            ]
        }
        metadata = build_derived_metadata(analysis, games_played=20)
        assert metadata.trend_direction == "up"
        assert metadata.confidence == 0.9

    def test_no_analysis_yields_stable_at_floor(self) -> None:
        metadata = build_derived_metadata(None, games_played=0)
        assert metadata.trend_direction == "stable"
        assert metadata.confidence == 0.5


class TestBuildFallback:
    def test_cache_hit_returns_cached_summary(self) -> None:
        cached = {
            "summary": "Test Rookie averages 20 PTS.",
            "trend_direction": "up",
            "confidence": 0.85,
            "generated_at": "2026-06-01T12:00:00+00:00",
        }
        decision = build_fallback(
            profile=_profile(),
            cached=cached,
            trend_analysis=None,
            games_played=15,
        )
        assert decision.warning_code == "cached_fallback"
        assert decision.summary == "Test Rookie averages 20 PTS."
        assert decision.metadata.trend_direction == "up"
        assert decision.metadata.confidence == 0.85
        assert decision.generated_at == datetime.datetime(
            2026, 6, 1, 12, 0, tzinfo=datetime.timezone.utc
        )

    def test_no_cache_returns_static_message(self) -> None:
        decision = build_fallback(
            profile=_profile(full_name="John Doe"),
            cached=None,
            trend_analysis=None,
            games_played=0,
        )
        assert decision.warning_code == "unavailable"
        assert "John Doe" in decision.summary
        assert "unavailable" in decision.summary.lower()
        assert decision.generated_at is None

    def test_no_cache_uses_derived_metadata(self) -> None:
        analysis = {
            "signals": [{"direction": "down"}, {"direction": "down"}]
        }
        decision = build_fallback(
            profile=_profile(),
            cached=None,
            trend_analysis=analysis,
            games_played=10,
        )
        assert decision.metadata.trend_direction == "down"
        assert decision.metadata.confidence == 0.7
