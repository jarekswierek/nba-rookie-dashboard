"""Fallback narrative selection when live LLM generation fails.

Pure functions that receive already-fetched data (cached narrative, trend
analysis, stats) and decide what to serve. I/O — the cache read itself — stays in
the endpoint; wrapping every failure with a try/except here would only hide
errors that should be logged upstream.
"""

import datetime
from typing import Any, Literal

from pydantic import BaseModel

from shared.schemas.narrative import PlayerNarrativeMetadata
from shared.schemas.stats import PlayerProfile
from shared.types import TrendDirection

# Derived-confidence bounds. Starts at the floor (a single game already
# tells us something), grows by _STEP per additional game, and never
# claims LLM-level certainty — the ceiling stays below 1.0.
_CONFIDENCE_FLOOR = 0.5
_CONFIDENCE_STEP_PER_GAME = 0.02
_CONFIDENCE_CEILING = 0.9


class FallbackDecision(BaseModel):
    """Content chosen when the live LLM path failed before any token shipped."""

    warning_code: Literal["cached_fallback", "unavailable"]
    summary: str
    metadata: PlayerNarrativeMetadata
    generated_at: datetime.datetime | None


def _majority_direction(
    trend_analysis: dict[str, Any] | None,
) -> TrendDirection:
    """Return the dominant non-stable direction across trend signals.

    Ties or absent signals fall back to ``"stable"`` — we would rather be silent
    about a direction than manufacture one from a coin flip.
    """
    if not trend_analysis:
        return "stable"
    signals = trend_analysis.get("signals", [])
    up = sum(1 for s in signals if s.get("direction") == "up")
    down = sum(1 for s in signals if s.get("direction") == "down")
    if up > down:
        return "up"
    if down > up:
        return "down"
    return "stable"


def _confidence_from_games_played(games_played: int) -> float:
    """Return a bounded confidence derived from sample size alone.

    Deliberately capped below 1.0 so a deterministic fallback never claims LLM-
    level certainty.
    """
    return min(
        _CONFIDENCE_FLOOR + games_played * _CONFIDENCE_STEP_PER_GAME,
        _CONFIDENCE_CEILING,
    )


def build_derived_metadata(
    trend_analysis: dict[str, Any] | None, games_played: int
) -> PlayerNarrativeMetadata:
    """Compute PlayerNarrativeMetadata without an LLM call.

    Used when the summary streamed successfully but the structured classification
    call failed. The direction is derived from existing trend signals; confidence
    is a bounded function of sample size.
    """
    return PlayerNarrativeMetadata(
        trend_direction=_majority_direction(trend_analysis),
        confidence=_confidence_from_games_played(games_played),
    )


def build_fallback(
    profile: PlayerProfile,
    cached: dict[str, Any] | None,
    trend_analysis: dict[str, Any] | None,
    games_played: int,
) -> FallbackDecision:
    """Choose fallback content when live LLM fails before any token ships.

    Prefers a stale cached narrative (with its ``generated_at`` surfaced so the
    UI can label the staleness) and falls back to a static message that only
    requires ``profile.full_name`` — the last-resort path must not depend on
    cache availability.
    """
    if cached is not None:
        raw_generated_at = cached.get("generated_at")
        generated_at = (
            datetime.datetime.fromisoformat(raw_generated_at)
            if isinstance(raw_generated_at, str)
            else raw_generated_at
        )
        return FallbackDecision(
            warning_code="cached_fallback",
            summary=cached["summary"],
            metadata=PlayerNarrativeMetadata(
                trend_direction=cached["trend_direction"],
                confidence=cached["confidence"],
            ),
            generated_at=generated_at,
        )
    return FallbackDecision(
        warning_code="unavailable",
        summary=(
            f"Analysis unavailable for {profile.full_name} — " "try again later."
        ),
        metadata=build_derived_metadata(trend_analysis, games_played),
        generated_at=None,
    )
