from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.graphs.meeting_chat.prompts import (
    ANSWER_QUESTION_SYSTEM_PROMPT,
    EXCERPTS_CONTEXT_RULE,
    FINAL_ANSWER_REQUEST,
    FINAL_ANSWER_SYSTEM_PROMPT,
    GEOPOLITICAL_SYSTEM_PROMPT,
)
from app.graphs.meeting_chat.state import ChatState
from app.graphs.model import get_model, invoke_for_answer
from app.graphs.tool_budget import without_pending_tool_calls


def meeting_content(state: ChatState, *, with_search_rule: bool = True) -> str:
    """The meeting as the model sees it this turn: whole, or as excerpts.

    The synthesis step has no tools, so it gets the excerpts without the
    instruction to search for more.
    """
    transcript = state.get("transcript", "")
    if transcript or not state.get("excerpts"):
        return f"Full meeting content:\n{transcript}"
    rule = f"{EXCERPTS_CONTEXT_RULE}\n\n" if with_search_rule else "Excerpts of the meeting (not the whole meeting).\n\n"
    return (
        f"{rule}"
        f"How the meeting opens:\n{state.get('opening', '')}\n\n"
        f"Passages relevant to the latest question:\n{state.get('excerpts', '')}"
    )


def run_agent(state: ChatState) -> ChatState:
    # Local import keeps the dedicated geopolitical node reusable by the tool
    # module without introducing an import cycle.
    from app.graphs.meeting_chat.tools import MEETING_CHAT_TOOLS

    context_prompt = (
        f"{ANSWER_QUESTION_SYSTEM_PROMPT}\n\n"
        f"Meeting ID: {state.get('meeting_id', 'not provided')}\n"
        f"{meeting_content(state)}"
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
    response = invoke_for_answer(
        [
            SystemMessage(content=(
                f"{FINAL_ANSWER_SYSTEM_PROMPT}\n\n"
                f"{meeting_content(state, with_search_rule=False)}"
            )),
            *without_pending_tool_calls(messages),
            HumanMessage(content=FINAL_ANSWER_REQUEST),
        ],
        model_factory=get_model,
    )
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
