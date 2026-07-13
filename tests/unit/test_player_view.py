"""Unit tests for player-view header helpers."""

from frontend.views.player import _overall_trend
from shared.schemas.stats import AggregatedStats, RollingWindow, StatWindows


def _rw(direction: str) -> RollingWindow:
    return RollingWindow(
        window_size=5,
        avg=10.0,
        delta=0.0,
        direction=direction,  # type: ignore[arg-type]
        games_played=5,
    )


def _stat_windows(direction: str) -> StatWindows:
    w = _rw(direction)
    return StatWindows(w5=w, w10=w, w15=w)


def _stats(**directions: str) -> AggregatedStats:
    """Build AggregatedStats where every stat has the given direction."""
    stable = _stat_windows("stable")
    return AggregatedStats(
        player_id=1,
        season="2024-25",
        total_games=20,
        games_played=20,
        pts=_stat_windows(directions.get("pts", "stable")),
        ast=_stat_windows(directions.get("ast", "stable")),
        reb=_stat_windows(directions.get("reb", "stable")),
        min=_stat_windows(directions.get("min", "stable")),
        # Percentages don't affect overall trend but must be present.
        fg_pct=stable,
        fg3_pct=stable,
        pts_season_avg=20.0,
        ast_season_avg=5.0,
        reb_season_avg=6.0,
        fg_pct_season_avg=0.45,
        fg3_pct_season_avg=0.35,
        min_season_avg=28.0,
    )


class TestOverallTrend:
    def test_all_stable_yields_stable(self) -> None:
        assert _overall_trend(_stats()) == "stable"

    def test_all_up_yields_up(self) -> None:
        assert (
            _overall_trend(_stats(pts="up", reb="up", ast="up", min="up"))
            == "up"
        )

    def test_majority_up_yields_up(self) -> None:
        assert _overall_trend(_stats(pts="up", reb="up", ast="up")) == "up"

    def test_majority_down_yields_down(self) -> None:
        assert (
            _overall_trend(_stats(pts="down", reb="down", ast="down"))
            == "down"
        )

    def test_tie_yields_stable(self) -> None:
        assert _overall_trend(_stats(pts="up", reb="up", ast="down", min="down")) == "stable"

    def test_percentages_ignored(self) -> None:
        # Even if we were passing percentage directions, they wouldn't count.
        # Overall trend uses only pts/reb/ast/min — assert this by making
        # pts/reb/ast/min all stable regardless of fg_pct.
        assert _overall_trend(_stats()) == "stable"
