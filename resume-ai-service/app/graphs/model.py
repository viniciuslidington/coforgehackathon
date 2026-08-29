"""Shared LLM client factory for every LangGraph workflow."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)

def get_model(*, max_tokens: int | None = None) -> ChatOpenAI:
    """Build a chat model, optionally overriding the default output ceiling.

    `OPENROUTER_MAX_TOKENS` is a conservative default sized for chat answers.
    Longer structured output — a three-paragraph briefing plus key points —
    needs more headroom, so callers can raise it per call.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured. Add it to .env before calling the API.")
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=max_tokens if max_tokens is not None else OPENROUTER_MAX_TOKENS,
        default_headers={
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
    )
