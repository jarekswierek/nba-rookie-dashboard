"""Build a full PlayerProfile from cached bio and draft class data."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.data import cache_service
from shared.schemas.stats import PlayerProfile


async def get_player_profile(
    session: AsyncSession, player_id: int, draft_year: int
) -> PlayerProfile:
    """Compose PlayerProfile from bio + draft class caches.

    ``draft_year`` must be supplied by the caller because bio rows do not carry
    it — persisting it would require a migration we can defer until another
    endpoint actually needs the lookup.
    """
    bio = await cache_service.get_player_bio(session, player_id)
    draft = await cache_service.get_draft_class(session, draft_year)
    pick = next(
        (r for r in draft["records"] if int(r["PERSON_ID"]) == player_id),
        None,
    )
    if pick is None:
        raise ValueError(
            f"Player {player_id} not found in draft class {draft_year}"
        )

    return PlayerProfile(
        player_id=player_id,
        full_name=bio.get("full_name") or str(pick.get("PLAYER_NAME", "")),
        position=bio.get("position"),
        height_cm=bio.get("height_cm"),
        weight_kg=bio.get("weight_kg"),
        country=bio.get("country"),
        team_abbreviation=bio.get("team_abbreviation"),
        team_at_draft=str(pick.get("TEAM_ABBREVIATION", "")) or None,
        overall_pick=int(pick.get("OVERALL_PICK", 0)),
        round_number=int(pick.get("ROUND_NUMBER", 1)),
        round_pick=int(pick.get("ROUND_PICK", 0)),
        draft_year=draft_year,
    )
