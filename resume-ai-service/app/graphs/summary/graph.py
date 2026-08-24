"""LangGraph workflows for meeting summaries: free-text (simple/detailed) and
the structured overview (title, summary, keywords) used for list rows."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graphs.summary.nodes import create_overview, summarize
from app.graphs.summary.state import Mode, OverviewState, SummaryState

summary_workflow = StateGraph(SummaryState)
summary_workflow.add_node("summarize", summarize)
summary_workflow.add_edge(START, "summarize")
summary_workflow.add_edge("summarize", END)
summary_graph = summary_workflow.compile()

def generate_summary_text(transcript: str, mode: Mode = "simple", focus_points: list[str] | None = None) -> str:
    return summary_graph.invoke({"transcript": transcript, "mode": mode, "focus_points": focus_points or []})["result"]

overview_workflow = StateGraph(OverviewState)
overview_workflow.add_node("create_overview", create_overview)
overview_workflow.add_edge(START, "create_overview")
overview_workflow.add_edge("create_overview", END)
overview_graph = overview_workflow.compile()

def generate_meeting_overview(transcript: str) -> tuple[str, str, list[str]]:
    result = overview_graph.invoke({"transcript": transcript})
    return result["title"], result["simple_summary"], result["keywords"]
