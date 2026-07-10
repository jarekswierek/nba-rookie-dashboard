"""SSE endpoint that streams the player's AI-generated narrative."""

import asyncio
import datetime
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.agent.context_events import detect_context_events
from backend.agent.fallback import (
    FallbackDecision,
    WarningCode,
    build_derived_metadata,
    build_fallback,
)
from backend.agent.narrative_stream import generate_metadata, stream_summary
from backend.agent.state import AgentState
from backend.agent.state_builder import build_agent_state
from backend.agent.trend_analysis import analyze_trends
from backend.api.deps import get_db_session
from backend.data import cache_postgres, cache_service
from shared.consts import DRAFT_YEAR_MIN, SEASON_PATTERN
from shared.schemas.narrative import PlayerNarrativeMetadata

logger = logging.getLogger(__name__)

router = APIRouter()

# Interval in seconds between SSE keepalive comments — long enough to avoid
# noise, short enough to keep intermediate proxies from closing idle
# connections (nginx defaults to ~60s).
_KEEPALIVE_INTERVAL_SECONDS = 15

# Fixed narrative payload for players with zero games played this season.
# Both fields are constants because the "no games" narrative is a
# deterministic short-circuit, not an LLM-generated result.
_NO_GAMES_DIRECTION = "stable"
_NO_GAMES_CONFIDENCE = 0.0


def _event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload)}


def _warning(code: WarningCode, **extra: Any) -> dict[str, str]:
    return _event("warning", {"code": code, **extra})


def _metadata_event(
    metadata: PlayerNarrativeMetadata,
    *,
    cached: bool,
    generated_at: datetime.datetime | None,
) -> dict[str, str]:
    return _event(
        "metadata",
        {
            "trend_direction": metadata.trend_direction,
            "confidence": metadata.confidence,
            "generated_at": (
                generated_at.isoformat() if generated_at is not None else None
            ),
            "cached": cached,
        },
    )


async def _emit_cached(
    session: AsyncSession, player_id: int, season: str
) -> AsyncIterator[dict[str, str]]:
    """Serve a still-fresh narrative from PostgreSQL as a single SSE burst."""
    cached = await cache_postgres.get_narrative(session, player_id, season)
    if cached is None:
        return
    yield _event("token", {"text": cached["summary"]})
    yield _event(
        "metadata",
        {
            "trend_direction": cached["trend_direction"],
            "confidence": cached["confidence"],
            "generated_at": cached["generated_at"],
            "cached": True,
        },
    )
    yield _event("done", {})


async def _emit_no_games(full_name: str) -> AsyncIterator[dict[str, str]]:
    text = f"{full_name} has not played any games this season."
    yield _event("token", {"text": text})
    yield _event(
        "metadata",
        {
            "trend_direction": _NO_GAMES_DIRECTION,
            "confidence": _NO_GAMES_CONFIDENCE,
            "generated_at": None,
            "cached": False,
        },
    )
    yield _event("done", {})


async def _safe_fetch_cached(
    session: AsyncSession, player_id: int, season: str
) -> dict[str, Any] | None:
    """Best-effort cache lookup for the fallback path.

    A cache-lookup failure during fallback must not fail the client — we still
    owe them a static message, and that path requires no I/O.
    """
    try:
        return await cache_postgres.get_narrative(session, player_id, season)
    except Exception:
        logger.exception("Fallback cache lookup failed")
        return None


async def _emit_full_fallback(
    session: AsyncSession,
    state: AgentState,
    player_id: int,
    season: str,
) -> AsyncIterator[dict[str, str]]:
    """Emit the pre-stream fallback path — nothing has been sent yet."""
    cached = await _safe_fetch_cached(session, player_id, season)
    decision: FallbackDecision = build_fallback(
        profile=state["profile"],
        cached=cached,
        trend_analysis=state.get("trend_analysis"),
        games_played=state["stats"].games_played,
    )
    warning_payload: dict[str, Any] = {}
    if decision.generated_at is not None:
        warning_payload["generated_at"] = decision.generated_at.isoformat()
    yield _warning(decision.warning_code, **warning_payload)
    yield _event("token", {"text": decision.summary})
    yield _metadata_event(
        decision.metadata,
        cached=decision.warning_code == "cached_fallback",
        generated_at=decision.generated_at,
    )
    yield _event("done", {})


