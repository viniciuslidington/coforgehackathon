"""The retry that keeps a spent token budget from becoming a blank answer.

A reasoning model bills thinking against the same ceiling as the answer, so a
long synthesis can spend the whole budget before writing a word and return
empty content — no error, just nothing to show the user.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from app.core.config import OPENROUTER_MAX_TOKENS
from app.graphs.model import invoke_for_answer

MESSAGES = [HumanMessage(content="What happened?")]


class ScriptedModel:
    """Replays one reply per call and records the ceiling it was built with."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.ceilings: list[int | None] = []

    def factory(self, *, max_tokens: int | None = None):
        self.ceilings.append(max_tokens)
        return self

    def invoke(self, _messages):
        return AIMessage(content=self.replies.pop(0))


def test_an_answer_is_returned_without_a_second_call() -> None:
    model = ScriptedModel("Here is the answer.")

    response = invoke_for_answer(MESSAGES, model_factory=model.factory)

    assert response.content == "Here is the answer."
    assert model.ceilings == [None]


def test_an_empty_answer_is_retried_with_double_the_ceiling() -> None:
    model = ScriptedModel("", "Here is the answer.")

    response = invoke_for_answer(MESSAGES, model_factory=model.factory)

    assert response.content == "Here is the answer."
    assert model.ceilings == [None, OPENROUTER_MAX_TOKENS * 2]


def test_the_retry_doubles_an_explicit_ceiling_too() -> None:
    model = ScriptedModel("   ", "Here is the answer.")

    invoke_for_answer(MESSAGES, model_factory=model.factory, max_tokens=800)

    assert model.ceilings == [800, 1600]


def test_a_second_empty_reply_is_not_retried_again() -> None:
    """Twice over is not a budget problem; the caller shows a message instead."""
    model = ScriptedModel("", "")

    response = invoke_for_answer(MESSAGES, model_factory=model.factory)

    assert response.content == ""
    assert len(model.ceilings) == 2
