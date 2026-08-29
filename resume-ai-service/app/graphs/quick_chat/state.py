"""Conversation state for the scoped Quick Chat agent."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QuickChatState(TypedDict, total=False):
    """State for one Quick Chat turn.

    `summaries` and `embeddings` are preloaded from the resolved scope so the
    tools stay pure lookups — no tool call reopens the database mid-turn, and
    `meeting_ids` is the authoritative access-control list every tool checks.
    """
    scope_fingerprint: str
    meeting_ids: list[str]
    catalog: list[dict[str, Any]]
    summaries: dict[str, str]
    embeddings: dict[str, bytes]
    messages: Annotated[list[BaseMessage], add_messages]
