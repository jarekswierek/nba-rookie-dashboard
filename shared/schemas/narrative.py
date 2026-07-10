"""LLM-generated narrative schema."""

from pydantic import BaseModel, Field

from shared.types import TrendDirection


class PlayerNarrative(BaseModel):
    """Two-to-three sentence narrative bound to a confidence score.

    ``min_length=1`` on summary guards against empty completions — Pydantic
    raises ValidationError which LangGraph surfaces as a retryable failure.
    """

    summary: str = Field(..., min_length=1, max_length=800)
    trend_direction: TrendDirection
    confidence: float = Field(..., ge=0.0, le=1.0)


class PlayerNarrativeMetadata(BaseModel):
    """Classification-only companion to a streamed narrative.

    Used by the SSE endpoint when the summary text streams token-by-token and the
    trend/confidence classification is generated in a follow-up structured call.
    """

    trend_direction: TrendDirection
    confidence: float = Field(..., ge=0.0, le=1.0)
