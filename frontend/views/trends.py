"""Trends tab: four Plotly charts in a 2x2 grid."""

import httpx
import streamlit as st

from frontend import cache
from frontend.charts import (
    COLOR_3P_BAR,
    COLOR_3P_LINE,
    COLOR_MIN_AREA,
    COLOR_PTS_BAR,
    COLOR_PTS_LINE,
    COLOR_REB_BAR,
    COLOR_REB_LINE,
    build_area_with_gaps,
    build_bar_with_rolling,
)
from shared.schemas.stats import GameLog


def _pts_values(logs: list[GameLog]) -> list[float | None]:
    return [None if log.is_dnp else log.pts for log in logs]


def _reb_values(logs: list[GameLog]) -> list[float | None]:
    return [None if log.is_dnp else log.reb for log in logs]


def _fg3_pct_values(logs: list[GameLog]) -> list[float | None]:
    # fg3_pct is None both for DNPs and games with zero 3PT attempts;
    # either way the position renders as a gap.
    return [None if log.is_dnp else log.fg3_pct for log in logs]


def _min_values(logs: list[GameLog]) -> list[float | None]:
    return [log.min for log in logs]


def render_trends_tab(player_id: int, season: str) -> None:
    """Render the four progression charts for the selected player."""
    with st.spinner("Loading game logs…"):
        try:
            response = cache.cached_game_logs(player_id, season)
        except httpx.HTTPError as exc:
            st.error(f"Failed to load game logs: {exc}")
            return

    logs = response.game_logs
    if not logs:
        st.info("No games played yet this season.")
        return

    game_numbers = [log.game_number for log in logs]

    fig_pts = build_bar_with_rolling(
        game_numbers=game_numbers,
        values=_pts_values(logs),
        stat_name="PTS",
        y_axis_title="Points",
        bar_color=COLOR_PTS_BAR,
        line_color=COLOR_PTS_LINE,
    )
    fig_3p = build_bar_with_rolling(
        game_numbers=game_numbers,
        values=_fg3_pct_values(logs),
        stat_name="3P%",
        y_axis_title="3-point %",
        bar_color=COLOR_3P_BAR,
        line_color=COLOR_3P_LINE,
        is_percentage=True,
    )
    fig_min = build_area_with_gaps(
        game_numbers=game_numbers,
        values=_min_values(logs),
        stat_name="MIN",
        y_axis_title="Minutes",
        area_color=COLOR_MIN_AREA,
    )
    fig_reb = build_bar_with_rolling(
        game_numbers=game_numbers,
        values=_reb_values(logs),
        stat_name="REB",
        y_axis_title="Rebounds",
        bar_color=COLOR_REB_BAR,
        line_color=COLOR_REB_LINE,
    )

    row1_left, row1_right = st.columns(2)
    with row1_left:
        st.plotly_chart(fig_pts, use_container_width=True)
    with row1_right:
        st.plotly_chart(fig_3p, use_container_width=True)

    row2_left, row2_right = st.columns(2)
    with row2_left:
        st.plotly_chart(fig_min, use_container_width=True)
    with row2_right:
        st.plotly_chart(fig_reb, use_container_width=True)
