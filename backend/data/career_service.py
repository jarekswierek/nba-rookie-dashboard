"""Service layer for player career statistics."""

from statistics import fmean
from typing import Any

from backend.data import nba_client
from shared.schemas.career import CareerSeasonRow, CareerStatsResponse


def _parse_records(
    player_id: int, records: list[dict[str, Any]]
) -> CareerStatsResponse:
    """Build CareerStatsResponse from raw nba_api rows.

    When a player is traded mid-season nba_api emits one row per team plus a
    combined "TOT" row. We keep TOT and drop the team-specific rows for that
    season to avoid double-counting.
    """
    seasons_with_tot = {
        str(r["SEASON_ID"])
        for r in records
        if str(r.get("TEAM_ABBREVIATION", "")) == "TOT"
    }
    filtered = [
        r
        for r in records
        if not (
            str(r["SEASON_ID"]) in seasons_with_tot
            and str(r.get("TEAM_ABBREVIATION", "")) != "TOT"
        )
    ]
    filtered.sort(key=lambda r: str(r["SEASON_ID"]))

    rows: list[CareerSeasonRow] = []
    for i, record in enumerate(filtered, start=1):
        team = str(record.get("TEAM_ABBREVIATION", "")) or None
        rows.append(
            CareerSeasonRow(
                season=str(record["SEASON_ID"]),
                season_label=f"{record['SEASON_ID']} · Season {i}",
                team_abbreviation=team if team != "TOT" else None,
                games_played=int(record.get("GP", 0)),
                pts=float(record.get("PTS", 0.0)),
                reb=float(record.get("REB", 0.0)),
                ast=float(record.get("AST", 0.0)),
            )
        )

    career_avg_total = (
        fmean(r.pts + r.reb + r.ast for r in rows) if rows else 0.0
    )
    return CareerStatsResponse(
        player_id=player_id,
        seasons=rows,
        career_avg_total=career_avg_total,
    )


async def get_career_stats(player_id: int) -> CareerStatsResponse:
    """Return per-season career averages for *player_id*."""
    df = await nba_client.fetch_career_stats(player_id)
    return _parse_records(player_id, df.to_dict(orient="records"))
