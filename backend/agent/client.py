"""Cached Anthropic client factory for LangGraph nodes.

``@lru_cache`` on the constructor keeps one HTTPX connection pool per unique
configuration — reusing it saves ~50-150ms of TLS handshake per call. Different
models or temperatures still get their own client.
"""

from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from backend.core.config import get_settings


@lru_cache(maxsize=4)
def get_anthropic_client(
    model: str = "claude-haiku-4-5",
    temperature: float = 0.3,
    max_tokens: int = 400,
) -> ChatAnthropic:
    """Return a cached ChatAnthropic client for the given configuration."""
    settings = get_settings()
    return ChatAnthropic(
        model=model,
        anthropic_api_key=SecretStr(settings.anthropic_api_key),
        temperature=temperature,
        max_tokens=max_tokens,
        default_request_timeout=30.0,
        max_retries=2,
    )
