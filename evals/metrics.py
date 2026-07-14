"""Deterministic evaluation metrics for the narrative pipeline.

All functions here are pure — no I/O, no LLM calls. They check properties that
can be verified without a language model: direction exactness and confidence
falling within the expected range.
"""

from dataclasses import dataclass


@dataclass
class EvalResult:
    example_id: str
    direction_correct: bool
    confidence_in_range: bool
    hallucination_free: bool | None  # None when judge was not run
    required_stats_mentioned: bool | None  # None when judge was not run
    judge_reasoning: str = ""

    @property
    def passed(self) -> bool:
        deterministic_ok = self.direction_correct and self.confidence_in_range
        if self.hallucination_free is not None and not self.hallucination_free:
            return False
        return deterministic_ok


def check_direction(actual: str, expected: str) -> bool:
    return actual == expected


def check_confidence_range(
    actual: float, conf_min: float, conf_max: float
) -> bool:
    return conf_min <= actual <= conf_max


def accuracy(results: list[EvalResult]) -> float:
    """Fraction of examples where direction_correct is True."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.direction_correct) / len(results)


def format_report(results: list[EvalResult]) -> str:
    lines: list[str] = []
    lines.append(f"\n{'ID':<30} {'DIR':>5} {'CONF':>5} {'HALL':>5} {'STATS':>6}")
    lines.append("-" * 60)
    for r in results:
        dir_mark = "✓" if r.direction_correct else "✗"
        conf_mark = "✓" if r.confidence_in_range else "✗"
        hall_mark = ("✓" if r.hallucination_free else "✗") if r.hallucination_free is not None else "—"
        stats_mark = ("✓" if r.required_stats_mentioned else "✗") if r.required_stats_mentioned is not None else "—"
        lines.append(f"{r.example_id:<30} {dir_mark:>5} {conf_mark:>5} {hall_mark:>5} {stats_mark:>6}")
    lines.append("-" * 60)
    acc = accuracy(results)
    passed = sum(1 for r in results if r.passed)
    lines.append(f"Passed: {passed}/{len(results)}  |  Direction accuracy: {acc:.0%}")
    return "\n".join(lines)
