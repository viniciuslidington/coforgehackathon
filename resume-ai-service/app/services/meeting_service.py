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
from app.services import priority
from app.services.database import list_summaries, list_summaries_for_priority

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

def compute_topic_embedding_blob(text: str) -> bytes:
    return priority.vector_to_blob(priority.embed_passage(text))

def _row_to_summary(row: dict[str, object], *, priority_score: float | None = None, priority_tier: str | None = None) -> StoredMeetingSummary:
    data = dict(row)
    data.pop("topic_embedding", None)
    data["participants"] = [name.strip() for name in data["participants"].split(",") if name.strip()]
    data["keywords"] = [keyword.strip() for keyword in data["keywords"].split(",") if keyword.strip()]
    return StoredMeetingSummary(**data, priority_score=priority_score, priority_tier=priority_tier)

MAX_TOPIC_LENGTH = 200


def _normalize_topics(topics: list[str] | None) -> list[str]:
    """Drop blank/whitespace-only topics and bound each topic's length.

    Truncating (rather than rejecting) long topics keeps the endpoint
    permissive while still bounding worst-case embedding-cache growth.
    """
    return [t.strip()[:MAX_TOPIC_LENGTH] for t in (topics or []) if t.strip()]


def get_stored_summaries(
    page: int,
    page_size: int,
    period: Literal["day", "week", "30d", "all"] = "all",
    topics: list[str] | None = None,
    sort: Literal["priority", "time"] = "priority",
) -> SummaryPage:
    date_from = {
        "day": date.today().isoformat(),
        "week": (date.today() - timedelta(days=6)).isoformat(),
        "30d": (date.today() - timedelta(days=29)).isoformat(),
        "all": None,
    }[period]

    topics = _normalize_topics(topics)

    if not topics:
        rows, total = list_summaries(offset=(page - 1) * page_size, limit=page_size, date_from=date_from)
        items = [_row_to_summary(row) for row in rows]
        return SummaryPage(items=items, total=total, page=page, page_size=page_size)

    topic_vectors = [priority.embed_topic(topic) for topic in topics]
    all_rows = list_summaries_for_priority(date_from=date_from)
    scored: list[tuple[float | None, str | None, dict[str, object]]] = []
    for row in all_rows:
        blob = row.get("topic_embedding")
        if blob:
            meeting_vector = priority.blob_to_vector(blob)
            try:
                score = priority.score_meeting(meeting_vector, topic_vectors)
            except ValueError:
                # A stored embedding from a previous, different-dimension
                # model. Degrade gracefully instead of 500ing the whole page.
                logger.warning(
                    "Skipping priority score for %s: stored embedding dimension mismatch",
                    row.get("meeting_id"),
                )
                score, tier = None, None
            else:
                tier = priority.tier_for_score(score)
        else:
            score, tier = None, None
        scored.append((score, tier, row))

    if sort == "priority":
        scored.sort(key=lambda entry: entry[0] if entry[0] is not None else -1.0, reverse=True)
    # sort == "time": `all_rows` (and therefore `scored`) is already ordered
    # by meeting_date DESC, refreshed_at DESC from list_summaries_for_priority,
    # so no re-sort is needed — every row is still scored above regardless.

    total = len(scored)
    start = (page - 1) * page_size
    page_slice = scored[start:start + page_size]
    items = [_row_to_summary(row, priority_score=score, priority_tier=tier) for score, tier, row in page_slice]
    return SummaryPage(items=items, total=total, page=page, page_size=page_size)

def caption_to_segment(caption: Caption) -> TranscriptSegment:
    t = format_timestamp(timestamp_seconds(caption.start))
    speaker, separator, rest = caption.text.partition(":")
    if separator:
        return TranscriptSegment(t=t, sp=speaker.strip(), tx=rest.strip())
    return TranscriptSegment(t=t, sp="", tx=caption.text)
