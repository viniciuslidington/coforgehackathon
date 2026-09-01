"""Persistent LangGraph agent for Q&A across a selected set of meetings."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.graphs.checkpointer import get_checkpointer
from app.graphs.quick_chat.nodes import run_quick_chat_agent, synthesize_quick_chat_answer
from app.graphs.quick_chat.state import QuickChatState
from app.graphs.quick_chat.tools import QUICK_CHAT_TOOLS
from app.graphs.tool_budget import MAX_TOOL_ROUNDS, recursion_limit_for, route_after_agent

QUICK_CHAT_RECURSION_LIMIT = recursion_limit_for(MAX_TOOL_ROUNDS)


def _route_after_agent(state: QuickChatState) -> str:
    return route_after_agent(state.get("messages", []), agent="Quick chat")


def build_quick_chat_graph(checkpointer: Any = None) -> CompiledStateGraph:
    workflow = StateGraph(QuickChatState)
    workflow.add_node("agent", run_quick_chat_agent)
    workflow.add_node("tools", ToolNode(QUICK_CHAT_TOOLS))
    workflow.add_node("synthesize", synthesize_quick_chat_answer)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "synthesize": "synthesize"},
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("synthesize", END)
    return workflow.compile(checkpointer=checkpointer)


quick_chat_graph = build_quick_chat_graph(get_checkpointer())


def thread_id_for(session_id: str) -> str:
    """Namespace the session so it never collides with a meeting chat thread."""
    return f"quick-chat:{session_id}"
