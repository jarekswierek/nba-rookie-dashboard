"""Builders for golden-dataset AggregatedStats fixtures.

Run as a script to (re)generate evals/golden_dataset.jsonl:

    python -m evals.fixtures

All examples are hand-crafted to cover the scenario space without hitting the
NBA API. For real-player snapshots use evals/seed_dataset.py.
"""

import json
import pathlib

from shared.schemas.gaps import GapEvent
from shared.schemas.stats import (
    AggregatedStats,
    PlayerProfile,
    RollingWindow,
    StatWindows,
)

_SEASON = "2024-25"
_DATASET_PATH = pathlib.Path(__file__).parent / "golden_dataset.jsonl"


# ── Primitive builders ────────────────────────────────────────────────────────


def _rw(
    size: int,
    avg: float | None = None,
    delta: float | None = None,
    direction: str = "stable",
    gp: int = 0,
) -> RollingWindow:
    return RollingWindow(
        window_size=size, avg=avg, delta=delta, direction=direction, games_played=gp
    )


def _empty_sw() -> StatWindows:
    return StatWindows(w5=_rw(5), w10=_rw(10), w15=_rw(15))


def _sw(
    w5: RollingWindow | None = None,
    w10: RollingWindow | None = None,
    w15: RollingWindow | None = None,
) -> StatWindows:
    return StatWindows(
        w5=w5 if w5 is not None else _rw(5),
        w10=w10 if w10 is not None else _rw(10),
        w15=w15 if w15 is not None else _rw(15),
    )


def _profile(
    full_name: str = "Alex Johnson",
    position: str = "SF",
    player_id: int = 99001,
) -> PlayerProfile:
    return PlayerProfile(
        player_id=player_id,
        full_name=full_name,
        position=position,
        height_cm=200.0,
        weight_kg=95.0,
        country="USA",
        team_abbreviation="NYK",
        team_at_draft="NYK",
        overall_pick=5,
        round_number=1,
        round_pick=5,
        draft_year=2024,
    )


def _stats(
    games_played: int,
    total_games: int | None = None,
    pts: StatWindows | None = None,
    ast: StatWindows | None = None,
    reb: StatWindows | None = None,
    fg_pct: StatWindows | None = None,
    fg3_pct: StatWindows | None = None,
    min_sw: StatWindows | None = None,
    pts_avg: float | None = None,
    ast_avg: float | None = None,
    reb_avg: float | None = None,
    fg_pct_avg: float | None = None,
    fg3_pct_avg: float | None = None,
    min_avg: float | None = None,
) -> AggregatedStats:
    return AggregatedStats(
        player_id=99001,
        season=_SEASON,
        total_games=total_games if total_games is not None else games_played,
        games_played=games_played,
        pts=pts or _empty_sw(),
        ast=ast or _empty_sw(),
        reb=reb or _empty_sw(),
        fg_pct=fg_pct or _empty_sw(),
        fg3_pct=fg3_pct or _empty_sw(),
        min=min_sw or _empty_sw(),
        pts_season_avg=pts_avg,
        ast_season_avg=ast_avg,
        reb_season_avg=reb_avg,
        fg_pct_season_avg=fg_pct_avg,
        fg3_pct_season_avg=fg3_pct_avg,
        min_season_avg=min_avg,
    )


def _example(
    id: str,
    description: str,
    profile: PlayerProfile,
    stats: AggregatedStats,
    gaps: list[GapEvent],
    expected_direction: str,
    confidence_min: float,
    confidence_max: float,
    must_mention_stats: list[str] | None = None,
) -> dict:
    return {
        "id": id,
        "description": description,
        "profile": profile.model_dump(mode="json"),
        "stats": stats.model_dump(mode="json"),
        "gaps": [g.model_dump(mode="json") for g in gaps],
        "expected": {
            "trend_direction": expected_direction,
            "confidence_min": confidence_min,
            "confidence_max": confidence_max,
            "must_mention_stats": must_mention_stats or [],
        },
    }


# ── Scenario builders ─────────────────────────────────────────────────────────


def _ex_zero_games() -> dict:
    return _example(
        id="zero_games",
        description="Player has not played any games this season",
        profile=_profile(),
        stats=_stats(games_played=0),
        gaps=[],
        expected_direction="stable",
        confidence_min=0.0,
        confidence_max=0.3,
    )


