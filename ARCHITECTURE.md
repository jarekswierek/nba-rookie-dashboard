# Architecture Decisions

Five decisions that shaped this codebase — what was chosen, what was rejected, and why.

---

## 1. Plain async composition over LangGraph

The narrative pipeline runs three steps in order:
`analyze_trends → detect_context_events → stream_summary + generate_metadata`

LangGraph was scaffolded early for this and removed when the SSE endpoint was built. A linear three-step sequence with no conditional branches, no parallel edges, and no persistent checkpoints does not earn a graph. Direct async composition is shorter, easier to trace, and has zero framework overhead on the request path.

```python
# What the production path actually looks like
trends = analyze_trends(stats)                  # pure function
events = detect_context_events(gaps, stats)     # pure function
async for token in stream_summary(state):       # LLM call 1
    yield {"event": "token", ...}
metadata = await generate_metadata(state, text) # LLM call 2
```

LangGraph earns its place when a pipeline has conditional routing, parallel branches, or human-in-the-loop checkpoints. None of those appeared. A framework added before the problem it solves shows up is dead code, and reviewers notice faster than you expect.

---

## 2. Two-call streaming pattern (stream + classify)

LangChain `.with_structured_output(Model)` binds an Anthropic tool call under the hood. Calling `.astream()` on that chain yields JSON fragments (`{"summary": "Player show`), not readable prose. The user would see JSON scaffolding streaming into the expander.

The pattern that works:

1. **`stream_summary()`** — plain-text streaming, no structured output, prose token-by-token via `astream()`.
2. **`generate_metadata()`** — called after the stream completes, takes the finished summary as context, returns `PlayerNarrativeMetadata` (trend direction + confidence) via `.with_structured_output()`.

Event sequence: `token* → metadata → done` (or `warning` before any of these on fallback).

Cost: 2× LLM inference. Mitigation: Anthropic prompt caching on an identical system prompt reduces the second call to roughly 10% of full price. The metadata call is fast because the summary (already computed) provides most of the signal — the LLM is classifying, not generating.

This constraint — streaming prose is mutually exclusive with structured output in a single LangChain call — determines the shape of the endpoint, the prompts, and the schema. It should be discovered before any of those are designed.

---

## 3. Two-level cache (Redis + PostgreSQL)

| Layer | Stores | TTL | Why this layer |
|---|---|---|---|
| Redis L1 | Game logs, season averages, season status | 4 h | Sub-second repeated reads within a session |
| PostgreSQL L2 | Draft lists, bio, AI narratives, fetch timestamps | 24 h – 7 d | Persists across restarts; holds `fetched_at` / `generated_at` |

Redis alone loses timestamps on restart — the UI would lose "Stats last fetched: today 14:32" between deploys. PostgreSQL alone has no sub-millisecond read path for hot data during a session. Together, they cover both.

Invalidation is asymmetric by design. Redis evicts on TTL automatically. AI narratives in PostgreSQL are only regenerated when `last_game_date` is newer than `narrative_generated_at` — avoiding a Claude Haiku call on every stats refresh. The comparison happens in the endpoint before any LLM call is issued.

`nba_api` is rate-limited at 0.5 req/s. Without caching, selecting a player would block for 2–3 seconds every time. The background job at 02:00 ET (APScheduler, phase 2) pre-fetches all active rookies so daytime requests hit Redis.

---

## 4. SSE over polling

Claude Haiku generates 100–200 tokens of prose. With polling, the user sees a spinner for 2–3 seconds then the full text appears. With SSE, tokens appear as they are generated — the reading experience starts immediately.

SSE is simpler than WebSocket for this use case: unidirectional (server → client only), works through HTTP reverse proxies without configuration, and is natively supported by `httpx`'s streaming interface on the Streamlit side.

Two non-obvious details:

- `ping=15` on `sse-starlette.EventSourceResponse` sends keepalive comments every 15 seconds. Without this, proxies (nginx default timeout: 60 s) close idle connections mid-stream.
- On `asyncio.CancelledError` (client disconnects mid-stream): propagate, do not catch. Catching it would persist a truncated summary to the database and serve it as the cached fallback on the next request.

Streamlit reruns the whole script on every interaction, which would restart the SSE stream and burn tokens on every sidebar click. The solution: cache the completed `_NarrativeResult` in `st.session_state` keyed by `(player_id, season, year)`. Subsequent reruns render statically from session state. Degraded results (`stream_interrupted`, `unavailable`) are intentionally not cached so the next rerun retries the live path.

---

## 5. Metric units at the data layer

`nba_api` returns height as a feet-inches string (`"6-7"`) and weight as an integer in pounds. The conversion to centimetres and kilograms happens once, in `DraftPlayer` schema construction inside `backend/data/draft_service.py`.

```python
# One conversion point — never in the UI, never duplicated
height_cm = _feet_inches_to_cm(raw_height)
weight_kg = _pounds_to_kg(raw_weight)
```

One conversion point means one place to fix if the source format changes, and one place to test. If Streamlit and a future batch job each converted independently, they could drift through different rounding or string-parsing edge cases. The UI receives `height_cm: float | None` and renders it directly — no unit logic outside the data layer.
