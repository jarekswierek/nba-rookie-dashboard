"""Server-Sent Events client wrapper for the FastAPI backend.

The main ``httpx.Client`` in ``api_client`` has a 30-second read timeout which is
fine for JSON endpoints but would cut off longer LLM streams mid-narrative. This
module builds a separate client with no read timeout, relying on the backend's
``ping=15`` keepalive to keep the connection live. The parser is provided by
``httpx-sse`` — bespoke line parsing would need to handle keepalive comments and
multiline data fields, which is not effort worth spending here.
"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from httpx_sse import connect_sse

_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

# Connect timeout stays short (fail fast when backend is down); read
# timeout is disabled because SSE streams are long-lived by design and
# the backend sends keepalive comments every 15s.
_CONNECT_TIMEOUT_SECONDS = 5.0
_POOL_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SSEEvent:
    """One decoded SSE frame with parsed JSON payload."""

    event: str
    data: dict[str, Any]


@lru_cache(maxsize=1)
def _sse_client() -> httpx.Client:
    return httpx.Client(
        base_url=_BASE_URL,
        timeout=httpx.Timeout(
            connect=_CONNECT_TIMEOUT_SECONDS,
            read=None,
            write=None,
            pool=_POOL_TIMEOUT_SECONDS,
        ),
    )


def iter_sse_events(
    path: str, params: dict[str, Any] | None = None
) -> Iterator[SSEEvent]:
    """Yield decoded SSE events from *path* until the server closes the
    stream."""
    with connect_sse(_sse_client(), "GET", path, params=params) as event_source:
        for sse in event_source.iter_sse():
            if not sse.event or not sse.data:
                continue
            try:
                payload = json.loads(sse.data)
            except json.JSONDecodeError:
                continue
            yield SSEEvent(event=sse.event, data=payload)
