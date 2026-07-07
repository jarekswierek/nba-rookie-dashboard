"""LLM-generated narrative schema."""

from typing import Literal

from pydantic import BaseModel, Field


class PlayerNarrative(BaseModel):
    """Two-to-three sentence narrative bound to a confidence score.

    ``min_length=1`` on summary guards against empty completions — Pydantic
    raises ValidationError which LangGraph surfaces as a retryable failure.
    """

    summary: str = Field(..., min_length=1, max_length=800)
    trend_direction: Literal["up", "down", "stable"]
    confidence: float = Field(..., ge=0.0, le=1.0)
