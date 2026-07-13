# 🏀 NBA Rookie Dashboard

> **Status: Full-stack MVP complete — evaluation suite and deploy remaining**

An analytics dashboard that tracks NBA rookie statistics and generates AI-powered narrative analysis with **Claude Haiku**, streamed via SSE, backed by a two-level cache (Redis + PostgreSQL).

![mockup](docs/mockup-preview.png)

---

## What it does

Select a draft class (2020–2024), pick a rookie, and get:

- **Live stats** — points, rebounds, assists, 3P%, minutes with trend deltas
- **Rolling averages** — 5/10/15-game windows overlaid on Plotly charts
- **AI narrative** — streamed token-by-token via SSE; the endpoint composes pure trend and context analysis with a two-call Claude Haiku pattern (plain-text streaming for the summary, structured output for trend direction and confidence)
- **Confidence score** — calibrated from data volume and trend signal strength
- **Draft Class Overview** — stacked bar chart comparing all rookies in a class
- **Career Progression** — season-over-season view per player

---

## Architecture

```mermaid
graph LR
    A[nba_api] -->|rate-limited wrapper| B[FastAPI]
    B -->|hot data, TTL| C[(Redis L1)]
    B -->|cold data, persisted| D[(PostgreSQL L2)]
    B -->|game logs + gaps| E[Narrative endpoint]

    subgraph Narrative endpoint
        E1[analyze_trends] --> E2[detect_context_events]
        E2 --> E3[stream_summary\nClaude Haiku · astream]
        E3 --> E4[generate_metadata\nClaude Haiku · structured]
    end

    E --> F[SSE stream]
    F -->|token + metadata events| G[Streamlit UI]
    E3 -.->|traces| H[LangSmith]
    E4 -.->|traces| H
```

**Key design decisions:**

| Decision | Why |
|---|---|
| Plain async composition over an orchestration framework | A linear three-step pipeline whose middle step needs to stream doesn't earn a graph — pure functions and direct calls stay easier to test, trace, and swap transports on |
| Two-call narrative pattern (stream + classify) | LangChain `with_structured_output` streams JSON fragments, not prose. Splitting into a plain-text streaming call and a structured metadata call keeps both UX and validation. |
| Two-level cache (Redis + PostgreSQL) | Redis handles sub-second hot reads; PostgreSQL persists historical data and narrative timestamps across restarts |
| SSE over polling | Streaming UX for narrative — user sees tokens appear, not a spinner for 2–3s |
| Lazy refresh on MVP, APScheduler for prod | `nba_api` rate-limits to 0.5 req/s; background job at 02:00 ET pre-fetches all rookies so daytime requests hit cache |
| Evaluation-first | Golden dataset (10–15 examples) + LLM-as-judge metrics defined before the prompt is tuned |

---

## Tech stack

| Layer | Tech |
|---|---|
| Data source | `nba_api` |
| Cache L1 | Redis (TTL-based, hot data) |
| Cache L2 | PostgreSQL + Alembic |
| API | FastAPI + SSE (`asyncio` streaming) |
| AI generation | LangChain + Anthropic Claude Haiku 4.5 |
| AI observability | LangSmith |
| Frontend | Streamlit + Plotly |
| Config | `pydantic-settings` |
| Tooling | Poetry, Ruff, mypy (strict), Black, pytest |

---

## Project status

`[████████████░░░] 75%` — Full-stack MVP complete, evaluation and deploy remaining

| Epic | | Status |
|---|---|---|
| 1 · Infrastructure & tooling | ✅ | Done |
| 2 · NBA data pipeline (Redis + PostgreSQL) | ✅ | Done |
| 3 · Season / draft logic | ✅ | Done |
| 4 · Stats aggregation + rolling averages + DNP gaps | ✅ | Done |
| 5 · AI narrative engine (streaming + structured metadata) | ✅ | Done |
| 6 · Streamlit dashboard | ✅ | Done |
| 7 · Evaluation suite | ⏳ | Planned |
| 8 · Portfolio & deploy | ⏳ | Planned |

---

## Quickstart

```bash
cp .env.example .env        # fill in POSTGRES_PASSWORD, ANTHROPIC_API_KEY, LANGCHAIN_API_KEY
make dev                    # docker compose up — API + UI + Redis + PostgreSQL
make verify-langsmith       # confirm LangSmith tracing is active
# open http://localhost:8501
```

API docs available at `http://localhost:8000/docs`.

---

## Evaluation

The narrative engine is designed to be testable:

- **Golden dataset** — 10–15 `(player_stats, expected_narrative)` pairs
- **LLM-as-judge** — factual accuracy (does the trend direction match the numbers?), hallucination check, confidence calibration
- **CI gate** — `make eval` runs against the golden set; PRs blocked if accuracy drops below threshold

---

## Local development

```bash
make install-dev   # poetry install --with dev
make check         # format-check + ruff + mypy
make test          # pytest
make eval          # golden dataset eval
```
