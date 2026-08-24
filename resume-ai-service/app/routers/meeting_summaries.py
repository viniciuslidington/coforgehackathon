"""Routes for browsing, syncing, and querying persisted meeting summaries.

This is the flow the frontend actually drives: the meeting list, its
transcript, and per-meeting Q&A, all backed by what's stored in the database.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.core.vtt import duration_seconds, parse_vtt, participants_from_captions, transcript_from_captions
from app.schemas.agent import MeetingResponse, QuestionRequest
from app.schemas.meetings import RefreshResponse, SummaryPage
from app.schemas.transcripts import TranscriptSegment
from app.services.database import delete_summary, summary_exists, summary_has_keywords, upsert_summary
from app.services.meeting_service import caption_to_segment, execute_chat, execute_overview, get_stored_summaries
from app.services.r2_storage import get_r2_vtt_content, list_r2_vtt_files
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
        upsert_summary(meeting_id=meeting_id, title=title, meeting_date=date.today().isoformat(), participants=participants, simple_summary=simple_summary, keywords=keywords, duration_seconds=duration)
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
