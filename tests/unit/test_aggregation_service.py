"""Unit tests for aggregation_service pure functions."""

import datetime

import pytest

from backend.data.aggregation_service import (
    _compute_direction,
    aggregate_stats,
)
from shared.schemas.stats import GameLog

_SEASON = "2024-25"
_PLAYER_ID = 12345


def _log(
    game_number: int,
    *,
    pts: float | None = 20.0,
    ast: float | None = 5.0,
    reb: float | None = 6.0,
    fg_pct: float | None = 0.45,
    fg3_pct: float | None = 0.35,
    min: float | None = 30.0,
) -> GameLog:
    """Build a GameLog with sensible defaults for a played game.

    Set ``min=None`` to mark the game as DNP; all other stats will still
    populate the field but ``is_dnp`` becomes True and aggregate_stats will
    exclude the row.
    """
    return GameLog(
        game_id=f"g{game_number:04d}",
        game_date=datetime.date(2025, 1, 1) + datetime.timedelta(days=game_number),
        matchup="NYK vs BOS",
        game_number=game_number,
        pts=pts,
        ast=ast,
        reb=reb,
        fg_pct=fg_pct,
        fg3_pct=fg3_pct,
        min=min,
    )


class TestComputeDirection:
    def test_none_delta_is_stable(self) -> None:
        assert _compute_direction(None, "pts") == "stable"

    def test_delta_above_threshold_is_up(self) -> None:
        assert _compute_direction(1.5, "pts") == "up"

    def test_delta_below_negative_threshold_is_down(self) -> None:
        assert _compute_direction(-1.5, "pts") == "down"

    def test_delta_at_threshold_is_stable(self) -> None:
        assert _compute_direction(1.0, "pts") == "stable"
        assert _compute_direction(-1.0, "pts") == "stable"

    def test_delta_within_deadband_is_stable(self) -> None:
        assert _compute_direction(0.5, "pts") == "stable"

    def test_fg_pct_threshold_is_smaller(self) -> None:
        # fg_pct threshold is 0.02 — 0.03 crosses it
        assert _compute_direction(0.03, "fg_pct") == "up"
        assert _compute_direction(0.01, "fg_pct") == "stable"


class TestAggregateStatsEmpty:
    def test_empty_logs_produces_empty_windows(self) -> None:
        stats = aggregate_stats([], _PLAYER_ID, _SEASON)
        assert stats.total_games == 0
        assert stats.games_played == 0
        assert stats.pts.w5.avg is None
        assert stats.pts.w5.delta is None
        assert stats.pts.w5.direction == "stable"
        assert stats.pts.w5.games_played == 0
        assert stats.pts_season_avg is None


class TestAggregateStatsAllDnp:
    def test_all_dnp_yields_zero_played(self) -> None:
        logs = [_log(i, min=None) for i in range(1, 11)]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.total_games == 10
        assert stats.games_played == 0
        assert stats.pts.w5.avg is None
        assert stats.pts_season_avg is None


class TestAggregateStatsFewGames:
    def test_three_games_no_window_populated(self) -> None:
        logs = [_log(i, pts=20.0) for i in range(1, 4)]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.games_played == 3
        # Fewer than 5 played — all windows empty
        assert stats.pts.w5.avg is None
        assert stats.pts.w5.games_played == 3
        # Season average is still populated even without a full window
        assert stats.pts_season_avg == 20.0


class TestAggregateStatsBetweenNAnd2N:
    def test_seven_games_w5_avg_populated_no_delta(self) -> None:
        # Games 1..5: pts=10, games 6..7: pts=20 — last 5 = [10, 10, 10, 20, 20]
        logs = [_log(i, pts=10.0) for i in range(1, 6)] + [
            _log(i, pts=20.0) for i in range(6, 8)
        ]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.games_played == 7
        assert stats.pts.w5.avg == pytest.approx(14.0)
        assert stats.pts.w5.delta is None
        assert stats.pts.w5.direction == "stable"
        assert stats.pts.w5.games_played == 5
        # w10 needs 10 games — still empty
        assert stats.pts.w10.avg is None


