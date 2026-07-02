"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_origins=["http://localhost:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 when the process is up."""
    return {"status": "ok", "env": settings.app_env}
