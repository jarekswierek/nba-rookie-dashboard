"""Sidebar: season badge, draft year selector, and player picker."""

import httpx
import streamlit as st

from frontend import api_client, state
from shared.schemas.draft import DraftClass, DraftPlayer
from shared.schemas.season import DraftYearRange, SeasonStatus
from shared.schemas.season_averages import SeasonAveragesResponse

_TTL_YEAR_RANGE_SECONDS = 3600
_TTL_SEASON_STATUS_SECONDS = 60
_TTL_DRAFT_CLASS_SECONDS = 300
_TTL_SEASON_AVERAGES_SECONDS = 300


@st.cache_data(ttl=_TTL_YEAR_RANGE_SECONDS)
def _cached_year_range() -> DraftYearRange:
    return api_client.get_draft_year_range()


@st.cache_data(ttl=_TTL_SEASON_STATUS_SECONDS)
def _cached_season_status() -> SeasonStatus:
    return api_client.get_season_status()


@st.cache_data(ttl=_TTL_DRAFT_CLASS_SECONDS)
def _cached_draft_class(year: int) -> DraftClass:
    return api_client.get_draft_class(year)


@st.cache_data(ttl=_TTL_SEASON_AVERAGES_SECONDS)
def _cached_season_averages(season: str) -> SeasonAveragesResponse:
    return api_client.get_season_averages(season)


def _season_string(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"


def _format_year(year: int, rookie_year: int) -> str:
    label = _season_string(year)
    if year == rookie_year:
        label += " (current rookies)"
    return label


def _format_player(player: DraftPlayer, ppg_by_player: dict[int, float]) -> str:
    team = player.team_abbreviation or player.team_at_draft or "—"
    ppg = ppg_by_player.get(player.player_id)
    ppg_text = f" · {ppg:.1f} ppg" if ppg is not None else ""
    return f"#{player.overall_pick} {player.full_name} ({team}){ppg_text}"


def _render_season_badge(status: SeasonStatus) -> None:
    if status.is_active:
        st.success(f"● {status.status_label}")
    else:
        st.warning(f"○ {status.status_label}")


def _on_year_change() -> None:
    """Clear player selection when the user picks a different draft class."""
    st.session_state[state.KEY_PLAYER] = None
    st.session_state[state.KEY_RADIO_R1] = None
    st.session_state[state.KEY_RADIO_R2] = None


def _on_round_1_change() -> None:
    """Round-1 selection wins — clear round-2 and lift into unified key."""
    selected = st.session_state.get(state.KEY_RADIO_R1)
    if selected is not None:
        st.session_state[state.KEY_RADIO_R2] = None
        st.session_state[state.KEY_PLAYER] = selected.player_id


def _on_round_2_change() -> None:
    """Round-2 selection wins — clear round-1 and lift into unified key."""
    selected = st.session_state.get(state.KEY_RADIO_R2)
    if selected is not None:
        st.session_state[state.KEY_RADIO_R1] = None
        st.session_state[state.KEY_PLAYER] = selected.player_id


def _render_year_selector(year_range: DraftYearRange) -> None:
    years = list(range(year_range.max_year, year_range.min_year - 1, -1))
    st.selectbox(
        "Draft Class",
        options=years,
        format_func=lambda y: _format_year(y, year_range.default_year),
        key=state.KEY_YEAR,
        on_change=_on_year_change,
    )


def _render_player_picker(
    draft_class: DraftClass, ppg_by_player: dict[int, float]
) -> None:
    st.markdown(
        f"**{len(draft_class.players)} rookies in {draft_class.season}**"
    )
    st.markdown("**— Round 1 —**")
    st.radio(
        "Round 1 players",
        options=draft_class.round_1,
        format_func=lambda p: _format_player(p, ppg_by_player),
        key=state.KEY_RADIO_R1,
        on_change=_on_round_1_change,
        label_visibility="collapsed",
        index=None,
    )
    st.markdown("**— Round 2 —**")
    st.radio(
        "Round 2 players",
        options=draft_class.round_2,
        format_func=lambda p: _format_player(p, ppg_by_player),
        key=state.KEY_RADIO_R2,
        on_change=_on_round_2_change,
        label_visibility="collapsed",
        index=None,
    )


def _build_ppg_map(
    averages: SeasonAveragesResponse | None,
) -> dict[int, float]:
    if averages is None:
        return {}
    return {p.player_id: p.pts for p in averages.players}


def render_sidebar() -> None:
    """Render the full sidebar and keep session state in sync."""
    with st.sidebar:
        st.header("Draft Class")

        try:
            year_range = _cached_year_range()
            status = _cached_season_status()
        except httpx.HTTPError as exc:
            st.error(f"Backend unreachable: {exc}")
            return

        state.init_state(year_range.default_year)
        _render_season_badge(status)
        _render_year_selector(year_range)

        selected_year: int = st.session_state[state.KEY_YEAR]

        try:
            draft_class = _cached_draft_class(selected_year)
        except httpx.HTTPError as exc:
            st.error(f"Failed to load draft class: {exc}")
            return

        # Season averages are best-effort — sidebar still works without ppg.
        averages: SeasonAveragesResponse | None
        try:
            averages = _cached_season_averages(draft_class.season)
        except httpx.HTTPError:
            averages = None

        _render_player_picker(draft_class, _build_ppg_map(averages))
