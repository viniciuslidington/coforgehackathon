from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.graphs.meeting_chat.prompts import (
    ANSWER_QUESTION_SYSTEM_PROMPT,
    FINAL_ANSWER_REQUEST,
    FINAL_ANSWER_SYSTEM_PROMPT,
    GEOPOLITICAL_SYSTEM_PROMPT,
)
from app.graphs.meeting_chat.state import ChatState
from app.graphs.model import get_model


def run_agent(state: ChatState) -> ChatState:
    # Local import keeps the dedicated geopolitical node reusable by the tool
    # module without introducing an import cycle.
    from app.graphs.meeting_chat.tools import MEETING_CHAT_TOOLS

    transcript = state.get("transcript", "")
    context_prompt = (
        f"{ANSWER_QUESTION_SYSTEM_PROMPT}\n\n"
        f"Meeting ID: {state.get('meeting_id', 'not provided')}\n"
        f"Full meeting content:\n{transcript}"
    )
    response = get_model().bind_tools(MEETING_CHAT_TOOLS).invoke([
        SystemMessage(content=context_prompt),
        *state.get("messages", []),
    ])
    return {"messages": [response]}


def synthesize_answer(state: ChatState) -> ChatState:
    """Turn the agent's draft/tool evidence into the only user-visible answer."""
    messages = state.get("messages", [])
    draft = messages[-1] if messages else None
    transcript = state.get("transcript", "")
    response = get_model().invoke([
        SystemMessage(content=(
            f"{FINAL_ANSWER_SYSTEM_PROMPT}\n\n"
            f"Full meeting content:\n{transcript}"
        )),
        *messages,
        HumanMessage(content=FINAL_ANSWER_REQUEST),
    ])
    # Reuse the draft id so add_messages replaces the internal draft instead
    # of retaining it in the persistent conversation history.
    if draft is not None and getattr(draft, "id", None):
        response.id = draft.id
    return {"messages": [response]}


def synthesize_geopolitical_analysis(articles: list[dict[str, Any]]) -> str:
    """Run a dedicated, news-only LLM call without the main chat history."""
    response = get_model().invoke([
        SystemMessage(content=GEOPOLITICAL_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(articles, ensure_ascii=False)),
    ])
    return str(response.content)
