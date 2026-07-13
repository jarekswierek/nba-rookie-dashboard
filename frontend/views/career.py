"""Career Progression tab: stacked horizontal bar chart by season."""

import httpx
import streamlit as st

from frontend import cache
from frontend.charts import build_career_chart


def render_career_tab(player_id: int) -> None:
    """Render the stacked horizontal bar chart for the player's career."""
    with st.spinner("Loading career data…"):
        try:
            response = cache.cached_career_stats(player_id)
        except httpx.HTTPError as exc:
            st.error(f"Failed to load career stats: {exc}")
            return

    seasons = response.seasons
    if not seasons:
        st.info("No career statistics available.")
        return

    fig = build_career_chart(
        season_labels=[s.season_label for s in seasons],
        pts=[s.pts for s in seasons],
        reb=[s.reb for s in seasons],
        ast=[s.ast for s in seasons],
        career_avg_total=response.career_avg_total,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Regular season averages per game"
        " · Dotted line = career average total production"
    )
