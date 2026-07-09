"""Unit tests for analyze_trends pure function."""

import pytest

from backend.agent.trend_analysis import analyze_trends
from backend.core.types import TrendDirection
from backend.schemas.stats import AggregatedStats, RollingWindow, StatWindows


def _rw(
    *,
    window_size: int = 5,
    avg: float | None = 20.0,
    delta: float | None = 0.0,
    direction: TrendDirection = "stable",
    games_played: int = 5,
) -> RollingWindow:
    return RollingWindow(
        window_size=window_size,
        avg=avg,
        delta=delta,
        direction=direction,
        games_played=games_played,
    )


def _empty_window(window_size: int) -> RollingWindow:
    return _rw(
        window_size=window_size,
        avg=None,
        delta=None,
        direction="stable",
        games_played=0,
    )


def _empty_stat_windows() -> StatWindows:
    return StatWindows(
        w5=_empty_window(5),
        w10=_empty_window(10),
        w15=_empty_window(15),
    )


def _base_stats(games_played: int = 10) -> AggregatedStats:
    return AggregatedStats(
        player_id=1,
        season="2024-25",
        total_games=games_played,
        games_played=games_played,
        pts=_empty_stat_windows(),
        ast=_empty_stat_windows(),
        reb=_empty_stat_windows(),
        fg_pct=_empty_stat_windows(),
        fg3_pct=_empty_stat_windows(),
        min=_empty_stat_windows(),
        pts_season_avg=None,
        ast_season_avg=None,
        reb_season_avg=None,
        fg_pct_season_avg=None,
        fg3_pct_season_avg=None,
        min_season_avg=None,
    )


class TestAnalyzeEmpty:
    def test_no_games_returns_empty_analysis(self) -> None:
        stats = _base_stats(games_played=0)
        result = analyze_trends(stats)
        assert result.signals == []
        assert result.summary == "No games played yet"
        assert result.has_significant_trends is False

    def test_all_windows_empty_returns_no_signals(self) -> None:
        stats = _base_stats(games_played=2)  # games_played > 0 but no full windows
        result = analyze_trends(stats)
        assert result.signals == []


class TestWindowSelection:
    def test_prefers_longest_populated_window(self) -> None:
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(window_size=5, avg=22.0, delta=2.0, direction="up",
                   games_played=5),
            w10=_rw(window_size=10, avg=20.0, delta=1.0, direction="stable",
                    games_played=10),
            w15=_rw(window_size=15, avg=18.0, delta=0.5, direction="stable",
                    games_played=15),
        )
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.window == 15

    def test_falls_back_to_w5_when_w10_underpopulated(self) -> None:
        stats = _base_stats()
        # w10 has only 5 played < 6 (60% of 10)
        stats.pts = StatWindows(
            w5=_rw(window_size=5, avg=22.0, delta=2.0, direction="up",
                   games_played=5),
            w10=_rw(window_size=10, avg=21.0, delta=1.0, direction="stable",
                    games_played=5),
            w15=_empty_window(15),
        )
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.window == 5

    def test_none_avg_skipped(self) -> None:
        stats = _base_stats()
        # w15 has games_played=15 but avg=None → must skip
        stats.pts = StatWindows(
            w5=_rw(window_size=5, avg=20.0, delta=0.0, direction="stable",
                   games_played=5),
            w10=_empty_window(10),
            w15=_rw(window_size=15, avg=None, delta=None, direction="stable",
                    games_played=15),
        )
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.window == 5


