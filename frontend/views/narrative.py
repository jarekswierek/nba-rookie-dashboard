"""AI narrative expander: SSE streaming, confidence, timestamps.

Every Streamlit interaction reruns the whole script, which would restart the SSE
stream mid-flight and burn LLM tokens on every click. To avoid that, the first
complete stream is cached into ``st.session_state`` and subsequent reruns render
statically. Streams that end in a warning (``stream_interrupted`` /
``unavailable``) are intentionally not cached so the next rerun retries.
"""

import datetime
from dataclasses import dataclass, field
from typing import Any

import httpx
import streamlit as st

from frontend import api_client, cache
from shared.consts import (
    NARRATIVE_WARNING_CACHED_FALLBACK,
    NARRATIVE_WARNING_DERIVED_METADATA,
    NARRATIVE_WARNING_STREAM_INTERRUPTED,
    NARRATIVE_WARNING_UNAVAILABLE,
)

# User-facing text for each backend warning code.
_WARNING_MESSAGES: dict[str, str] = {
    NARRATIVE_WARNING_CACHED_FALLBACK: (
        "Live analysis unavailable — showing cached version."
    ),
    NARRATIVE_WARNING_UNAVAILABLE: ("Analysis unavailable — try again later."),
    NARRATIVE_WARNING_DERIVED_METADATA: (
        "AI classifier failed — direction and confidence derived from stats."
    ),
    NARRATIVE_WARNING_STREAM_INTERRUPTED: (
        "Analysis interrupted — text above may be incomplete."
    ),
}

# Warnings that indicate a degraded final state — do not persist to
# session cache so the next rerun retries the live path.
_NO_CACHE_WARNING_CODES: frozenset[str] = frozenset(
    {NARRATIVE_WARNING_UNAVAILABLE, NARRATIVE_WARNING_STREAM_INTERRUPTED}
)

_CURSOR = "▍"


@dataclass
class _NarrativeResult:
    summary: str = ""
    metadata: dict[str, Any] | None = None
    warning_code: str | None = None
    warning_extra: dict[str, Any] = field(default_factory=dict)


def _session_key(player_id: int, season: str, year: int) -> str:
    # Year is included because the same player_id may appear in different
    # draft cohorts across a long-running session — cache_key collisions
    # would show one player's narrative for another.
    return f"narrative:{player_id}:{season}:{year}"


def _fmt_timestamp(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        dt = datetime.datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _render_warning(slot: Any, code: str, extra: dict[str, Any]) -> None:
    message = _WARNING_MESSAGES.get(code, f"Analysis warning: {code}")
    generated_at = _fmt_timestamp(extra.get("generated_at"))
    if generated_at is not None:
        message += f" (from {generated_at})"
    slot.warning(message, icon="⚠️")


def _render_metadata(
    slot: Any,
    metadata: dict[str, Any],
    stats_fetched_at: datetime.datetime | None,
) -> None:
    confidence = float(metadata.get("confidence", 0.0))
    generated_at = _fmt_timestamp(metadata.get("generated_at"))
    cached = bool(metadata.get("cached", False))

    lines: list[str] = []
    stats_ts = (
        stats_fetched_at.strftime("%Y-%m-%d %H:%M UTC")
        if stats_fetched_at is not None
        else "—"
    )
    lines.append(f"🟢 Stats last fetched: {stats_ts}")
    if generated_at is not None:
        lines.append(f"🟡 AI analysis generated: {generated_at}")
    if cached:
        lines.append("⚡ cached")

    with slot.container():
        # Confidence bar only when the LLM actually generated something.
        if generated_at is not None:
            st.progress(
                min(max(confidence, 0.0), 1.0),
                text=f"Confidence: {confidence:.0%}",
            )
        st.caption(" · ".join(lines))


def _stream_and_render(
    player_id: int,
    season: str,
    year: int,
    warn_slot: Any,
    text_slot: Any,
    meta_slot: Any,
    stats_fetched_at: datetime.datetime | None,
) -> _NarrativeResult:
    """Consume SSE events, updating slots as tokens arrive."""
    result = _NarrativeResult()
    try:
        for sse in api_client.stream_narrative(player_id, season, year):
            if sse.event == "warning":
                result.warning_code = str(sse.data.get("code", ""))
                result.warning_extra = {
                    k: v for k, v in sse.data.items() if k != "code"
                }
                _render_warning(
                    warn_slot, result.warning_code, result.warning_extra
                )
            elif sse.event == "token":
                result.summary += str(sse.data.get("text", ""))
                text_slot.markdown(result.summary + _CURSOR)
            elif sse.event == "metadata":
                result.metadata = dict(sse.data)
                _render_metadata(meta_slot, result.metadata, stats_fetched_at)
            elif sse.event == "error":
                warn_slot.error(
                    f"Analysis error: {sse.data.get('message', 'unknown')}",
                    icon="⚠️",
                )
                result.warning_code = NARRATIVE_WARNING_STREAM_INTERRUPTED
                break
            elif sse.event == "done":
                break
    except httpx.HTTPError as exc:
        warn_slot.error(f"Failed to load analysis: {exc}", icon="⚠️")
        result.warning_code = NARRATIVE_WARNING_STREAM_INTERRUPTED

    text_slot.markdown(result.summary or "*(no content)*")
    return result


def _render_from_cache(
    cached: _NarrativeResult,
    warn_slot: Any,
    text_slot: Any,
    meta_slot: Any,
    stats_fetched_at: datetime.datetime | None,
) -> None:
    if cached.warning_code is not None:
        _render_warning(warn_slot, cached.warning_code, cached.warning_extra)
    text_slot.markdown(cached.summary or "*(no content)*")
    if cached.metadata is not None:
        _render_metadata(meta_slot, cached.metadata, stats_fetched_at)


def render_narrative_panel(player_id: int, season: str, year: int) -> None:
    """Render the AI Analysis expander with streaming or a cached replay."""
    try:
        agg = cache.cached_aggregated_stats(player_id, season)
        stats_fetched_at = agg.fetched_at
    except httpx.HTTPError:
        stats_fetched_at = None

    with st.expander("🤖 AI Analysis", expanded=True):
        warn_slot = st.empty()
        text_slot = st.empty()
        meta_slot = st.empty()

        session_key = _session_key(player_id, season, year)
        cached_result: _NarrativeResult | None = st.session_state.get(
            session_key
        )
        if cached_result is not None:
            _render_from_cache(
                cached_result, warn_slot, text_slot, meta_slot, stats_fetched_at
            )
            return

        result = _stream_and_render(
            player_id,
            season,
            year,
            warn_slot,
            text_slot,
            meta_slot,
            stats_fetched_at,
        )
        # Only persist stable results so degraded paths retry on next rerun.
        if result.warning_code not in _NO_CACHE_WARNING_CODES:
            st.session_state[session_key] = result
