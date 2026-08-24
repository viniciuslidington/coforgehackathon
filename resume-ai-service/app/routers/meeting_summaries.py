"""Routes for browsing, syncing, and querying persisted meeting summaries.

This is the flow the frontend actually drives: the meeting list, its
transcript, and per-meeting Q&A, all backed by what's stored in the database.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.core.vtt import transcript_from_captions
from app.schemas.agent import MeetingResponse, QuestionRequest
from app.schemas.meetings import MeetingListItem, RefreshResponse, SummaryPage
from app.schemas.transcripts import TranscriptSegment
from app.services.database import summary_exists, summary_has_keywords, upsert_summary
from app.services.meeting_service import caption_to_segment, execute_chat, execute_overview, get_stored_summaries
from app.services.sample_meetings import MEETINGS, load_meeting_transcript, meeting_duration_seconds, meeting_participants
from app.services.transcripts import transcript_repository

logger = logging.getLogger("meeting-insights")

router = APIRouter(tags=["meeting-summaries"])

@router.get("/meetings", response_model=list[MeetingListItem])
def list_meetings() -> list[MeetingListItem]:
    """List built-in sample meetings and their IDs."""
    return [MeetingListItem(id=item.id, title=item.title, description=item.description) for item in MEETINGS.values()]

@router.post("/sync-meetings", response_model=RefreshResponse)
def refresh_meetings() -> RefreshResponse:
    """Store only built-in meetings that have not already been processed."""
    processed = 0
    skipped = 0
    total = len(MEETINGS)
    logger.info("Starting meeting sync: total_available=%d", total)
    for meeting in MEETINGS.values():
        if summary_exists(meeting.id) and summary_has_keywords(meeting.id):
            skipped += 1
            logger.info(
                "Skipping meeting %s (%d/%d): summary already has keywords and duration",
                meeting.id,
                processed + skipped,
                total,
            )
            continue
        logger.info(
            "Processing meeting %s (%d/%d): processed=%d skipped=%d",
            meeting.id,
            processed + skipped + 1,
            total,
            processed,
            skipped,
        )
        transcript, _ = load_meeting_transcript(meeting)
        title, simple_summary, keywords = execute_overview(transcript)
        participants = meeting_participants(meeting)
        duration = meeting_duration_seconds(meeting)
        upsert_summary(meeting_id=meeting.id, title=title, meeting_date=meeting.meeting_date, participants=participants, simple_summary=simple_summary, keywords=keywords, duration_seconds=duration)
        processed += 1
        logger.info(
            "Stored meeting %s: title=%r participants=%s duration_seconds=%d keywords=%s",
            meeting.id,
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

@router.get("/meeting-summaries", response_model=SummaryPage)
def get_meeting_summaries(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100), period: Literal["day", "week", "30d", "all"] = "all") -> SummaryPage:
    """Return persisted meeting overviews, filtered by meeting date and paginated."""
    return get_stored_summaries(page, page_size, period)

@router.get("/meeting-summaries/{meeting_id}/transcript", response_model=list[TranscriptSegment])
def get_meeting_transcript(meeting_id: str) -> list[TranscriptSegment]:
    """Return timestamped, speaker-attributed segments for a stored meeting."""
    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for meeting '{meeting_id}'.")
    return [caption_to_segment(caption) for caption in captions]

@router.post("/meeting-summaries/{meeting_id}/questions", response_model=MeetingResponse)
def ask_meeting_question(meeting_id: str, request: QuestionRequest) -> MeetingResponse:
    """Answer one question grounded in a stored meeting's full transcript."""
    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for meeting '{meeting_id}'.")
    transcript = transcript_from_captions(captions)
    return MeetingResponse(result=execute_chat(transcript, request.question), caption_count=len(captions))
