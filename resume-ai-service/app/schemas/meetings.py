from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

class SearchMatch(BaseModel):
    """Why a meeting matched a search, and where to look.

    `start` is set when the evidence is a moment in the transcript, so the UI
    can open the meeting at that cue.
    """
    source: Literal["title", "keywords", "participants", "summary", "transcript", "related"]
    snippet: str | None = None
    start: str | None = None

class StoredMeetingSummary(BaseModel):
    meeting_id: str
    title: str
    meeting_date: str
    participants: list[str]
    simple_summary: str
    keywords: list[str]
    duration_seconds: int
    refreshed_at: str
    priority_score: float | None = None
    priority_tier: Literal["urgent", "high", "normal"] | None = None
    match: SearchMatch | None = None

class SummaryPage(BaseModel):
    items: list[StoredMeetingSummary]
    total: int
    page: int
    page_size: int

class RefreshResponse(BaseModel):
    processed: int
    skipped: int
    total_stored: int
    items: list[StoredMeetingSummary]
