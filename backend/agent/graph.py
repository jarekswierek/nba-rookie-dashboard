"""Compile the narrative-generation graph."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.agent.nodes.analyze_trends import analyze_trends
from backend.agent.nodes.detect_context import detect_context_events
from backend.agent.nodes.generate_narrative import generate_narrative
from backend.agent.state import AgentState


def build_graph() -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build the linear graph: analyze_trends -> detect_context ->
    generate_narrative.

    Compiled at call time rather than module import so tests can rebuild with
    patched nodes without state leaking across cases.
    """
    builder: StateGraph = StateGraph(AgentState)  # type: ignore[type-arg]

    builder.add_node("analyze_trends", analyze_trends)
    builder.add_node("detect_context_events", detect_context_events)
    builder.add_node("generate_narrative", generate_narrative)

    builder.add_edge(START, "analyze_trends")
    builder.add_edge("analyze_trends", "detect_context_events")
    builder.add_edge("detect_context_events", "generate_narrative")
    builder.add_edge("generate_narrative", END)

    return builder.compile()
