"""Graph nodes for the scoped Quick Chat agent."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.graphs.model import get_model, invoke_for_answer
from app.graphs.quick_chat.prompts import (
    QUICK_CHAT_FINAL_ANSWER_REQUEST,
    QUICK_CHAT_FINAL_ANSWER_SYSTEM_PROMPT,
    QUICK_CHAT_SYSTEM_PROMPT,
)
from app.graphs.quick_chat.state import QuickChatState
from app.graphs.tool_budget import without_pending_tool_calls


def _catalog_text(state: QuickChatState) -> str:
    """One compact line per meeting.

    A line rather than a full summary: at ~35 tokens each this stays cheap for
    a scope of a hundred meetings, and the agent pulls detail on demand
    through its tools.
    """
    lines = [
        "{meeting_id} | {meeting_date} | {title} | {keywords}".format(
            meeting_id=entry.get("meeting_id", ""),
            meeting_date=entry.get("meeting_date", ""),
            title=entry.get("title", ""),
            keywords=", ".join(entry.get("keywords", [])),
        )
        for entry in state.get("catalog", [])
    ]
    if not lines:
        return "(no meetings in scope)"
    return "\n".join(lines)


def run_quick_chat_agent(state: QuickChatState) -> QuickChatState:
    from app.graphs.quick_chat.tools import QUICK_CHAT_TOOLS  # avoids an import cycle

    context_prompt = (
        f"{QUICK_CHAT_SYSTEM_PROMPT}\n\n"
        f"Meetings in scope ({len(state.get('meeting_ids', []))}):\n"
        f"meeting_id | date | title | keywords\n"
        f"{_catalog_text(state)}"
    )
    response = get_model().bind_tools(QUICK_CHAT_TOOLS).invoke([
        SystemMessage(content=context_prompt),
        *state.get("messages", []),
    ])
    return {"messages": [response]}


def synthesize_quick_chat_answer(state: QuickChatState) -> QuickChatState:
    """Turn the agent's draft and tool evidence into the user-visible answer."""
    messages = state.get("messages", [])
    draft = messages[-1] if messages else None
    response = invoke_for_answer(
        [
            SystemMessage(content=QUICK_CHAT_FINAL_ANSWER_SYSTEM_PROMPT),
            *without_pending_tool_calls(messages),
            HumanMessage(content=QUICK_CHAT_FINAL_ANSWER_REQUEST),
        ],
        model_factory=get_model,
    )
    # Reuse the draft id so add_messages replaces the internal draft rather
    # than persisting it. That matters more here than in the meeting chat:
    # the draft would otherwise carry a restatement of the whole catalog into
    # every later turn's history.
    if draft is not None and getattr(draft, "id", None):
        response.id = draft.id
    return {"messages": [response]}
