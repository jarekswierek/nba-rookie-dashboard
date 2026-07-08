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
from backend.agent.narrative_stream import generate_metadata, stream_summary
from backend.agent.state_builder import build_agent_state
from backend.agent.trend_analysis import analyze_trends
from backend.api.deps import get_db_session
from backend.data import cache_postgres, cache_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload)}


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
        {"trend_direction": "stable", "confidence": 0.0, "cached": False},
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
    except Exception as exc:
        logger.exception("LLM streaming failed for player=%d", player_id)
        yield _event("error", {"code": "llm_error", "message": str(exc)})
        return

    summary = "".join(accumulated).strip()
    if not summary:
        yield _event(
            "error",
            {"code": "empty_summary", "message": "Model returned no content"},
        )
        return

    try:
        metadata = await generate_metadata(state, summary)
    except Exception as exc:
        logger.exception(
            "Metadata classification failed for player=%d", player_id
        )
        yield _event("error", {"code": "metadata_error", "message": str(exc)})
        return

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
        logger.exception("Failed to persist narrative for player=%d", player_id)

    yield _event(
        "metadata",
        {
            "trend_direction": metadata.trend_direction,
            "confidence": metadata.confidence,
            "generated_at": datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            "cached": False,
        },
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
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    draft_year: int = Query(..., ge=2000),
    session: AsyncSession = Depends(get_db_session),
) -> EventSourceResponse:
    """Stream the AI narrative as Server-Sent Events.

    Event sequence: N × ``token`` → ``metadata`` → ``done``, or a single
    ``error`` on failure. ``ping=15`` sends keepalive comments so idle
    proxies do not close the connection.
    """
    return EventSourceResponse(
        _narrative_stream(session, player_id, season, draft_year),
        ping=15,
    )
