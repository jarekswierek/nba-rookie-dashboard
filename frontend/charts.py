"""Pure chart builders and rolling-average helper.

Kept free of Streamlit so figures can be rendered from any transport (HTML
export, notebook, tests). ``rolling_average`` mirrors the backend convention of
skipping DNP-flagged values so the frontend line matches the aggregated-stats
rolling deltas shown in the metric row.
"""

from statistics import fmean
from typing import Final

import plotly.graph_objects as go

# Fixed rolling window matches the backlog mockup ("5G avg").
ROLLING_WINDOW: Final[int] = 5

# Chart heights kept small so a 2x2 grid fits above the fold on 1080p.
_CHART_HEIGHT_PX: Final[int] = 320

# Per-stat colours from the design mockup. Bars use lower opacity so the
# rolling line reads as the primary visual element.
COLOR_PTS_BAR: Final[str] = "#1f77b4"  # blue
COLOR_PTS_LINE: Final[str] = "#d62728"  # red
COLOR_3P_BAR: Final[str] = "#2ca02c"  # green
COLOR_3P_LINE: Final[str] = "#2ca02c"  # green
COLOR_MIN_AREA: Final[str] = "#1f77b4"  # blue
COLOR_REB_BAR: Final[str] = "#9467bd"  # purple
COLOR_REB_LINE: Final[str] = "#9467bd"  # purple

_BAR_OPACITY: Final[float] = 0.6

# Stacked chart colours shared by Draft Class Overview and Career Progression.
COLOR_PTS_STACK: Final[str] = "#2a9d8f"  # teal
COLOR_REB_STACK: Final[str] = "#e9c46a"  # amber
COLOR_AST_STACK: Final[str] = "#e76f51"  # red

_STACK_CHART_MIN_HEIGHT_PX: Final[int] = 400
_STACK_CHART_PX_PER_ROW: Final[int] = 24


def rolling_average(
    values: list[float | None], window: int = ROLLING_WINDOW
) -> list[float | None]:
    """Return the trailing rolling mean of *values*, excluding None entries.

    Position N in the output is the average of the last ``window`` non-None
    entries at or before position N. Positions with fewer than ``window`` non-
    None entries in their trailing slice return None so the line does not
    extrapolate.
    """
    result: list[float | None] = []
    for i in range(len(values)):
        seen: list[float] = []
        j = i
        while j >= 0 and len(seen) < window:
            value = values[j]
            if value is not None:
                seen.append(value)
            j -= 1
        if len(seen) < window:
            result.append(None)
        else:
            result.append(fmean(seen))
    return result


def _base_layout(y_axis_title: str, is_percentage: bool) -> dict[str, object]:
    tickformat = ".0%" if is_percentage else None
    return {
        "height": _CHART_HEIGHT_PX,
        "margin": {"l": 40, "r": 10, "t": 40, "b": 40},
        "xaxis_title": "Game",
        "yaxis_title": y_axis_title,
        "yaxis_tickformat": tickformat,
        "hovermode": "x unified",
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    }


def build_bar_with_rolling(
    game_numbers: list[int],
    values: list[float | None],
    stat_name: str,
    y_axis_title: str,
    bar_color: str,
    line_color: str,
    is_percentage: bool = False,
) -> go.Figure:
    """Bar of per-game values plus a rolling-average line overlay."""
    rolling = rolling_average(values)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=game_numbers,
            y=values,
            name=stat_name,
            marker={"color": bar_color},
            opacity=_BAR_OPACITY,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=game_numbers,
            y=rolling,
            name=f"{ROLLING_WINDOW}G avg",
            mode="lines",
            line={"color": line_color, "width": 2.5},
            connectgaps=False,
        )
    )
    fig.update_layout(**_base_layout(y_axis_title, is_percentage))
    return fig


