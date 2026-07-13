"""Constants shared across backend modules.

Values used from more than one file live here so a change updates a single source
of truth. File-local values stay as module-level ``_CONSTANT`` at the top of
their own file.
"""

# Regex matching the NBA season format used by nba_api and validated on
# every season-scoped query parameter (e.g. "2024-25").
SEASON_PATTERN = r"^\d{4}-\d{2}$"

# Oldest draft year exposed to callers. Earlier years have thin nba_api
# coverage for rookie statistics — surfacing them would produce confusing
# empty responses.
DRAFT_YEAR_MIN = 2000

# SSE warning codes emitted by the narrative endpoint on degraded paths.
# Kept here rather than in either module because backend emits them and
# frontend maps them to user-facing messages — the string values are the
# wire contract.
NARRATIVE_WARNING_CACHED_FALLBACK = "cached_fallback"
NARRATIVE_WARNING_UNAVAILABLE = "unavailable"
NARRATIVE_WARNING_DERIVED_METADATA = "derived_metadata"
NARRATIVE_WARNING_STREAM_INTERRUPTED = "stream_interrupted"
