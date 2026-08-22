from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
import os
from typing import Literal
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIStatusError
from pydantic import BaseModel, Field

from app.database import initialize_database, list_summaries, summary_exists, summary_has_keywords, upsert_summary
from app.graph import Mode, generate_meeting_overview, run_meeting_agent
from app.meetings import MEETINGS, get_meeting, load_meeting_transcript, meeting_participants
from app.vtt import parse_vtt, transcript_from_captions

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield

app = FastAPI(title="Meeting Insights API", description="LangGraph-powered summaries and Q&A for WebVTT meeting transcripts.", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

class MeetingResponse(BaseModel):
    result: str
    caption_count: int

class MeetingListItem(BaseModel):
    id: str
    title: str
    description: str

class QuestionRequest(BaseModel):
    question: str = Field(min_length=2)

class StoredMeetingSummary(BaseModel):
    meeting_id: str
    title: str
    meeting_date: str
    participants: list[str]
    simple_summary: str
    keywords: list[str]
    refreshed_at: str

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

async def read_transcript(vtt_file: UploadFile) -> tuple[str, int]:
    if not (vtt_file.filename or "").lower().endswith(".vtt"):
        raise HTTPException(status_code=400, detail="Upload a .vtt WebVTT transcript file.")
    try:
        captions = parse_vtt((await vtt_file.read()).decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="The VTT file must be UTF-8 encoded.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return transcript_from_captions(captions), len(captions)

def execute_agent(transcript: str, mode: Mode, focus_points: str | None, question: str | None) -> str:
    points = [item.strip() for item in (focus_points or "").split(",") if item.strip()]
    try:
        return run_meeting_agent(transcript=transcript, mode=mode, focus_points=points, question=question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        # Do not leak upstream SDK stack traces to API clients; keep the actual
        # provider message, which is actionable for invalid keys/credit limits.
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc.message}") from exc

def execute_overview(transcript: str) -> tuple[str, str]:
    try:
        return generate_meeting_overview(transcript)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc.message}") from exc

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/meetings", response_model=list[MeetingListItem])
def list_meetings() -> list[MeetingListItem]:
    """List built-in sample meetings and their IDs."""
    return [MeetingListItem(id=item.id, title=item.title, description=item.description) for item in MEETINGS.values()]

@app.post("/sync-meetings", response_model=RefreshResponse)
def refresh_meetings() -> RefreshResponse:
    """Store only built-in meetings that have not already been processed."""
    processed = 0
    skipped = 0
    for meeting in MEETINGS.values():
        if summary_exists(meeting.id) and summary_has_keywords(meeting.id):
            skipped += 1
            continue
        transcript, _ = load_meeting_transcript(meeting)
        title, simple_summary, keywords = execute_overview(transcript)
        upsert_summary(meeting_id=meeting.id, title=title, meeting_date=meeting.meeting_date, participants=meeting_participants(meeting), simple_summary=simple_summary, keywords=keywords)
        processed += 1
    page = get_stored_summaries(page=1, page_size=20)
    return RefreshResponse(processed=processed, skipped=skipped, total_stored=page.total, items=page.items)

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

@app.get("/meeting-summaries", response_model=SummaryPage)
def get_meeting_summaries(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100), period: Literal["day", "week", "30d", "all"] = "all") -> SummaryPage:
    """Return persisted meeting overviews, filtered by meeting date and paginated."""
    return get_stored_summaries(page, page_size, period)

def find_sample_meeting(meeting_id: str):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' was not found. Use GET /meetings to list available IDs.")
    return meeting

@app.post("/meetings/{meeting_id}/summaries", response_model=MeetingResponse)
def create_sample_summary(meeting_id: str, mode: Mode = "simple", focus_points: str | None = None) -> MeetingResponse:
    """Create a summary for a built-in meeting selected by ID."""
    transcript, caption_count = load_meeting_transcript(find_sample_meeting(meeting_id))
    return MeetingResponse(result=execute_agent(transcript, mode, focus_points, None), caption_count=caption_count)

@app.post("/meetings/{meeting_id}/questions", response_model=MeetingResponse)
def ask_sample_question(meeting_id: str, request: QuestionRequest) -> MeetingResponse:
    """Ask a question about a built-in meeting selected by ID."""
    transcript, caption_count = load_meeting_transcript(find_sample_meeting(meeting_id))
    return MeetingResponse(result=execute_agent(transcript, "simple", None, request.question), caption_count=caption_count)

@app.post("/summaries", response_model=MeetingResponse)
async def create_summary(vtt_file: UploadFile = File(...), mode: Mode = Form("simple"), focus_points: str | None = Form(None)) -> MeetingResponse:
    """Create a simple or detailed meeting summary from a .vtt upload."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_agent(transcript, mode, focus_points, None), caption_count=caption_count)

@app.post("/questions", response_model=MeetingResponse)
async def ask_question(vtt_file: UploadFile = File(...), question: str = Form(..., min_length=2)) -> MeetingResponse:
    """Answer one question strictly from the uploaded VTT transcript."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_agent(transcript, "simple", None, question), caption_count=caption_count)
