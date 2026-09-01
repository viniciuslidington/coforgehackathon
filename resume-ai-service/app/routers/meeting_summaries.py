"""Routes for browsing, syncing, and querying persisted meeting summaries.

This is the flow the frontend actually drives: the meeting list, its
transcript, and per-meeting Q&A, all backed by what's stored in the database.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Iterator, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError

from app.core.vtt import duration_seconds, parse_vtt, participants_from_captions, transcript_from_captions
from app.graphs.meeting_chat.graph import MEETING_CHAT_RECURSION_LIMIT, chat_graph
from app.graphs.meeting_chat.prompts import (
    CHAT_EMPTY_ANSWER_MESSAGE,
    CHAT_GAVE_UP_MESSAGE,
    INITIAL_STEP_LABEL,
    SYNTHESIS_STEP_LABEL,
    TOOL_STEP_LABELS,
)
from app.schemas.agent import AnswerEvent, ErrorEvent, QuestionRequest, StepEvent
from app.schemas.meetings import RefreshResponse, StoredMeetingSummary, SummaryPage
from app.schemas.transcripts import TranscriptSegment
from app.services.database import delete_summary, get_summary, summary_exists, summary_has_keywords, upsert_summary
from app.services.meeting_service import caption_to_segment, compute_topic_embedding_blob, execute_overview, get_stored_summaries, get_stored_summary
from app.services.r2_storage import get_r2_vtt_content, list_r2_vtt_files
from app.services.sse import message_text, sse
from app.services.transcripts import transcript_repository

logger = logging.getLogger("meeting-insights")

router = APIRouter(tags=["meeting-summaries"])

def _sync_from_r2(*, limit: int | None) -> RefreshResponse:
    """Store meetings from R2-hosted VTTs that have not already been processed.

    Stops after `limit` newly-processed meetings when given, otherwise
    processes every file in the bucket.
    """
    processed = 0
    skipped = 0
    file_keys = list_r2_vtt_files()
    total = len(file_keys)
    logger.info("Starting meeting sync from R2: total_available=%d limit=%s", total, limit)
    for file_key in file_keys:
        if limit is not None and processed >= limit:
            break
        meeting_id = file_key.removesuffix(".vtt")
        if summary_exists(meeting_id) and summary_has_keywords(meeting_id):
            skipped += 1
            logger.info(
                "Skipping meeting %s (%d/%d): summary already has keywords and duration",
                meeting_id,
                processed + skipped,
                total,
            )
            continue
        logger.info(
            "Processing meeting %s (%d/%d): processed=%d skipped=%d",
            meeting_id,
            processed + skipped + 1,
            total,
            processed,
            skipped,
        )
        captions = parse_vtt(get_r2_vtt_content(file_key))
        transcript = transcript_from_captions(captions)
        title, simple_summary, keywords = execute_overview(transcript)
        participants = participants_from_captions(captions)
        duration = duration_seconds(captions)
        topic_embedding = compute_topic_embedding_blob(f"{title} {simple_summary} {' '.join(keywords)}")
        upsert_summary(meeting_id=meeting_id, title=title, meeting_date=date.today().isoformat(), participants=participants, simple_summary=simple_summary, keywords=keywords, duration_seconds=duration, topic_embedding=topic_embedding)
        processed += 1
        logger.info(
            "Stored meeting %s: title=%r participants=%s duration_seconds=%d keywords=%s",
            meeting_id,
            title,
            participants,
            duration,
            keywords,
        )
    page = get_stored_summaries(page=1, page_size=20)
    logger.info(
        "Meeting sync complete: processed=%d skipped=%d total_stored=%d",
        processed,
        skipped,
        page.total,
    )
    return RefreshResponse(processed=processed, skipped=skipped, total_stored=page.total, items=page.items)

@router.post("/sync-meetings", response_model=RefreshResponse)
def refresh_meetings() -> RefreshResponse:
    """Store every R2-hosted meeting that has not already been processed."""
    return _sync_from_r2(limit=None)

@router.post("/sync-meetings/batch", response_model=RefreshResponse)
def sync_meetings_batch(limit: int = Query(..., gt=0, description="Exact number of new meetings to process")) -> RefreshResponse:
    """Store at most `limit` newly-processed R2-hosted meetings."""
    return _sync_from_r2(limit=limit)

@router.delete("/meetings/{meeting_id}")
def remove_meeting_summary(meeting_id: str) -> dict[str, str]:
    """Delete a processed meeting summary, allowing it to be reprocessed."""
    if not delete_summary(meeting_id):
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found in database.")
    return {"status": "success", "message": f"Meeting '{meeting_id}' deleted successfully."}

@router.get("/meeting-summaries", response_model=SummaryPage)
def get_meeting_summaries(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    period: Literal["day", "week", "30d", "all"] = "all",
    topics: list[str] | None = Query(None, max_length=10),
    sort: Literal["priority", "time"] = "priority",
) -> SummaryPage:
    """Return persisted meeting overviews, filtered by meeting date and paginated.

    When `topics` is given, each item also carries `priority_score`/`priority_tier`.
    `sort` controls ordering: "priority" orders by relevance to those topics
    (computed deterministically, no LLM); "time" orders by meeting date
    regardless of whether topics are active.
    """
    return get_stored_summaries(page, page_size, period, topics, sort)

@router.get("/meeting-summaries/{meeting_id}", response_model=StoredMeetingSummary)
def get_meeting_summary(meeting_id: str) -> StoredMeetingSummary:
    """Return one stored meeting overview.

    Lets the UI open a meeting cited in a chat answer even when that meeting
    is not on the currently rendered page of the table.
    """
    summary = get_stored_summary(meeting_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found.")
    return summary

@router.get("/meeting-summaries/{meeting_id}/transcript", response_model=list[TranscriptSegment])
def get_meeting_transcript(meeting_id: str) -> list[TranscriptSegment]:
    """Return timestamped, speaker-attributed segments for a stored meeting."""
    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for meeting '{meeting_id}'.")
    return [caption_to_segment(caption) for caption in captions]

@router.post("/meeting-summaries/{meeting_id}/questions")
def ask_meeting_question(meeting_id: str, request: QuestionRequest) -> StreamingResponse:
    """Stream an agent answer grounded in one stored meeting and its chat session."""
    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for meeting '{meeting_id}'.")
    transcript = transcript_from_captions(captions)
    summary = get_summary(meeting_id) or {}
    metadata = {
        "meeting_id": meeting_id,
        "title": summary.get("title"),
        "date": summary.get("meeting_date"),
        "participants": [
            item.strip()
            for item in str(summary.get("participants", "")).split(",")
            if item.strip()
        ] or participants_from_captions(captions),
        "duration_seconds": summary.get("duration_seconds", duration_seconds(captions)),
        "keywords": [
            item.strip()
            for item in str(summary.get("keywords", "")).split(",")
            if item.strip()
        ],
    }
    graph_input = {
        "meeting_id": meeting_id,
        "transcript": transcript,
        "captions": [
            {"start": caption.start, "end": caption.end, "text": caption.text}
            for caption in captions
        ],
        "metadata": metadata,
        "messages": [HumanMessage(content=request.question)],
    }
    config: RunnableConfig = {
        "configurable": {"thread_id": request.session_id},
        "recursion_limit": MEETING_CHAT_RECURSION_LIMIT,
    }

    def event_stream() -> Iterator[str]:
        yield sse(StepEvent(label=INITIAL_STEP_LABEL))
        try:
            for update in chat_graph.stream(graph_input, config=config, stream_mode="updates"):
                agent_update = update.get("agent")
                if agent_update:
                    for message in agent_update.get("messages", []):
                        if not isinstance(message, AIMessage):
                            continue
                        if message.tool_calls:
                            for tool_call in message.tool_calls:
                                tool_name = tool_call.get("name", "")
                                label = TOOL_STEP_LABELS.get(tool_name, "Consulting a tool…")
                                yield sse(StepEvent(label=label))
                        else:
                            yield sse(StepEvent(label=SYNTHESIS_STEP_LABEL))
                synthesis_update = update.get("synthesize")
                if synthesis_update:
                    for message in synthesis_update.get("messages", []):
                        if not isinstance(message, AIMessage):
                            continue
                        text = message_text(message)
                        if not text.strip():
                            yield sse(ErrorEvent(detail=CHAT_EMPTY_ANSWER_MESSAGE))
                            continue
                        yield sse(AnswerEvent(text=text, caption_count=len(captions)))
        except GraphRecursionError:
            # Caught ahead of the RuntimeError passthrough below, which it would
            # otherwise satisfy: GraphRecursionError subclasses RecursionError,
            # and its message names a `recursion_limit` config key that means
            # nothing to the person reading the answer.
            logger.exception("Meeting chat exhausted its steps for meeting=%s", meeting_id)
            yield sse(ErrorEvent(detail=CHAT_GAVE_UP_MESSAGE))
        except Exception as exc:
            logger.exception("Meeting chat stream failed for meeting=%s", meeting_id)
            detail = str(exc) if isinstance(exc, RuntimeError) else "Could not complete the response."
            yield sse(ErrorEvent(detail=detail))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
