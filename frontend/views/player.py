"""Main player view: header, bio row, and 5-metric summary.

Trend badge in the header is a header-only heuristic (majority vote on w5
direction across counting stats) — not the same as the backend ``analyze_trends``
output. Aggregating across percentages was skipped because low-attempt shooting
percentages swing week to week and would skew the overall direction.
"""

from typing import Literal

import httpx
import streamlit as st

from frontend import cache
from frontend.formatting import (
    fmt_delta,
    fmt_pct_delta,
    fmt_pct_value,
    fmt_value,
)
from frontend.views.narrative import render_narrative_panel
from shared.schemas.draft import DraftPlayer
from shared.schemas.stats import AggregatedStats

# Counting stats used to derive the overall header trend badge.
# Percentages (fg_pct/fg3_pct) are excluded — small-sample swings would
# dominate the majority vote and mislead the header.
_TREND_STATS: tuple[str, ...] = ("pts", "reb", "ast", "min")

_TREND_ARROWS: dict[str, str] = {"up": "▲", "down": "▼", "stable": "→"}


def _overall_trend(stats: AggregatedStats) -> Literal["up", "down", "stable"]:
    """Majority vote across w5 directions of the counting stats."""
    up = sum(
        1 for name in _TREND_STATS if getattr(stats, name).w5.direction == "up"
    )
    down = sum(
        1 for name in _TREND_STATS if getattr(stats, name).w5.direction == "down"
    )
    if up > down:
        return "up"
    if down > up:
        return "down"
    return "stable"


def _find_player(player_id: int, year: int) -> DraftPlayer | None:
    """Look up the draft player object in the cached draft class."""
    draft_class = cache.cached_draft_class(year)
    for player in draft_class.players:
        if player.player_id == player_id:
            return player
    return None


def _render_header(profile: DraftPlayer, stats: AggregatedStats) -> None:
    arrow = _TREND_ARROWS[_overall_trend(stats)]
    st.title(f"🏀 {profile.full_name}  {arrow}")


def _render_bio_row(profile: DraftPlayer, season: str) -> None:
    parts: list[str] = []
    if profile.height_cm is not None:
        parts.append(f"📏 {profile.height_cm:.0f} cm")
    if profile.weight_kg is not None:
        parts.append(f"⚖️ {profile.weight_kg:.0f} kg")
    if profile.country:
        parts.append(profile.country)
    if profile.position:
        parts.append(profile.position)
    parts.append(season)
    st.caption(" · ".join(parts))


def _render_metrics_row(stats: AggregatedStats) -> None:
    cols = st.columns(5, gap="small")
    help_text = "5-game rolling vs season average"
    with cols[0]:
        st.metric(
            label="PTS",
            value=fmt_value(stats.pts_season_avg),
            delta=fmt_delta(stats.pts.w5.delta),
            help=help_text,
        )
    with cols[1]:
        st.metric(
            label="REB",
            value=fmt_value(stats.reb_season_avg),
            delta=fmt_delta(stats.reb.w5.delta),
            help=help_text,
        )
    with cols[2]:
        st.metric(
            label="AST",
            value=fmt_value(stats.ast_season_avg),
            delta=fmt_delta(stats.ast.w5.delta),
            help=help_text,
        )
    with cols[3]:
        st.metric(
            label="3P%",
            value=fmt_pct_value(stats.fg3_pct_season_avg),
            delta=fmt_pct_delta(stats.fg3_pct.w5.delta),
            help=help_text,
        )
    with cols[4]:
        st.metric(
            label="MIN",
            value=fmt_value(stats.min_season_avg),
            delta=fmt_delta(stats.min.w5.delta),
            help=help_text,
        )


def render_player_view(player_id: int, season: str, year: int) -> None:
    """Render the header, bio, and metric row for the selected player."""
    profile = _find_player(player_id, year)
    if profile is None:
        st.warning("Player not found in the selected draft class.")
        return

    try:
        agg = cache.cached_aggregated_stats(player_id, season)
    except httpx.HTTPError as exc:
        st.error(f"Failed to load stats: {exc}")
        return

    _render_header(profile, agg.stats)
    _render_bio_row(profile, season)
    _render_metrics_row(agg.stats)
    st.divider()
    render_narrative_panel(player_id, season, year)
