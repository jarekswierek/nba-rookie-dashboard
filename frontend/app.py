"""NBA Rookie Dashboard — Streamlit entry point."""

import streamlit as st

from frontend import state
from frontend.formatting import season_string
from frontend.views.player import render_player_view
from frontend.views.sidebar import render_sidebar

_PAGE_TITLE = "NBA Rookie Dashboard"
_PAGE_ICON = "🏀"

st.set_page_config(
    page_title=_PAGE_TITLE,
    page_icon=_PAGE_ICON,
    layout="wide",
)


def _render_empty_state() -> None:
    st.title(f"{_PAGE_ICON} {_PAGE_TITLE}")
    st.caption("AI-powered analytics for NBA rookies.")
    st.info(
        "Select a player from the sidebar to see stats, trends, and an "
        "AI-generated narrative."
    )


def _render_main() -> None:
    player_id = st.session_state.get(state.KEY_PLAYER)
    if player_id is None:
        _render_empty_state()
        return
    year: int = st.session_state[state.KEY_YEAR]
    render_player_view(player_id, season_string(year), year)


def main() -> None:
    render_sidebar()
    _render_main()


main()
