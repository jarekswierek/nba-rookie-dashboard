"""Draft class business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_service
from backend.data.season_detector import season_string
from shared.schemas.draft import DraftClass, DraftPlayer


async def get_draft_class_with_bio(
    session: AsyncSession, year: int
) -> DraftClass:
    """Return draft class for *year* with current team and bio data per
    player."""
    draft_data = await cache_service.get_draft_class(session, year)
    records = draft_data["records"]

    players: list[DraftPlayer] = []
    for pick in records:
        player_id = int(pick["PERSON_ID"])
        bio = await cache_service.get_player_bio(session, player_id)
        players.append(
            DraftPlayer(
                player_id=player_id,
                full_name=str(pick.get("PLAYER_NAME", "")),
                team_abbreviation=bio.get("team_abbreviation"),
                team_at_draft=str(pick.get("TEAM_ABBREVIATION", "")) or None,
                overall_pick=int(pick.get("OVERALL_PICK", 0)),
                round_number=int(pick.get("ROUND_NUMBER", 1)),
                round_pick=int(pick.get("ROUND_PICK", 0)),
                position=bio.get("position"),
                height_cm=bio.get("height_cm"),
                weight_kg=bio.get("weight_kg"),
                country=bio.get("country"),
            )
        )

    return DraftClass(
        season_year=year,
        season=season_string(year),
        players=players,
    )