def build_area_with_gaps(
    game_numbers: list[int],
    values: list[float | None],
    stat_name: str,
    y_axis_title: str,
    area_color: str,
) -> go.Figure:
    """Filled area chart where None entries render as visible gaps."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=game_numbers,
            y=values,
            name=stat_name,
            mode="lines",
            line={"color": area_color, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.25)",
            connectgaps=False,
        )
    )
    fig.update_layout(**_base_layout(y_axis_title, is_percentage=False))
    fig.update_layout(showlegend=False)
    return fig


def _stacked_bar_layout(
    n_rows: int,
    x_axis_title: str,
    left_margin: int,
) -> dict[str, object]:
    height = max(
        _STACK_CHART_MIN_HEIGHT_PX,
        n_rows * _STACK_CHART_PX_PER_ROW + 80,
    )
    return {
        "barmode": "stack",
        "height": height,
        "margin": {"l": left_margin, "r": 20, "t": 40, "b": 40},
        "xaxis_title": x_axis_title,
        "hovermode": "y unified",
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    }


def build_draft_class_chart(
    player_labels: list[str],
    pts: list[float],
    reb: list[float],
    ast: list[float],
    round_boundary_index: int | None,
    class_avg_total: float,
) -> go.Figure:
    """Stacked horizontal bar chart for all draft class players.

    Players are passed sorted ascending by overall pick; ``autorange='reversed'``
    puts pick #1 at the top. ``round_boundary_index`` is the list index of the
    first Round 2 player; a dashed shape is drawn between the rounds.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=player_labels,
            x=pts,
            name="PTS",
            orientation="h",
            marker_color=COLOR_PTS_STACK,
        )
    )
    fig.add_trace(
        go.Bar(
            y=player_labels,
            x=reb,
            name="REB",
            orientation="h",
            marker_color=COLOR_REB_STACK,
        )
    )
    fig.add_trace(
        go.Bar(
            y=player_labels,
            x=ast,
            name="AST",
            orientation="h",
            marker_color=COLOR_AST_STACK,
        )
    )

    fig.add_vline(
        x=class_avg_total,
        line_dash="dot",
        line_color="rgba(80,80,80,0.6)",
        annotation_text=f"Class avg {class_avg_total:.1f}",
        annotation_position="top right",
        annotation_font_size=11,
    )

    n = len(player_labels)
    if round_boundary_index is not None and 0 < round_boundary_index < n:
        # Separator between R1 and R2; y-coordinates on a categorical axis
        # map 0 → first category, N-1 → last. With autorange='reversed' the
        # first category is at the visual top, so the separator sits at
        # round_boundary_index - 0.5 (between the last R1 and first R2 row).
        fig.add_shape(
            type="line",
            xref="paper",
            x0=0,
            x1=1,
            yref="y",
            y0=round_boundary_index - 0.5,
            y1=round_boundary_index - 0.5,
            line={"color": "rgba(120,120,120,0.4)", "width": 1, "dash": "dash"},
        )

    layout = _stacked_bar_layout(
        n_rows=n,
        x_axis_title="PTS + REB + AST (per game)",
        left_margin=220,
    )
    layout["yaxis"] = {"autorange": "reversed"}
    fig.update_layout(**layout)
    return fig


def build_career_chart(
    season_labels: list[str],
    pts: list[float],
    reb: list[float],
    ast: list[float],
    career_avg_total: float,
) -> go.Figure:
    """Stacked horizontal bar chart for a player's career progression.

    Seasons are passed sorted ascending so the default Plotly ordering (index 0
    at the bottom) places the oldest season at the bottom and the most recent
    season at the top — matching the mockup.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=season_labels,
            x=pts,
            name="PTS",
            orientation="h",
            marker_color=COLOR_PTS_STACK,
        )
    )
    fig.add_trace(
        go.Bar(
            y=season_labels,
            x=reb,
            name="REB",
            orientation="h",
            marker_color=COLOR_REB_STACK,
        )
    )
    fig.add_trace(
        go.Bar(
            y=season_labels,
            x=ast,
            name="AST",
            orientation="h",
            marker_color=COLOR_AST_STACK,
        )
    )

    fig.add_vline(
        x=career_avg_total,
        line_dash="dot",
        line_color="rgba(80,80,80,0.6)",
        annotation_text=f"Career avg {career_avg_total:.1f}",
        annotation_position="top right",
        annotation_font_size=11,
    )

    layout = _stacked_bar_layout(
        n_rows=len(season_labels),
        x_axis_title="PTS + REB + AST (per game)",
        left_margin=160,
    )
    fig.update_layout(**layout)
    return fig
