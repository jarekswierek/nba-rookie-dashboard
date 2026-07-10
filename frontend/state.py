"""Streamlit ``st.session_state`` key constants and initialisation.

Centralising the keys prevents typo-driven bugs where two widgets read from
slightly different strings and quietly desync. All widget state that must persist
across reruns goes through here.
"""

import streamlit as st

# Currently selected draft year (int, e.g. 2024).
KEY_YEAR = "selected_year"

# Currently selected player_id (int) or None when nothing chosen yet.
KEY_PLAYER = "selected_player_id"

# Per-round radio widget keys. Streamlit needs distinct keys per widget,
# and the sync logic clears the opposite round when one is picked.
KEY_RADIO_R1 = "radio_round_1"
KEY_RADIO_R2 = "radio_round_2"


def init_state(default_year: int) -> None:
    """Populate default values on the first render of the session."""
    if KEY_YEAR not in st.session_state:
        st.session_state[KEY_YEAR] = default_year
    if KEY_PLAYER not in st.session_state:
        st.session_state[KEY_PLAYER] = None