def _ex_five_games_early() -> dict:
    return _example(
        id="five_games_early",
        description="Only 5 games played — insufficient for rolling windows",
        profile=_profile(),
        stats=_stats(
            games_played=5,
            pts=_sw(w5=_rw(5, avg=None, gp=5)),
            pts_avg=18.0,
            reb_avg=5.0,
            ast_avg=3.0,
            min_avg=28.0,
        ),
        gaps=[],
        expected_direction="stable",
        confidence_min=0.0,
        confidence_max=0.4,
    )


def _ex_strong_up_pts_reb() -> dict:
    return _example(
        id="strong_up_pts_reb",
        description="Strong upward trend in PTS (+7) and REB (+3) over last 5",
        profile=_profile(),
        stats=_stats(
            games_played=20,
            pts=_sw(
                w5=_rw(5, avg=26.0, delta=7.0, direction="up", gp=5),
                w10=_rw(10, avg=23.0, delta=4.0, direction="up", gp=10),
            ),
            reb=_sw(
                w5=_rw(5, avg=9.0, delta=3.0, direction="up", gp=5),
                w10=_rw(10, avg=7.5, delta=1.5, direction="up", gp=10),
            ),
            ast=_sw(w5=_rw(5, avg=4.0, delta=0.2, direction="stable", gp=5)),
            min_sw=_sw(w5=_rw(5, avg=34.0, delta=1.0, direction="stable", gp=5)),
            pts_avg=22.0,
            reb_avg=7.0,
            ast_avg=3.8,
            min_avg=32.0,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.65,
        confidence_max=1.0,
        must_mention_stats=["PTS", "REB"],
    )


def _ex_strong_down_pts() -> dict:
    return _example(
        id="strong_down_pts",
        description="Sharp decline in PTS (-9) and MIN (-6) over last 5 games",
        profile=_profile(),
        stats=_stats(
            games_played=18,
            pts=_sw(
                w5=_rw(5, avg=11.0, delta=-9.0, direction="down", gp=5),
                w10=_rw(10, avg=16.0, delta=-5.0, direction="down", gp=10),
            ),
            min_sw=_sw(
                w5=_rw(5, avg=22.0, delta=-6.0, direction="down", gp=5),
                w10=_rw(10, avg=26.0, delta=-3.0, direction="down", gp=10),
            ),
            ast=_sw(w5=_rw(5, avg=2.0, delta=-0.5, direction="stable", gp=5)),
            pts_avg=17.0,
            min_avg=27.0,
        ),
        gaps=[],
        expected_direction="down",
        confidence_min=0.6,
        confidence_max=1.0,
        must_mention_stats=["PTS"],
    )


def _ex_moderate_up_3pt() -> dict:
    return _example(
        id="moderate_up_3pt",
        description="Sustained 3P% improvement (+9pp) over 15 games",
        profile=_profile(),
        stats=_stats(
            games_played=20,
            fg3_pct=_sw(
                w5=_rw(5, avg=0.42, delta=0.09, direction="up", gp=5),
                w10=_rw(10, avg=0.40, delta=0.07, direction="up", gp=10),
                w15=_rw(15, avg=0.38, delta=0.05, direction="up", gp=15),
            ),
            pts=_sw(w5=_rw(5, avg=19.0, delta=0.8, direction="stable", gp=5)),
            pts_avg=18.5,
            fg3_pct_avg=0.37,
            min_avg=30.0,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.55,
        confidence_max=1.0,
        must_mention_stats=["3P%"],
    )


def _ex_stable_consistent() -> dict:
    return _example(
        id="stable_consistent",
        description="All stats within dead-band across 15 games — no meaningful trend",
        profile=_profile(),
        stats=_stats(
            games_played=15,
            pts=_sw(
                w5=_rw(5, avg=17.5, delta=0.4, direction="stable", gp=5),
                w10=_rw(10, avg=17.2, delta=0.2, direction="stable", gp=10),
            ),
            reb=_sw(w5=_rw(5, avg=5.5, delta=0.3, direction="stable", gp=5)),
            ast=_sw(w5=_rw(5, avg=3.2, delta=0.1, direction="stable", gp=5)),
            min_sw=_sw(w5=_rw(5, avg=30.0, delta=0.5, direction="stable", gp=5)),
            pts_avg=17.3,
            reb_avg=5.4,
            ast_avg=3.1,
            min_avg=29.8,
        ),
        gaps=[],
        expected_direction="stable",
        confidence_min=0.4,
        confidence_max=0.8,
    )


def _ex_return_from_injury() -> dict:
    import datetime

    return _example(
        id="return_from_injury",
        description="Return from 4-game absence; MIN and PTS trending up in first 5 back",
        profile=_profile(),
        stats=_stats(
            games_played=16,
            total_games=20,
            pts=_sw(
                w5=_rw(5, avg=21.0, delta=5.0, direction="up", gp=5),
                w10=_rw(10, avg=19.0, delta=3.0, direction="up", gp=10),
            ),
            min_sw=_sw(
                w5=_rw(5, avg=33.0, delta=8.0, direction="up", gp=5),
                w10=_rw(10, avg=30.0, delta=5.0, direction="up", gp=10),
            ),
            pts_avg=19.0,
            min_avg=30.0,
        ),
        gaps=[
            GapEvent(
                start_game_number=12,
                end_game_number=15,
                start_date=datetime.date(2025, 2, 1),
                end_date=datetime.date(2025, 2, 8),
            )
        ],
        expected_direction="up",
        confidence_min=0.55,
        confidence_max=1.0,
        must_mention_stats=["MIN", "PTS"],
    )


def _ex_currently_absent() -> dict:
    import datetime

    return _example(
        id="currently_absent",
        description="Player has been absent for last 3 games (DNP streak ongoing)",
        profile=_profile(),
        stats=_stats(
            games_played=12,
            total_games=15,
            pts=_sw(w5=_rw(5, avg=18.0, delta=0.5, direction="stable", gp=5)),
            min_sw=_sw(w5=_rw(5, avg=29.0, delta=-1.0, direction="stable", gp=5)),
            pts_avg=18.2,
            min_avg=29.5,
        ),
        gaps=[
            GapEvent(
                start_game_number=13,
                end_game_number=15,
                start_date=datetime.date(2025, 3, 10),
                end_date=datetime.date(2025, 3, 15),
            )
        ],
        expected_direction="stable",
        confidence_min=0.0,
        confidence_max=0.5,
    )


def _ex_extended_absence() -> dict:
    import datetime

    return _example(
        id="extended_absence",
        description="Player has been out for 8+ games with no recent data",
        profile=_profile(),
        stats=_stats(
            games_played=10,
            total_games=18,
            pts=_sw(w5=_rw(5, avg=17.0, delta=0.3, direction="stable", gp=5)),
            pts_avg=17.2,
            min_avg=28.0,
        ),
        gaps=[
            GapEvent(
                start_game_number=11,
                end_game_number=18,
                start_date=datetime.date(2025, 2, 20),
                end_date=datetime.date(2025, 3, 12),
            )
        ],
        expected_direction="stable",
        confidence_min=0.0,
        confidence_max=0.4,
    )


def _ex_mixed_signals() -> dict:
    return _example(
        id="mixed_signals",
        description="PTS strongly up (+4) while MIN down (-5); model follows the scoring signal",
        profile=_profile(),
        stats=_stats(
            games_played=14,
            pts=_sw(
                w5=_rw(5, avg=22.0, delta=4.0, direction="up", gp=5),
                w10=_rw(10, avg=20.0, delta=2.5, direction="up", gp=10),
            ),
            min_sw=_sw(
                w5=_rw(5, avg=24.0, delta=-5.0, direction="down", gp=5),
                w10=_rw(10, avg=27.0, delta=-3.0, direction="down", gp=10),
            ),
            ast=_sw(w5=_rw(5, avg=3.0, delta=0.2, direction="stable", gp=5)),
            pts_avg=20.0,
            min_avg=27.0,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.3,
        confidence_max=0.75,
    )


def _ex_high_confidence_30g() -> dict:
    return _example(
        id="high_confidence_30g",
        description="30 games played, strong and sustained upward trend in all counting stats",
        profile=_profile(),
        stats=_stats(
            games_played=30,
            pts=_sw(
                w5=_rw(5, avg=28.0, delta=6.0, direction="up", gp=5),
                w10=_rw(10, avg=25.0, delta=4.0, direction="up", gp=10),
                w15=_rw(15, avg=23.0, delta=3.0, direction="up", gp=15),
            ),
            reb=_sw(
                w5=_rw(5, avg=10.0, delta=2.5, direction="up", gp=5),
                w10=_rw(10, avg=9.0, delta=1.5, direction="up", gp=10),
                w15=_rw(15, avg=8.0, delta=1.0, direction="up", gp=15),
            ),
            ast=_sw(
                w5=_rw(5, avg=6.0, delta=1.5, direction="up", gp=5),
                w10=_rw(10, avg=5.0, delta=0.8, direction="up", gp=10),
            ),
            min_sw=_sw(w5=_rw(5, avg=36.0, delta=1.0, direction="stable", gp=5)),
            pts_avg=23.0,
            reb_avg=8.5,
            ast_avg=5.0,
            min_avg=34.0,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.75,
        confidence_max=1.0,
        must_mention_stats=["PTS", "REB"],
    )


def _ex_low_confidence_8g() -> dict:
    return _example(
        id="low_confidence_8g",
        description="8 games played, modest upward trend but small sample",
        profile=_profile(),
        stats=_stats(
            games_played=8,
            pts=_sw(w5=_rw(5, avg=20.0, delta=3.5, direction="up", gp=5)),
            min_sw=_sw(w5=_rw(5, avg=30.0, delta=2.0, direction="up", gp=5)),
            pts_avg=18.5,
            min_avg=28.5,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.0,
        confidence_max=0.6,
    )


def _ex_no_3pt_shooter() -> dict:
    return _example(
        id="no_3pt_shooter",
        description="Big man — no 3PT attempts all season; trends driven by PTS/REB/MIN",
        profile=_profile(position="C"),
        stats=_stats(
            games_played=22,
            pts=_sw(
                w5=_rw(5, avg=16.0, delta=2.5, direction="up", gp=5),
                w10=_rw(10, avg=14.5, delta=1.5, direction="up", gp=10),
            ),
            reb=_sw(
                w5=_rw(5, avg=11.0, delta=2.0, direction="up", gp=5),
                w10=_rw(10, avg=9.5, delta=1.0, direction="up", gp=10),
            ),
            fg3_pct=_empty_sw(),
            pts_avg=14.0,
            reb_avg=9.0,
            fg3_pct_avg=None,
            min_avg=28.0,
        ),
        gaps=[],
        expected_direction="up",
        confidence_min=0.5,
        confidence_max=1.0,
        must_mention_stats=["PTS", "REB"],
    )


def _ex_minutes_regression() -> dict:
    return _example(
        id="minutes_regression",
        description="Rotation shrinking — MIN down (-7) and PTS down (-5) over last 5",
        profile=_profile(),
        stats=_stats(
            games_played=20,
            pts=_sw(
                w5=_rw(5, avg=10.0, delta=-5.0, direction="down", gp=5),
                w10=_rw(10, avg=14.0, delta=-3.0, direction="down", gp=10),
            ),
            min_sw=_sw(
                w5=_rw(5, avg=20.0, delta=-7.0, direction="down", gp=5),
                w10=_rw(10, avg=25.0, delta=-4.0, direction="down", gp=10),
            ),
            ast=_sw(w5=_rw(5, avg=1.8, delta=-0.3, direction="stable", gp=5)),
            pts_avg=14.5,
            min_avg=25.0,
        ),
        gaps=[],
        expected_direction="down",
        confidence_min=0.55,
        confidence_max=1.0,
        must_mention_stats=["MIN", "PTS"],
    )


def _ex_breakout_noise() -> dict:
    return _example(
        id="breakout_noise",
        description="One 45-point game inflates w5 avg; prior 4 games were 12-16 pts",
        profile=_profile(),
        stats=_stats(
            games_played=15,
            pts=_sw(
                # w5 inflated by one outlier game
                w5=_rw(5, avg=20.6, delta=3.8, direction="up", gp=5),
                # w10 more stable
                w10=_rw(10, avg=17.5, delta=0.5, direction="stable", gp=10),
            ),
            min_sw=_sw(w5=_rw(5, avg=30.0, delta=0.0, direction="stable", gp=5)),
            pts_avg=17.0,
            min_avg=30.0,
        ),
        gaps=[],
        expected_direction="stable",
        confidence_min=0.2,
        confidence_max=0.7,
    )


# ── Public API ────────────────────────────────────────────────────────────────


def build_golden_dataset() -> list[dict]:
    """Return all 15 golden-dataset examples as serialisable dicts."""
    return [
        _ex_zero_games(),
        _ex_five_games_early(),
        _ex_strong_up_pts_reb(),
        _ex_strong_down_pts(),
        _ex_moderate_up_3pt(),
        _ex_stable_consistent(),
        _ex_return_from_injury(),
        _ex_currently_absent(),
        _ex_extended_absence(),
        _ex_mixed_signals(),
        _ex_high_confidence_30g(),
        _ex_low_confidence_8g(),
        _ex_no_3pt_shooter(),
        _ex_minutes_regression(),
        _ex_breakout_noise(),
    ]


if __name__ == "__main__":
    examples = build_golden_dataset()
    with _DATASET_PATH.open("w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Written {len(examples)} examples to {_DATASET_PATH}")
