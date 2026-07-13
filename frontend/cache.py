"""Centralised ``@st.cache_data`` wrappers over the API client.

All views must import cached fetches from here — defining a ``@st.cache_data``
wrapper inline in a view module creates a distinct cache key (Streamlit keys by
``module + function``), which means the same data would be fetched twice per
interaction and evicted on two independent schedules.
"""

import streamlit as st

from frontend import api_client
from shared.schemas.draft import DraftClass
from shared.schemas.season import DraftYearRange, SeasonStatus
from shared.schemas.season_averages import SeasonAveragesResponse
from shared.schemas.stats import AggregatedStatsResponse

# TTLs by data volatility. Year range shifts once a season (long).
# Season status carries games-today which turns over daily (short).
# Player-scoped stats and league averages change intraday only when
# nba_api refreshes — five minutes is a reasonable compromise.
_TTL_YEAR_RANGE_SECONDS = 3600
_TTL_SEASON_STATUS_SECONDS = 60
_TTL_DRAFT_CLASS_SECONDS = 300
_TTL_SEASON_AVERAGES_SECONDS = 300
_TTL_AGGREGATED_STATS_SECONDS = 300


@st.cache_data(ttl=_TTL_YEAR_RANGE_SECONDS)
def cached_year_range() -> DraftYearRange:
    return api_client.get_draft_year_range()


@st.cache_data(ttl=_TTL_SEASON_STATUS_SECONDS)
def cached_season_status() -> SeasonStatus:
    return api_client.get_season_status()


@st.cache_data(ttl=_TTL_DRAFT_CLASS_SECONDS)
def cached_draft_class(year: int) -> DraftClass:
    return api_client.get_draft_class(year)


@st.cache_data(ttl=_TTL_SEASON_AVERAGES_SECONDS)
def cached_season_averages(season: str) -> SeasonAveragesResponse:
    return api_client.get_season_averages(season)


@st.cache_data(ttl=_TTL_AGGREGATED_STATS_SECONDS)
def cached_aggregated_stats(
    player_id: int, season: str
) -> AggregatedStatsResponse:
    return api_client.get_aggregated_stats(player_id, season)
