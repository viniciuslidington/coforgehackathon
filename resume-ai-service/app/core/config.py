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

SAMPLES_DIR = BASE_DIR / "samples"
DATABASE_PATH = Path(os.getenv("MEETINGS_DATABASE_PATH", BASE_DIR / "meeting_insights.db"))

CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
# Some OpenRouter models otherwise default to a very large output reservation
# (for example 65,536 tokens), exceeding demo credit limits.
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "1200"))
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Meeting Insights API")