async def _generate_and_stream(
    session: AsyncSession, player_id: int, season: str, draft_year: int
) -> AsyncIterator[dict[str, str]]:
    """Build state, stream summary tokens, classify metadata, persist."""
    state = await build_agent_state(session, player_id, season, draft_year)

    if state["stats"].games_played == 0:
        async for evt in _emit_no_games(state["profile"].full_name):
            yield evt
        return

    state["trend_analysis"] = analyze_trends(state["stats"]).model_dump()
    context = detect_context_events(state["gaps"], state["stats"])
    state["context_events"] = [e.model_dump(mode="json") for e in context.events]

    accumulated: list[str] = []
    try:
        async for token in stream_summary(state):
            accumulated.append(token)
            yield _event("token", {"text": token})
    except asyncio.CancelledError:
        # Client disconnected mid-stream — do not persist a truncated
        # summary and let the runtime finish cleanup normally.
        raise
    except Exception:
        logger.exception("LLM streaming failed for player=%d", player_id)
        if not accumulated:
            # Nothing shipped yet — switch to the full fallback path.
            async for evt in _emit_full_fallback(
                session, state, player_id, season
            ):
                yield evt
            return
        # Tokens already reached the client — do not splice a second
        # narrative on top. Signal interruption and close.
        yield _warning("stream_interrupted")
        yield _event("done", {})
        return

    summary = "".join(accumulated).strip()
    if not summary:
        # LLM produced no content at all — treat as a pre-stream failure.
        async for evt in _emit_full_fallback(session, state, player_id, season):
            yield evt
        return

    try:
        metadata = await generate_metadata(state, summary)
        derived = False
    except Exception:
        logger.exception(
            "Metadata classification failed for player=%d", player_id
        )
        metadata = build_derived_metadata(
            state.get("trend_analysis"), state["stats"].games_played
        )
        derived = True

    if derived:
        yield _warning("derived_metadata")
    else:
        try:
            await cache_postgres.upsert_narrative(
                session,
                player_id,
                season,
                summary=summary,
                trend_direction=metadata.trend_direction,
                confidence=metadata.confidence,
            )
        except Exception:
            # Narrative is already streamed to the client; a persistence
            # failure should not surface as a user-facing error.
            logger.exception(
                "Failed to persist narrative for player=%d", player_id
            )

    yield _metadata_event(
        metadata,
        cached=False,
        generated_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    yield _event("done", {})


async def _narrative_stream(
    session: AsyncSession, player_id: int, season: str, draft_year: int
) -> AsyncIterator[dict[str, str]]:
    if not await cache_service.is_narrative_stale(session, player_id, season):
        async for evt in _emit_cached(session, player_id, season):
            yield evt
        return
    async for evt in _generate_and_stream(
        session, player_id, season, draft_year
    ):
        yield evt


@router.get("/{player_id}/narrative")
async def stream_player_narrative(
    player_id: int = Path(..., gt=0),
    season: str = Query(..., pattern=SEASON_PATTERN),
    draft_year: int = Query(..., ge=DRAFT_YEAR_MIN),
    session: AsyncSession = Depends(get_db_session),
) -> EventSourceResponse:
    """Stream the AI narrative as Server-Sent Events.

    Event sequence: N × ``token`` → ``metadata`` → ``done``. Degraded paths
    emit a ``warning`` event before the fallback ``token``/``metadata`` or
    before an early ``done`` when the stream was already partway through.
    Keepalive comments prevent idle proxies from closing the connection.
    """
    return EventSourceResponse(
        _narrative_stream(session, player_id, season, draft_year),
        ping=_KEEPALIVE_INTERVAL_SECONDS,
    )