class TestAggregateStatsFullDelta:
    def test_ten_games_w5_delta_computed(self) -> None:
        # First 5: pts=10, last 5: pts=20 → w5 avg=20, prev=10, delta=+10 → up
        logs = [_log(i, pts=10.0) for i in range(1, 6)] + [
            _log(i, pts=20.0) for i in range(6, 11)
        ]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.pts.w5.avg == pytest.approx(20.0)
        assert stats.pts.w5.delta == pytest.approx(10.0)
        assert stats.pts.w5.direction == "up"
        assert stats.pts.w5.games_played == 5

    def test_declining_trend_yields_down(self) -> None:
        # First 5: pts=25, last 5: pts=15 → delta=-10 → down
        logs = [_log(i, pts=25.0) for i in range(1, 6)] + [
            _log(i, pts=15.0) for i in range(6, 11)
        ]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.pts.w5.delta == pytest.approx(-10.0)
        assert stats.pts.w5.direction == "down"

    def test_small_delta_stays_stable(self) -> None:
        # First 5: pts=20, last 5: pts=20.5 → delta=0.5 (under PTS threshold 1.0)
        logs = [_log(i, pts=20.0) for i in range(1, 6)] + [
            _log(i, pts=20.5) for i in range(6, 11)
        ]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.pts.w5.direction == "stable"


class TestAggregateStatsDnpInMiddle:
    def test_dnp_games_excluded_from_windows(self) -> None:
        # 12 total, games 6-8 are DNP → 9 played
        # Played sequence PTS: [10, 10, 10, 10, 10, 20, 20, 20, 20]
        # Last 5 played PTS: [10, 20, 20, 20, 20] → avg=18
        logs = []
        for i in range(1, 6):
            logs.append(_log(i, pts=10.0))
        for i in range(6, 9):
            logs.append(_log(i, min=None))
        for i in range(9, 13):
            logs.append(_log(i, pts=20.0))

        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.total_games == 12
        assert stats.games_played == 9
        assert stats.pts.w5.avg == pytest.approx(18.0)
        assert stats.pts.w5.games_played == 5


class TestAggregateStatsNoneValueMidSeason:
    def test_none_fg3_pct_excluded_but_pts_counted(self) -> None:
        # 10 played games. Games 3, 6, 9 have fg3_pct=None (no 3PT attempts)
        # PTS uses all 10 → w5 delta from played games
        # fg3_pct uses 7 non-None values — fewer than 10, so w10 avg is None
        logs = []
        for i in range(1, 11):
            logs.append(
                _log(i, pts=20.0, fg3_pct=None if i in {3, 6, 9} else 0.35)
            )

        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        # PTS: 10 values → w5 populated with avg and delta
        assert stats.pts.w5.avg == pytest.approx(20.0)
        assert stats.pts.w5.games_played == 5
        # fg3_pct: 7 values → w5 populated (7 >= 5), w10 empty (7 < 10)
        assert stats.fg3_pct.w5.avg == pytest.approx(0.35)
        assert stats.fg3_pct.w5.games_played == 5
        assert stats.fg3_pct.w10.avg is None
        assert stats.fg3_pct.w10.games_played == 7


class TestAggregateStatsSeasonAverages:
    def test_season_avg_over_played_games_only(self) -> None:
        # 3 played games with pts=10, 20, 30 → mean = 20
        # Plus 2 DNP games — should be ignored
        logs = [_log(1, pts=10.0), _log(2, pts=20.0), _log(3, pts=30.0)]
        logs.extend([_log(4, min=None), _log(5, min=None)])
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.games_played == 3
        assert stats.pts_season_avg == pytest.approx(20.0)

    def test_season_avg_ignores_none_values(self) -> None:
        # 3 played games, only 2 have fg3_pct
        logs = [
            _log(1, fg3_pct=0.30),
            _log(2, fg3_pct=None),
            _log(3, fg3_pct=0.40),
        ]
        stats = aggregate_stats(logs, _PLAYER_ID, _SEASON)
        assert stats.fg3_pct_season_avg == pytest.approx(0.35)
