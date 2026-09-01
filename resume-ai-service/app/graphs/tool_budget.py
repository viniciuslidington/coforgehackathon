"""Bounding the agent tool loop so a turn always ends in an answer.

Both chat graphs route agent -> tools -> agent for as long as the model keeps
asking for tools, and nothing in that shape guarantees it ever stops. When it
does not, LangGraph raises GraphRecursionError: an error where the user
expected an answer, after paying for every round. These helpers end the turn
instead, synthesizing from whatever evidence was gathered before the cut.
"""
from __future__ import annotations

import logging
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger("meeting-insights")

# How many times an agent may call tools before it has to answer. Five covers
# every question these agents answer well; past that the model is looping
# rather than gathering. Each round also re-sends the whole context, so an
# unbounded loop is expensive as well as slow.
MAX_TOOL_ROUNDS = 5


def recursion_limit_for(max_rounds: int = MAX_TOOL_ROUNDS) -> int:
    """A backstop that should never fire, since the router cuts the loop first.

    One round is two super-steps (agent, tools); the entry agent step and
    synthesize add two more. The extra headroom keeps LangGraph's own limit
    from being the thing that ends a turn, because that surfaces as an error
    rather than as an answer.
    """
    return 2 * max_rounds + 6


def tool_rounds_this_turn(messages: Sequence[BaseMessage]) -> int:
    """Tool rounds taken since the user's latest question.

    Counted per turn rather than over the whole list: `messages` is
    checkpointed across the session, so a running total would shrink every
    later question's budget until none was left.
    """
    rounds = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, AIMessage) and message.tool_calls:
            rounds += 1
    return rounds


def route_after_agent(
    messages: Sequence[BaseMessage],
    *,
    max_rounds: int = MAX_TOOL_ROUNDS,
    agent: str = "chat",
) -> str:
    """"tools" while the agent is still gathering, "synthesize" once it is done
    — or once it has spent its budget."""
    message = messages[-1] if messages else None
    if not (isinstance(message, AIMessage) and message.tool_calls):
        return "synthesize"
    if tool_rounds_this_turn(messages) >= max_rounds:
        logger.warning(
            "%s hit its tool budget (%s rounds); answering from the evidence gathered "
            "so far.",
            agent,
            max_rounds,
        )
        return "synthesize"
    return "tools"


def without_pending_tool_calls(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """The history with the trailing draft's unanswered tool calls removed.

    Only ever non-trivial when the router cut a runaway loop short: the draft
    still asks for tools that will never run, and providers reject a tool call
    that has no matching result. Everything gathered before the cut stays, so
    the answer is still grounded.
    """
    if not messages:
        return list(messages)
    draft = messages[-1]
    if not (isinstance(draft, AIMessage) and draft.tool_calls):
        return list(messages)
    return [*messages[:-1], AIMessage(content=draft.content or "", id=draft.id)]
