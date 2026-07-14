"""LLM-as-judge for narrative factual accuracy.

Uses the same model as the pipeline (Claude Haiku 4.5) with a binary-question
prompt. Asking binary factual questions instead of open-ended quality assessment
reduces same-model bias and produces consistent, parseable verdicts.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, SecretStr

from backend.core.config import get_settings

_SYSTEM = """\
You are a fact-checker for NBA rookie performance narratives.
You will be given a short narrative text and the underlying statistics.
Answer the two questions below with a strict yes or no — no qualifications.
"""

_HUMAN = """\
NARRATIVE:
{narrative}

UNDERLYING STATISTICS (season averages and recent rolling windows):
{stats_snapshot}

REQUIRED STATS TO MENTION: {required_stats}

Questions:
1. Does the narrative contain any specific number (e.g. a points or percentage value) that directly contradicts the underlying statistics? Answer yes (hallucination found) or no.
2. Are all of the required stats listed above mentioned or clearly referenced in the narrative? Answer yes or no.

Respond with your JSON verdict only.
"""


class JudgeVerdict(BaseModel):
    hallucination_detected: bool = Field(
        description="True if a number in the narrative contradicts the stats"
    )
    required_stats_mentioned: bool = Field(
        description="True if all required stats appear in the narrative"
    )
    reasoning: str = Field(
        description="One sentence explaining the verdict", max_length=300
    )


def _stats_snapshot(stats_dict: dict[str, Any]) -> str:
    """Format key season averages for the judge prompt."""
    lines: list[str] = []
    for key in ("pts_season_avg", "reb_season_avg", "ast_season_avg",
                "fg_pct_season_avg", "fg3_pct_season_avg", "min_season_avg"):
        val = stats_dict.get(key)
        if val is not None:
            label = key.replace("_season_avg", "").upper().replace("_", " ")
            if "pct" in key:
                lines.append(f"- {label}: {val * 100:.1f}%")
            else:
                lines.append(f"- {label}: {val:.1f}")
    games = stats_dict.get("games_played", 0)
    lines.append(f"- Games played: {games}")
    return "\n".join(lines) if lines else "(no averages available)"


async def judge_narrative(
    narrative_text: str,
    stats_dict: dict[str, Any],
    must_mention_stats: list[str],
) -> JudgeVerdict:
    """Call LLM judge and return a binary verdict on hallucination and coverage."""
    settings = get_settings()
    llm = ChatAnthropic(
        model="claude-haiku-4-5",
        anthropic_api_key=SecretStr(settings.anthropic_api_key),
        temperature=0.0,
        max_tokens=200,
    ).with_structured_output(JudgeVerdict)

    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM), ("human", _HUMAN)]
    )
    chain = prompt | llm

    required = ", ".join(must_mention_stats) if must_mention_stats else "none specified"
    result = await chain.ainvoke(
        {
            "narrative": narrative_text,
            "stats_snapshot": _stats_snapshot(stats_dict),
            "required_stats": required,
        }
    )
    return result  # type: ignore[return-value]
