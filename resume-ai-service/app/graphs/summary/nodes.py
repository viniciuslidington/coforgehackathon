from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.graphs.model import get_model
from app.graphs.summary.prompts import (
    OVERVIEW_SYSTEM_PROMPT,
    SUMMARY_LENGTH_DETAILED,
    SUMMARY_LENGTH_SIMPLE,
    SUMMARY_SYSTEM_PROMPT_BASE,
)
from app.graphs.summary.state import OverviewState, SummaryState

def summarize(state: SummaryState) -> SummaryState:
    focus = ", ".join(state.get("focus_points", [])) or "No extra topics were requested."
    length = SUMMARY_LENGTH_SIMPLE if state["mode"] == "simple" else SUMMARY_LENGTH_DETAILED
    response = get_model().invoke([
        SystemMessage(content=SUMMARY_SYSTEM_PROMPT_BASE + length),
        HumanMessage(content=f"Focus points: {focus}\n\nTranscript:\n{state['transcript']}"),
    ])
    return {"result": str(response.content)}

def create_overview(state: OverviewState) -> OverviewState:
    response = get_model().invoke([
        SystemMessage(content=OVERVIEW_SYSTEM_PROMPT),
        HumanMessage(content=f"Meeting context:\n{state['transcript']}"),
    ])
    lines = str(response.content).splitlines()
    title = next((line.removeprefix("TITLE:").strip() for line in lines if line.startswith("TITLE:")), "Meeting overview")
    summary = next((line.removeprefix("SUMMARY:").strip() for line in lines if line.startswith("SUMMARY:")), "No summary was generated.")
    raw_keywords = next((line.removeprefix("KEYWORDS:").strip() for line in lines if line.startswith("KEYWORDS:")), "")
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    return {"title": title, "simple_summary": summary, "keywords": keywords}
