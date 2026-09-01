"""Shared LLM client factory for every LangGraph workflow."""
from __future__ import annotations

import logging
from typing import Callable, Sequence

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_MODEL,
    OPENROUTER_REASONING_EFFORT,
    OPENROUTER_SITE_URL,
)

logger = logging.getLogger("meeting-insights")


def get_model(*, max_tokens: int | None = None) -> ChatOpenAI:
    """Build a chat model, optionally overriding the default output ceiling.

    `OPENROUTER_MAX_TOKENS` is a conservative default sized for chat answers.
    Longer structured output — a three-paragraph briefing plus key points —
    needs more headroom, so callers can raise it per call.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured. Add it to .env before calling the API.")
    # On a reasoning model the ceiling above covers thinking *and* the answer,
    # so without an effort cap the whole budget can go to thinking and the
    # answer arrives truncated. Sent only when configured, because a model that
    # does not reason rejects or ignores the field.
    extra_body = (
        {"reasoning": {"effort": OPENROUTER_REASONING_EFFORT}}
        if OPENROUTER_REASONING_EFFORT
        else None
    )
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=max_tokens if max_tokens is not None else OPENROUTER_MAX_TOKENS,
        extra_body=extra_body,
        default_headers={
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
    )


def _answer_text(message: BaseMessage) -> str:
    """The text of a reply, flattened across both content shapes."""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        str(part.get("text", ""))
        for part in message.content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def invoke_for_answer(
    messages: Sequence[BaseMessage],
    *,
    model_factory: Callable[..., ChatOpenAI] = get_model,
    max_tokens: int | None = None,
) -> BaseMessage:
    """Invoke the model, retrying once with more headroom if it says nothing.

    A reasoning model bills thinking against the same ceiling as the answer, so
    a long synthesis can spend the entire budget before writing a word and come
    back with empty content. One retry at double the ceiling recovers that. A
    second would only be slower: an empty reply twice over is not a budget
    problem, and the caller shows the user a message rather than a blank bubble.

    `model_factory` is a parameter rather than a direct `get_model` call so a
    node keeps the seam its tests patch — the node passes its own module-level
    `get_model`, and a stub substituted there still reaches this helper.
    """
    response = model_factory(max_tokens=max_tokens).invoke(list(messages))
    if _answer_text(response).strip():
        return response

    ceiling = max_tokens if max_tokens is not None else OPENROUTER_MAX_TOKENS
    logger.warning(
        "Empty answer at %s tokens (finish_reason=%s); retrying with %s.",
        ceiling,
        response.response_metadata.get("finish_reason"),
        ceiling * 2,
    )
    retried = model_factory(max_tokens=ceiling * 2).invoke(list(messages))
    return retried if _answer_text(retried).strip() else response
