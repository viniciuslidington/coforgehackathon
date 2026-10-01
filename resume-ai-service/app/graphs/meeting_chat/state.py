from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    meeting_id: str
    # The whole meeting when it is short; empty when it is sent as excerpts.
    transcript: str
    # Set instead of `transcript` for a long meeting, refreshed every turn
    # for the question being asked.
    opening: str
    excerpts: str
    captions: list[dict[str, str]]
    metadata: dict[str, Any]
    messages: Annotated[list[BaseMessage], add_messages]
