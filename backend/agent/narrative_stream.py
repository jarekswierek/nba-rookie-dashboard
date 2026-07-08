"""Streaming narrative generation for the SSE endpoint.

Two LLM calls, both against Claude Haiku 4.5:

1. ``stream_summary`` — plain text, streamed token by token so the UI can
   render mid-generation. No structured output; validation is impossible
   until the stream ends.
2. ``generate_metadata`` — structured output. Runs after the summary is
   complete and classifies trend_direction and confidence against the
   same signals plus the freshly-written summary text.

Splitting the responsibilities lets us keep hard schema guarantees for
metadata (progress bar, badge) while still delivering real streaming to
the client. The alternative — streaming tokens through a tool call — hands
the client fragments of JSON, not prose.
"""

from collections.abc import AsyncIterator
from typing import cast

from langchain_core.prompts import ChatPromptTemplate

from backend.agent.client import get_anthropic_client
from backend.agent.nodes.generate_narrative import _build_prompt_inputs
from backend.agent.prompts.narrative import (
    HUMAN_TEMPLATE,
    METADATA_HUMAN_TEMPLATE,
    METADATA_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from backend.agent.state import AgentState
from backend.schemas.narrative import PlayerNarrativeMetadata


async def stream_summary(state: AgentState) -> AsyncIterator[str]:
    """Yield narrative tokens as Claude produces them."""
    inputs = _build_prompt_inputs(state)
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_TEMPLATE)]
    )
    chain = prompt | get_anthropic_client()
    async for chunk in chain.astream(inputs):
        content = chunk.content
        if isinstance(content, str) and content:
            yield content


async def generate_metadata(
    state: AgentState, summary: str
) -> PlayerNarrativeMetadata:
    """Classify trend direction and confidence from state + finished summary."""
    inputs = _build_prompt_inputs(state)
    inputs["summary"] = summary
    prompt = ChatPromptTemplate.from_messages(
        [("system", METADATA_SYSTEM_PROMPT), ("human", METADATA_HUMAN_TEMPLATE)]
    )
    llm = get_anthropic_client().with_structured_output(PlayerNarrativeMetadata)
    chain = prompt | llm
    return cast(PlayerNarrativeMetadata, await chain.ainvoke(inputs))
