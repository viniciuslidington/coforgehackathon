"""Orchestration helpers: agent execution, overview generation, stored-summary paging.

This is where request-shaped work (paging, error mapping) meets the graphs
and repositories underneath it. Routers call into here; nothing here talks
HTTP directly.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, Literal

import numpy as np

from fastapi import HTTPException
from openai import APIStatusError

from app.core.vtt import Caption, format_timestamp, timestamp_seconds
from app.graphs.meeting_chat.graph import answer_from_transcript
from app.graphs.summary.graph import generate_meeting_overview, generate_summary_text
from app.graphs.summary.state import Mode
from app.schemas.meetings import PriorityReason, SearchMatch, StoredMeetingSummary, SummaryPage, TopicSuggestion, TopicSuggestionsResponse
from app.schemas.transcripts import TranscriptSegment
from app.services import priority, retrieval
from app.services.database import get_summary, list_summaries, list_summaries_for_priority, max_meeting_date

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

def _split(field: object) -> list[str]:
    return [item.strip() for item in str(field).split(",") if item.strip()]

def _row_to_summary(row: dict[str, object], *, priority_score: float | None = None, priority_tier: str | None = None, priority_reason: PriorityReason | None = None, match: SearchMatch | None = None) -> StoredMeetingSummary:
    data = dict(row)
    data.pop("topic_embedding", None)
    data["participants"] = _split(data["participants"])
    data["keywords"] = _split(data["keywords"])
    return StoredMeetingSummary(**data, priority_score=priority_score, priority_tier=priority_tier, priority_reason=priority_reason, match=match)

MAX_TOPIC_LENGTH = 200
MAX_QUERY_LENGTH = 200

# Minimum cosine for a meeting to match the search bar on meaning alone, with
# no literal mention. Calibrated on this corpus with the local MiniLM model:
# at 0.45 a query like "bond yields rising" finds the handful of meetings
# about it, while unrelated queries ("vacation plans") match nothing.
SEARCH_MIN_SIMILARITY = 0.45


def _normalize_topics(topics: list[str] | None) -> list[str]:
    """Drop blank/whitespace-only topics and bound each topic's length.

    Truncating (rather than rejecting) long topics keeps the endpoint
    permissive while still bounding worst-case embedding-cache growth.
    """
    return [t.strip()[:MAX_TOPIC_LENGTH] for t in (topics or []) if t.strip()]


def _search_match(match: retrieval.MeetingMatch) -> SearchMatch:
    source = match.lexical_source or "related"
    moment = match.moment
    # A literal hit in the overview is visible in the row already; only point
    # into the transcript when that is where the evidence is.
    if source in ("transcript", "related") and moment is not None:
        return SearchMatch(source=source, snippet=moment.snippet, start=moment.start)  # type: ignore[arg-type]
    return SearchMatch(source=source)  # type: ignore[arg-type]

def _search(rows: list[dict[str, object]], query: str) -> dict[str, tuple[int, SearchMatch]]:
    """Meetings matching a search, as id -> (relevance rank, why it matched).

    A meeting matches when the query appears literally in its overview or
    transcript, or when it is close enough in meaning on its own.
    """
    ranked = retrieval.rank_meetings(query, [
        retrieval.MeetingText(
            meeting_id=str(row["meeting_id"]),
            title=str(row["title"]),
            summary=str(row["simple_summary"]),
            keywords=_split(row["keywords"]),
            participants=_split(row["participants"]),
            topic_embedding=row.get("topic_embedding"),  # type: ignore[arg-type]
        )
        for row in rows
    ])
    matched = [
        match for match in ranked
        if match.lexical_source is not None or match.semantic >= SEARCH_MIN_SIMILARITY
    ]
    return {match.meeting_id: (rank, _search_match(match)) for rank, match in enumerate(matched)}

TopicInput = tuple[str, np.ndarray, dict[str, retrieval.TopicEvidence]]

def _topic_priority(
    row: dict[str, object], topic_inputs: list[TopicInput],
) -> tuple[float | None, PriorityReason | None]:
    """A meeting's priority: its best score across topics, and why.

    Combines the overview similarity with transcript evidence (see
    priority.combine). A meeting with neither an overview embedding nor a
    transcript index has nothing to score and gets None.
    """
    meeting_id = str(row["meeting_id"])
    blob = row.get("topic_embedding")
    meeting_vector = priority.blob_to_vector(blob) if blob else None  # type: ignore[arg-type]

    best: tuple[float, PriorityReason] | None = None
    for topic, topic_vector, evidence_by_meeting in topic_inputs:
        evidence = evidence_by_meeting.get(meeting_id)
        summary_cosine = 0.0
        if meeting_vector is not None:
            try:
                summary_cosine = priority.cosine_similarity(meeting_vector, topic_vector)
            except ValueError:
                # A stored embedding from a previous, different-dimension
                # model. Degrade gracefully instead of 500ing the whole page.
                logger.warning(
                    "Skipping overview similarity for %s: stored embedding dimension mismatch",
                    meeting_id,
                )
                meeting_vector = None
        if meeting_vector is None and evidence is None:
            continue

        chunk_cosine = evidence.chunk_cosine if evidence else None
        mentions = evidence.mentions if evidence else 0
        score = priority.combine(summary_cosine, chunk_cosine, mentions)
        if best is not None and score <= best[0]:
            continue
        if mentions:
            kind = "mentioned"
        elif chunk_cosine is not None and chunk_cosine > summary_cosine:
            kind = "discussed"
        else:
            kind = "summary"
        moment = evidence.moment if evidence and kind != "summary" else None
        best = (score, PriorityReason(
            topic=topic,
            kind=kind,  # type: ignore[arg-type]
            mentions=mentions,
            start=moment.start if moment else None,
            snippet=moment.snippet if moment else None,
        ))
    return (best[0], best[1]) if best else (None, None)

def get_stored_summaries(
    page: int,
    page_size: int,
    period: Literal["day", "week", "30d", "all"] = "all",
    topics: list[str] | None = None,
    sort: Literal["priority", "time"] = "priority",
    query: str | None = None,
) -> SummaryPage:
    date_from = {
        "day": date.today().isoformat(),
        "week": (date.today() - timedelta(days=6)).isoformat(),
        "30d": (date.today() - timedelta(days=29)).isoformat(),
        "all": None,
    }[period]

    topics = _normalize_topics(topics)
    query = (query or "").strip()[:MAX_QUERY_LENGTH]

    if not topics and not query:
        rows, total = list_summaries(offset=(page - 1) * page_size, limit=page_size, date_from=date_from)
        items = [_row_to_summary(row) for row in rows]
        return SummaryPage(items=items, total=total, page=page, page_size=page_size)

    all_rows = list_summaries_for_priority(date_from=date_from)
    matches: dict[str, tuple[int, SearchMatch]] = {}
    if query:
        matches = _search(all_rows, query)
        all_rows = [row for row in all_rows if row["meeting_id"] in matches]

    meeting_ids = [str(row["meeting_id"]) for row in all_rows]
    topic_inputs = [
        (topic, priority.embed_topic(topic), retrieval.topic_evidence(topic, meeting_ids))
        for topic in topics
    ]
    scored: list[tuple[float | None, str | None, PriorityReason | None, dict[str, object]]] = []
    for row in all_rows:
        score, reason = _topic_priority(row, topic_inputs)
        tier = priority.tier_for_score(score) if score is not None else None
        scored.append((score, tier, reason, row))

    if sort == "priority" and topics:
        # Mentions break ties: meetings that only clear the mention cap
        # all share one score, and the one naming the topic most often is
        # the one most about it.
        scored.sort(
            key=lambda entry: (
                entry[0] if entry[0] is not None else -1.0,
                entry[2].mentions if entry[2] else 0,
            ),
            reverse=True,
        )
    elif sort == "priority":
        # Searching without topics: the most relevant meeting first.
        scored.sort(key=lambda entry: matches[str(entry[3]["meeting_id"])][0])
    # sort == "time": `all_rows` (and therefore `scored`) is already ordered
    # by meeting_date DESC, refreshed_at DESC from list_summaries_for_priority,
    # so no re-sort is needed — every row is still scored above regardless.

    total = len(scored)
    start = (page - 1) * page_size
    page_slice = scored[start:start + page_size]
    items = [
        _row_to_summary(
            row,
            priority_score=score,
            priority_tier=tier,
            priority_reason=reason,
            match=matches[str(row["meeting_id"])][1] if query else None,
        )
        for score, tier, reason, row in page_slice
    ]
    return SummaryPage(items=items, total=total, page=page, page_size=page_size)

def get_stored_summary(meeting_id: str) -> StoredMeetingSummary | None:
    """One stored meeting overview, or None when it has not been processed."""
    row = get_summary(meeting_id)
    return _row_to_summary(row) if row else None

def caption_to_segment(caption: Caption) -> TranscriptSegment:
    t = format_timestamp(timestamp_seconds(caption.start))
    speaker, separator, rest = caption.text.partition(":")
    sp, tx = (speaker.strip(), rest.strip()) if separator else ("", caption.text)
    # The raw cue bounds travel alongside the display string: the chat agent
    # quotes them verbatim, so the UI needs them to resolve a citation to a cue.
    return TranscriptSegment(t=t, sp=sp, tx=tx, start=caption.start, end=caption.end)


# Topic suggestions come from the keywords the summary step already extracts,
# so they cost no model call. The window is anchored to the newest meeting,
# not today, for the same reason as the "last day" scope: meeting_date is
# when a meeting was synced into the catalog.
SUGGESTION_WINDOW_DAYS = 7
SUGGESTION_MIN_MEETINGS = 2
# Keywords this close in meaning are one suggestion ("volatility" and
# "implied volatility" sit at ~0.92). Aliases such as NVDA/Nvidia score far
# lower with this model, so they are deliberately not merged.
SUGGESTION_DUPLICATE_SIMILARITY = 0.85

def topic_suggestions(limit: int = 8) -> TopicSuggestionsResponse:
    """The keywords most meetings in the recent window share, most common first.

    Participant names are dropped — the summary step sometimes lists a
    speaker as a keyword — and so is any keyword that duplicates a more
    common one in meaning. When the recent window is too thin to fill the
    list, the whole catalog is used instead.
    """
    anchor = max_meeting_date()
    if anchor is None:
        return TopicSuggestionsResponse(suggestions=[])
    date_from = (date.fromisoformat(anchor) - timedelta(days=SUGGESTION_WINDOW_DAYS - 1)).isoformat()

    suggestions = _rank_keywords(list_summaries_for_priority(date_from=date_from), limit)
    if len(suggestions) < limit:
        date_from = None
        suggestions = _rank_keywords(list_summaries_for_priority(), limit)
    return TopicSuggestionsResponse(suggestions=suggestions, date_from=date_from, date_to=anchor)

def _rank_keywords(rows: list[dict[str, object]], limit: int) -> list[TopicSuggestion]:
    names = {name.casefold() for row in rows for name in _split(row["participants"])}
    counts: dict[str, int] = {}
    # The spelling most meetings used, so "CPI" is not shown as "cpi".
    spellings: dict[str, dict[str, int]] = {}
    for row in rows:
        for keyword in set(_split(row["keywords"])):
            folded = keyword.casefold()
            if folded in names:
                continue
            counts[folded] = counts.get(folded, 0) + 1
            variants = spellings.setdefault(folded, {})
            variants[keyword] = variants.get(keyword, 0) + 1

    ranked = sorted(
        (folded for folded, count in counts.items() if count >= SUGGESTION_MIN_MEETINGS),
        key=lambda folded: (-counts[folded], folded),
    )
    chosen: list[tuple[str, np.ndarray]] = []
    for folded in ranked:
        if len(chosen) >= limit:
            break
        vector = priority.embed_topic(folded)
        if any(
            priority.cosine_similarity(vector, other) >= SUGGESTION_DUPLICATE_SIMILARITY
            for _, other in chosen
        ):
            continue
        chosen.append((folded, vector))

    return [
        TopicSuggestion(
            topic=max(spellings[folded], key=lambda spelling: (spellings[folded][spelling], spelling)),
            meetings=counts[folded],
        )
        for folded, _ in chosen
    ]
