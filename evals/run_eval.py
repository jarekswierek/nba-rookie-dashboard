"""Evaluation runner for the narrative pipeline.

Usage:
    make eval                   # full eval (direction + judge)
    make eval-fast              # direction accuracy only, no LLM judge

Exit code 1 when direction accuracy < 80% — used as CI gate.

The runner uses the same pipeline functions as production
(analyze_trends → detect_context_events → stream_summary → generate_metadata)
so prompt regressions surface immediately without mocking.
"""

import argparse
import asyncio
import json
import logging
import pathlib
import sys
from typing import Any

from backend.agent.context_events import detect_context_events
from backend.agent.narrative_stream import generate_metadata, stream_summary
from backend.agent.state import AgentState
from backend.agent.trend_analysis import analyze_trends
from evals.judge import judge_narrative
from evals.metrics import (
    EvalResult,
    accuracy,
    check_confidence_range,
    check_direction,
    format_report,
)
from shared.schemas.gaps import GapEvent
from shared.schemas.stats import AggregatedStats, PlayerProfile

logging.basicConfig(level=logging.WARNING)

_DATASET_PATH = pathlib.Path(__file__).parent / "golden_dataset.jsonl"
_ACCURACY_THRESHOLD = 0.80


def _load_examples() -> list[dict[str, Any]]:
    with _DATASET_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _build_state(example: dict[str, Any]) -> AgentState:
    profile = PlayerProfile.model_validate(example["profile"])
    stats = AggregatedStats.model_validate(example["stats"])
    gaps = [GapEvent.model_validate(g) for g in example.get("gaps", [])]
    return AgentState(
        player_id=profile.player_id,
        season=stats.season,
        profile=profile,
        stats=stats,
        gaps=gaps,
    )


async def _eval_one(
    example: dict[str, Any],
    *,
    run_judge: bool,
) -> tuple[EvalResult, str]:
    """Evaluate one example; return (EvalResult, narrative_text)."""
    expected = example["expected"]
    state = _build_state(example)

    state["trend_analysis"] = analyze_trends(state["stats"]).model_dump()
    context = detect_context_events(state["gaps"], state["stats"])
    state["context_events"] = [e.model_dump(mode="json") for e in context.events]

    tokens: list[str] = []
    async for token in stream_summary(state):
        tokens.append(token)
    narrative = "".join(tokens).strip()

    metadata = await generate_metadata(state, narrative)

    dir_ok = check_direction(metadata.trend_direction, expected["trend_direction"])
    conf_ok = check_confidence_range(
        metadata.confidence,
        expected["confidence_min"],
        expected["confidence_max"],
    )

    hallucination_free: bool | None = None
    stats_mentioned: bool | None = None
    reasoning = ""

    if run_judge and expected.get("must_mention_stats"):
        verdict = await judge_narrative(
            narrative_text=narrative,
            stats_dict=example["stats"],
            must_mention_stats=expected["must_mention_stats"],
        )
        hallucination_free = not verdict.hallucination_detected
        stats_mentioned = verdict.required_stats_mentioned
        reasoning = verdict.reasoning

    return (
        EvalResult(
            example_id=example["id"],
            direction_correct=dir_ok,
            confidence_in_range=conf_ok,
            hallucination_free=hallucination_free,
            required_stats_mentioned=stats_mentioned,
            judge_reasoning=reasoning,
        ),
        narrative,
    )


async def run_eval(*, run_judge: bool) -> list[EvalResult]:
    examples = _load_examples()
    results: list[EvalResult] = []

    for i, ex in enumerate(examples, start=1):
        print(f"[{i:2d}/{len(examples)}] {ex['id']} ...", end=" ", flush=True)
        try:
            result, narrative = await _eval_one(ex, run_judge=run_judge)
            mark = "✓" if result.direction_correct else "✗"
            print(f"{mark} ({metadata_summary(result, narrative)})")
            results.append(result)
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append(
                EvalResult(
                    example_id=ex["id"],
                    direction_correct=False,
                    confidence_in_range=False,
                    hallucination_free=None,
                    required_stats_mentioned=None,
                    judge_reasoning=str(exc),
                )
            )

    return results


def metadata_summary(result: EvalResult, narrative: str) -> str:
    preview = narrative[:60].replace("\n", " ")
    return f"conf={'✓' if result.confidence_in_range else '✗'}  \"{preview}…\""


def main() -> None:
    parser = argparse.ArgumentParser(description="Narrative pipeline evaluator")
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM-as-judge (direction accuracy only, faster)",
    )
    args = parser.parse_args()

    results = asyncio.run(run_eval(run_judge=not args.no_judge))

    print(format_report(results))

    acc = accuracy(results)
    if acc < _ACCURACY_THRESHOLD:
        print(
            f"\nFAIL — direction accuracy {acc:.0%} is below"
            f" threshold {_ACCURACY_THRESHOLD:.0%}"
        )
        sys.exit(1)
    else:
        print(f"\nPASS — direction accuracy {acc:.0%}")


if __name__ == "__main__":
    main()
