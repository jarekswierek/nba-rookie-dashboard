"""Season status business logic."""

from backend.data import cache_redis, nba_client
from backend.data.season_detector import detect_current_season
from backend.schemas.season import SeasonStatus


async def get_season_status() -> SeasonStatus:
    """Return current season status, served from Redis cache when available."""
    cached = await cache_redis.get_scoreboard()
    if cached is not None:
        return SeasonStatus(**cached)

    df = await nba_client.fetch_scoreboard()
    status_dict = detect_current_season(df)
    await cache_redis.set_scoreboard(status_dict)
    return SeasonStatus(**status_dict)
