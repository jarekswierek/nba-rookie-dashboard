"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import draft as draft_router
from backend.api.routes import narrative as narrative_router
from backend.api.routes import players as players_router
from backend.api.routes import season as season_router
from backend.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="NBA Rookie Dashboard API",
    version="0.1.0",
    description=(
        "AI-powered NBA rookie stats visualizer. "
        "Narrative generation via LangGraph + Claude Haiku."
    ),
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(season_router.router, prefix="/api/season", tags=["season"])
app.include_router(draft_router.router, prefix="/api/draft", tags=["draft"])
app.include_router(
    players_router.router, prefix="/api/players", tags=["players"]
)
app.include_router(
    narrative_router.router, prefix="/api/players", tags=["narrative"]
)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 when the process is up."""
    return {"status": "ok", "env": settings.app_env}
