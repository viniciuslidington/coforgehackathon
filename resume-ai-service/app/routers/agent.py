"""Stateless prototype endpoints: summarize or question a directly-uploaded transcript.

Predates the persisted meeting-summaries flow; kept for direct .vtt upload
demos. Not used by the frontend.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.vtt import parse_vtt, transcript_from_captions
from app.graphs.summary.state import Mode
from app.schemas.agent import MeetingResponse
from app.services.meeting_service import execute_chat, execute_summary

router = APIRouter(tags=["agent"])

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

@router.post("/summaries", response_model=MeetingResponse)
async def create_summary(vtt_file: UploadFile = File(...), mode: Mode = Form("simple"), focus_points: str | None = Form(None)) -> MeetingResponse:
    """Create a simple or detailed meeting summary from a .vtt upload."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_summary(transcript, mode, focus_points), caption_count=caption_count)

@router.post("/questions", response_model=MeetingResponse)
async def ask_question(vtt_file: UploadFile = File(...), question: str = Form(..., min_length=2)) -> MeetingResponse:
    """Answer one question strictly from the uploaded VTT transcript."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_chat(transcript, question), caption_count=caption_count)
