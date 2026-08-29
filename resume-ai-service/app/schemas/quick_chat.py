"""Request/response models for the scoped Quick Chat agent and its briefings.

A "meeting scope" is the set of meetings the agent may read. The client picks
one of four selections; the server resolves it to a concrete, ordered list of
meeting ids plus a content fingerprint used as the briefing cache key.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

MAX_SCOPE_MEETINGS = 100


class LastNScope(BaseModel):
    kind: Literal["last_n"] = "last_n"
    count: int = Field(5, ge=1, le=50)


class LastDayScope(BaseModel):
    """The newest day present in the data, plus the day before it.

    Anchored to `MAX(meeting_date)` rather than today: `meeting_date` records
    when a meeting was synced, not when it happened, so a wall-clock window
    silently resolves to zero meetings whenever syncing has paused.
    """
    kind: Literal["last_day"] = "last_day"


class DateRangeScope(BaseModel):
    kind: Literal["date_range"] = "date_range"
    date_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ExplicitScope(BaseModel):
    """Exactly the meetings the client names — the current table page."""
    kind: Literal["explicit"] = "explicit"
    meeting_ids: list[str] = Field(min_length=1, max_length=MAX_SCOPE_MEETINGS)


MeetingScopeSelection = Annotated[
    LastNScope | LastDayScope | DateRangeScope | ExplicitScope,
    Field(discriminator="kind"),
]


class ScopeResolution(BaseModel):
    fingerprint: str
    meeting_ids: list[str]
    meeting_count: int
    range_start: str | None = None
    range_end: str | None = None
    resolved_at: str
    truncated: bool = False
    missing_meeting_ids: list[str] = Field(default_factory=list)


class ReferencedMeeting(BaseModel):
    meeting_id: str
    title: str
    meeting_date: str


class KeyPoint(BaseModel):
    text: str
    tone: Literal["urgent", "teal", "muted"] = "muted"
    meeting_id: str | None = None


class BriefingResponse(BaseModel):
    summary: str
    key_points: list[KeyPoint] = Field(default_factory=list)
    referenced_meetings: list[ReferencedMeeting] = Field(default_factory=list)
    scope: ScopeResolution
    cached: bool = False
    truncated: bool = False
    created_at: str


class BriefingLookupRequest(BaseModel):
    scope: MeetingScopeSelection


class BriefingLookupResponse(BaseModel):
    """Scope resolution plus the cached briefing, if one exists.

    Deliberately one round trip: it drives the initial render, every scope
    switch, and the "too many meetings" banner count. It never calls the LLM.
    """
    scope: ScopeResolution
    briefing: BriefingResponse | None = None


class BriefingRequest(BaseModel):
    scope: MeetingScopeSelection
    force: bool = False


class BriefingEvent(BaseModel):
    """Terminal frame of `POST /quick-chat/briefings`."""
    type: Literal["briefing"] = "briefing"
    briefing: BriefingResponse


class QuickChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    session_id: str = Field(min_length=8, max_length=128)
    scope: MeetingScopeSelection


class QuickChatAnswerEvent(BaseModel):
    """Terminal frame of `POST /quick-chat/questions`."""
    type: Literal["answer"] = "answer"
    text: str
    referenced_meetings: list[ReferencedMeeting] = Field(default_factory=list)
    meeting_count: int
