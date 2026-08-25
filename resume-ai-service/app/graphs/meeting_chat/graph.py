"""Persistent LangGraph agent for Q&A about one meeting."""
from __future__ import annotations

import atexit
from contextlib import AbstractContextManager
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import DATABASE_PATH
from app.graphs.meeting_chat.nodes import run_agent, synthesize_answer
from app.graphs.meeting_chat.state import ChatState
from app.graphs.meeting_chat.tools import MEETING_CHAT_TOOLS


def _route_after_agent(state: ChatState) -> str:
    message = state.get("messages", [])[-1]
    return "tools" if isinstance(message, AIMessage) and message.tool_calls else "synthesize"


def build_chat_graph(checkpointer: Any = None) -> CompiledStateGraph:
    workflow = StateGraph(ChatState)
    workflow.add_node("agent", run_agent)
    workflow.add_node("tools", ToolNode(MEETING_CHAT_TOOLS))
    workflow.add_node("synthesize", synthesize_answer)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "synthesize": "synthesize"},
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("synthesize", END)
    return workflow.compile(checkpointer=checkpointer)


_checkpoint_context: AbstractContextManager[SqliteSaver] = SqliteSaver.from_conn_string(str(DATABASE_PATH))
_checkpointer = _checkpoint_context.__enter__()
atexit.register(_checkpoint_context.__exit__, None, None, None)
chat_graph = build_chat_graph(_checkpointer)


def answer_from_transcript(transcript: str, question: str) -> str:
    """Compatibility wrapper for the stateless uploaded-VTT endpoint."""
    result = chat_graph.invoke(
        {
            "meeting_id": "uploaded-vtt",
            "transcript": transcript,
            "captions": [],
            "metadata": {},
            "messages": [HumanMessage(content=question)],
        },
        config={"configurable": {"thread_id": str(uuid4())}},
    )
    message = result["messages"][-1]
    if not isinstance(message, AIMessage):
        raise RuntimeError("The meeting chat agent did not return a final answer.")
    return str(message.content)
