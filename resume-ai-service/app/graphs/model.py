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

def get_model() -> ChatOpenAI:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured. Add it to .env before calling the API.")
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=OPENROUTER_MAX_TOKENS,
        default_headers={
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
    )
