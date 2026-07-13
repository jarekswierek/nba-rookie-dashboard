"""Draft Class Overview tab: stacked horizontal bar chart."""

from statistics import fmean

import httpx
import streamlit as st

from frontend import cache
from frontend.charts import build_draft_class_chart


def render_draft_class_tab(year: int, season: str) -> None:
    """Render the stacked horizontal bar chart for the selected draft class."""
    with st.spinner("Loading draft class data…"):
        try:
            draft_class = cache.cached_draft_class(year)
            season_avgs = cache.cached_season_averages(season)
        except httpx.HTTPError as exc:
            st.error(f"Failed to load draft class data: {exc}")
            return

    avgs_by_id = {p.player_id: p for p in season_avgs.players}

    players_r1 = sorted(draft_class.round_1, key=lambda p: p.overall_pick)
    players_r2 = sorted(draft_class.round_2, key=lambda p: p.overall_pick)
    ordered = players_r1 + players_r2

    labels: list[str] = []
    pts_vals: list[float] = []
    reb_vals: list[float] = []
    ast_vals: list[float] = []

    for p in ordered:
        avg = avgs_by_id.get(p.player_id)
        team = p.team_abbreviation or "—"
        labels.append(f"#{p.overall_pick} {p.full_name} ({team})")
        pts_vals.append(avg.pts if avg else 0.0)
        reb_vals.append(avg.reb if avg else 0.0)
        ast_vals.append(avg.ast if avg else 0.0)

    if not labels:
        st.info("No data available for this draft class.")
        return

    active = [
        avgs_by_id[p.player_id] for p in ordered if p.player_id in avgs_by_id
    ]
    class_avg = fmean(p.pts + p.reb + p.ast for p in active) if active else 0.0

    fig = build_draft_class_chart(
        player_labels=labels,
        pts=pts_vals,
        reb=reb_vals,
        ast=ast_vals,
        round_boundary_index=len(players_r1),
        class_avg_total=class_avg,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Season averages per game · Dotted line = rookie class average production"
    )
