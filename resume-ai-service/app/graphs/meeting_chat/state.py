from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    meeting_id: str
    transcript: str
    captions: list[dict[str, str]]
    metadata: dict[str, Any]
    messages: Annotated[list[BaseMessage], add_messages]
