"""NBA Rookie Dashboard — Streamlit entry point."""

import streamlit as st

_PAGE_TITLE = "NBA Rookie Dashboard"
_PAGE_ICON = "🏀"

st.set_page_config(
    page_title=_PAGE_TITLE,
    page_icon=_PAGE_ICON,
    layout="wide",
)


def _render_sidebar() -> None:
    """Draft class selector and player picker — placeholder until wired."""
    with st.sidebar:
        st.header("Draft Class")
        st.caption("Season and player selection coming soon.")


def _render_main() -> None:
    """Player metrics, tabs, and AI narrative — placeholder until wired."""
    st.title(f"{_PAGE_ICON} {_PAGE_TITLE}")
    st.caption("AI-powered analytics for NBA rookies.")
    st.info(
        "Select a player from the sidebar to see stats, trends, and an "
        "AI-generated narrative."
    )


def main() -> None:
    _render_sidebar()
    _render_main()


main()
