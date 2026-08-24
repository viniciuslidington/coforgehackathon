"""LangGraph workflow for transcript-grounded Q&A about a single meeting."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graphs.meeting_chat.nodes import answer_question
from app.graphs.meeting_chat.state import ChatState

workflow = StateGraph(ChatState)
workflow.add_node("answer", answer_question)
workflow.add_edge(START, "answer")
workflow.add_edge("answer", END)
chat_graph = workflow.compile()

def answer_from_transcript(transcript: str, question: str) -> str:
    return chat_graph.invoke({"transcript": transcript, "question": question})["result"]
