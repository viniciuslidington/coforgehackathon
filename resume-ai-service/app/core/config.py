"""Centralized environment configuration.

Every setting the app reads from the environment is defined here, once.
Adding a real database later (e.g. DATABASE_URL for Postgres) belongs here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Allows `uv run uvicorn ...` to use local development credentials from .env.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATABASE_PATH = Path(os.getenv("MEETINGS_DATABASE_PATH", BASE_DIR / "meeting_insights.db"))

CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
# Some OpenRouter models otherwise default to a very large output reservation
# (for example 65,536 tokens), exceeding demo credit limits.
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "1200"))
# A briefing is three paragraphs plus key points, which does not reliably fit
# in the chat-sized default above.
OPENROUTER_BRIEFING_MAX_TOKENS = int(os.getenv("OPENROUTER_BRIEFING_MAX_TOKENS", "1600"))
# Reasoning models (Gemini 3.x, o-series) bill thinking tokens against the same
# ceiling as the answer, so the budgets above can be spent entirely on thinking
# and leave a response truncated mid-sentence. Set this to one of OpenRouter's
# effort levels — minimal, low, medium, high — to cap thinking on such a model.
# Empty is correct for a non-reasoning model: the field is then omitted, and
# providers that reject an unknown `reasoning` field keep working.
OPENROUTER_REASONING_EFFORT = os.getenv("OPENROUTER_REASONING_EFFORT", "").strip() or None
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Meeting Insights API")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

R2_URL = os.getenv("R2_URL")
R2_ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("BUCKET_NAME", "hackathon-traders-vtt")