class TestStrengthClassification:
    def test_strong_improvement_for_counting_stat(self) -> None:
        # +5.0 PTS on 20 season_avg → ratio 0.25 → strong
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(avg=25.0, delta=5.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.strength == "strong"

    def test_moderate_improvement_for_counting_stat(self) -> None:
        # +2.0 PTS on 20 season_avg → ratio 0.10 → moderate
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(avg=22.0, delta=2.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.strength == "moderate"

    def test_percentage_uses_absolute_pp_threshold(self) -> None:
        # 3P% delta +0.06 (6pp) → strong, regardless of season_avg
        stats = _base_stats()
        stats.fg3_pct = StatWindows(
            w5=_rw(avg=0.41, delta=0.06, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.fg3_pct_season_avg = 0.35
        result = analyze_trends(stats)
        fg3 = next(s for s in result.signals if s.stat == "fg3_pct")
        assert fg3.strength == "strong"

    def test_missing_season_avg_falls_back_to_weak(self) -> None:
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(avg=22.0, delta=2.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = None  # no baseline
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.strength == "weak"


class TestDisplayFormat:
    def test_counting_stat_display_format(self) -> None:
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_empty_window(5),
            w10=_rw(window_size=10, avg=23.4, delta=3.4, direction="up",
                    games_played=10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.display == "+3.4 PTS last 10G"

    def test_negative_delta_has_sign(self) -> None:
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(avg=17.5, delta=-2.5, direction="down", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        result = analyze_trends(stats)
        pts = next(s for s in result.signals if s.stat == "pts")
        assert pts.display == "-2.5 PTS last 5G"

    def test_percentage_display_uses_pp_suffix(self) -> None:
        stats = _base_stats()
        stats.fg3_pct = StatWindows(
            w5=_rw(avg=0.384, delta=0.034, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.fg3_pct_season_avg = 0.35
        result = analyze_trends(stats)
        fg3 = next(s for s in result.signals if s.stat == "fg3_pct")
        assert fg3.display == "+3.4pp 3P% last 5G"


class TestRanking:
    def test_all_stable_no_significant_flag(self) -> None:
        stats = _base_stats()
        for name in ("pts", "ast", "reb", "fg_pct", "fg3_pct", "min"):
            setattr(
                stats,
                name,
                StatWindows(
                    w5=_rw(avg=10.0, delta=0.1, direction="stable",
                           games_played=5),
                    w10=_empty_window(10),
                    w15=_empty_window(15),
                ),
            )
        result = analyze_trends(stats)
        assert result.has_significant_trends is False
        assert len(result.signals) == 6  # every stat reported

    def test_strong_ranks_before_moderate(self) -> None:
        stats = _base_stats()
        # PTS +2.0 moderate (season_avg 20 → ratio 0.10)
        stats.pts = StatWindows(
            w5=_rw(avg=22.0, delta=2.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        # REB +2.0 strong (season_avg 5 → ratio 0.40)
        stats.reb = StatWindows(
            w5=_rw(avg=7.0, delta=2.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.reb_season_avg = 5.0
        result = analyze_trends(stats)
        assert result.signals[0].stat == "reb"
        assert result.signals[0].rank == 1
        assert result.signals[0].strength == "strong"

    def test_tie_broken_by_stat_priority(self) -> None:
        stats = _base_stats()
        # PTS and AST both weak stable — priority puts PTS first
        stats.pts = StatWindows(
            w5=_rw(avg=20.0, delta=0.5, direction="stable", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        stats.ast = StatWindows(
            w5=_rw(avg=5.0, delta=0.1, direction="stable", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.ast_season_avg = 5.0
        result = analyze_trends(stats)
        pts_rank = next(s for s in result.signals if s.stat == "pts").rank
        ast_rank = next(s for s in result.signals if s.stat == "ast").rank
        assert pts_rank < ast_rank


class TestSummary:
    def test_summary_reflects_top_signals(self) -> None:
        stats = _base_stats()
        stats.pts = StatWindows(
            w5=_rw(avg=25.0, delta=5.0, direction="up", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.pts_season_avg = 20.0
        stats.fg3_pct = StatWindows(
            w5=_rw(avg=0.30, delta=-0.05, direction="down", games_played=5),
            w10=_empty_window(10),
            w15=_empty_window(15),
        )
        stats.fg3_pct_season_avg = 0.35
        result = analyze_trends(stats)
        assert "PTS up" in result.summary
        assert "3P% down" in result.summary


