"""Orchestration helpers: agent execution, overview generation, stored-summary paging.

This is where request-shaped work (paging, error mapping) meets the graphs
and repositories underneath it. Routers call into here; nothing here talks
HTTP directly.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, Literal

from fastapi import HTTPException
from openai import APIStatusError

from app.core.vtt import Caption, format_timestamp, timestamp_seconds
from app.graphs.meeting_chat.graph import answer_from_transcript
from app.graphs.summary.graph import generate_meeting_overview, generate_summary_text
from app.graphs.summary.state import Mode
from app.schemas.meetings import StoredMeetingSummary, SummaryPage
from app.schemas.transcripts import TranscriptSegment
from app.services.database import list_summaries

logger = logging.getLogger("meeting-insights")

def openrouter_failure(exc: APIStatusError) -> str:
    provider_body = getattr(exc, "body", None)
    suffix = f" Provider response: {provider_body}" if provider_body else ""
    return f"OpenRouter request failed ({exc.status_code}): {exc.message}.{suffix}"

def raise_openrouter_failure(exc: APIStatusError) -> None:
    # Preserve upstream throttling so clients can retry instead of treating a
    # shared free-pool limit as an internal gateway failure.
    status_code = 429 if exc.status_code == 429 else 502
    raise HTTPException(status_code=status_code, detail=openrouter_failure(exc)) from exc

def _run_agent_call(call_name: str, call: Callable[[], str]) -> str:
    try:
        return call()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        # Do not leak upstream SDK stack traces; preserve the actionable
        # provider message and throttling status for clients.
        logger.error(
            "OpenRouter %s request failed status=%s message=%s body=%r",
            call_name,
            exc.status_code,
            exc.message,
            getattr(exc, "body", None),
        )
        raise_openrouter_failure(exc)

def execute_chat(transcript: str, question: str) -> str:
    return _run_agent_call("chat", lambda: answer_from_transcript(transcript, question))

def execute_summary(transcript: str, mode: Mode, focus_points: str | None) -> str:
    points = [item.strip() for item in (focus_points or "").split(",") if item.strip()]
    return _run_agent_call("summary", lambda: generate_summary_text(transcript, mode, points))

def execute_overview(transcript: str) -> tuple[str, str, list[str]]:
    try:
        result = generate_meeting_overview(transcript)
        logger.info(
            "AI overview returned title=%r summary=%r keywords=%s",
            result[0],
            result[1],
            result[2],
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        logger.error(
            "OpenRouter overview request failed status=%s message=%s body=%r",
            exc.status_code,
            exc.message,
            getattr(exc, "body", None),
        )
        raise_openrouter_failure(exc)

def get_stored_summaries(page: int, page_size: int, period: Literal["day", "week", "30d", "all"] = "all") -> SummaryPage:
    date_from = {
        "day": date.today().isoformat(),
        "week": (date.today() - timedelta(days=6)).isoformat(),
        "30d": (date.today() - timedelta(days=29)).isoformat(),
        "all": None,
    }[period]
    rows, total = list_summaries(offset=(page - 1) * page_size, limit=page_size, date_from=date_from)
    items = []
    for row in rows:
        data = dict(row)
        data["participants"] = [name.strip() for name in data["participants"].split(",") if name.strip()]
        data["keywords"] = [keyword.strip() for keyword in data["keywords"].split(",") if keyword.strip()]
        items.append(StoredMeetingSummary(**data))
    return SummaryPage(items=items, total=total, page=page, page_size=page_size)

def caption_to_segment(caption: Caption) -> TranscriptSegment:
    t = format_timestamp(timestamp_seconds(caption.start))
    speaker, separator, rest = caption.text.partition(":")
    if separator:
        return TranscriptSegment(t=t, sp=speaker.strip(), tx=rest.strip())
    return TranscriptSegment(t=t, sp="", tx=caption.text)
