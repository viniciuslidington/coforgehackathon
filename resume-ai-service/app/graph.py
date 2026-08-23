"""LangGraph workflow for meeting summaries and transcript-grounded Q&A."""
from __future__ import annotations
import os
from typing import Literal, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

Mode = Literal["simple", "detailed"]

# Allows `uv run uvicorn ...` to use local development credentials from .env.
load_dotenv()

class MeetingState(TypedDict, total=False):
    transcript: str
    mode: Mode
    focus_points: list[str]
    question: str
    result: str

class OverviewState(TypedDict):
    transcript: str
    title: str
    simple_summary: str
    keywords: list[str]

def _model() -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured. Add it to .env before calling the API.")
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        # Some OpenRouter models otherwise default to a very large output
        # reservation (for example 65,536 tokens), exceeding demo credit limits.
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "1200")),
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "Meeting Insights API"),
        },
    )

def summarize(state: MeetingState) -> MeetingState:
    focus = ", ".join(state.get("focus_points", [])) or "No extra topics were requested."
    length = "Write exactly one concise paragraph (roughly 50 words)." if state["mode"] == "simple" else "Write a clear detailed summary in 3–4 short paragraphs at most. Include outcomes, decisions, risks, owners, and next steps when present."
    response = _model().invoke([SystemMessage(content="You are a precise meeting-notes assistant. Only use facts in the supplied transcript. Do not invent attendees, decisions, dates, or action owners. " + length), HumanMessage(content=f"Focus points: {focus}\n\nTranscript:\n{state['transcript']}")])
    return {"result": str(response.content)}

def answer_question(state: MeetingState) -> MeetingState:
    response = _model().invoke([SystemMessage(content="Answer the user's question using only the supplied meeting context. Refer to it as 'the meeting' or 'this meeting', never as a transcript, file, document, or source. Be concise and cite relevant timestamps in square brackets when possible. Attribute claims, decisions, concerns, and action items to the speaker named in the meeting whenever that name is available; for example, write 'Nina said...' or 'According to Leo...'. If the meeting does not state the answer, say so plainly."), HumanMessage(content=f"Meeting context:\n{state['transcript']}\n\nQuestion: {state['question']}")])
    return {"result": str(response.content)}

def create_overview(state: OverviewState) -> OverviewState:
    response = _model().invoke([SystemMessage(content="You prepare a meeting-list row from meeting context. Return exactly three lines and no markdown: TITLE: a specific, simple title of at most 8 words; SUMMARY: one concise paragraph of at most 70 words; KEYWORDS: 3 to 8 comma-separated important subjects, people, companies, or topics explicitly mentioned in the meeting. Use only facts from the meeting."), HumanMessage(content=f"Meeting context:\n{state['transcript']}")])
    lines = str(response.content).splitlines()
    title = next((line.removeprefix("TITLE:").strip() for line in lines if line.startswith("TITLE:")), "Meeting overview")
    summary = next((line.removeprefix("SUMMARY:").strip() for line in lines if line.startswith("SUMMARY:")), "No summary was generated.")
    raw_keywords = next((line.removeprefix("KEYWORDS:").strip() for line in lines if line.startswith("KEYWORDS:")), "")
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    return {"title": title, "simple_summary": summary, "keywords": keywords}

def choose_task(state: MeetingState) -> str:
    return "question" if state.get("question") else "summary"

workflow = StateGraph(MeetingState)
workflow.add_node("summary", summarize)
workflow.add_node("question", answer_question)
workflow.add_conditional_edges(START, choose_task, {"summary": "summary", "question": "question"})
workflow.add_edge("summary", END)
workflow.add_edge("question", END)
meeting_graph = workflow.compile()

overview_workflow = StateGraph(OverviewState)
overview_workflow.add_node("create_overview", create_overview)
overview_workflow.add_edge(START, "create_overview")
overview_workflow.add_edge("create_overview", END)
overview_graph = overview_workflow.compile()

def run_meeting_agent(*, transcript: str, mode: Mode = "simple", focus_points: list[str] | None = None, question: str | None = None) -> str:
    state: MeetingState = {"transcript": transcript, "mode": mode, "focus_points": focus_points or []}
    if question:
        state["question"] = question
    return meeting_graph.invoke(state)["result"]

def generate_meeting_overview(transcript: str) -> tuple[str, str, list[str]]:
    result = overview_graph.invoke({"transcript": transcript})
    return result["title"], result["simple_summary"], result["keywords"]
