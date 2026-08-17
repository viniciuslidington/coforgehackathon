"""Catalog of built-in demo meetings addressable through stable API IDs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.vtt import parse_vtt, transcript_from_captions

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

@dataclass(frozen=True)
class Meeting:
    id: str
    title: str
    description: str
    filename: str
    meeting_date: str

MEETINGS: dict[str, Meeting] = {
    "product-planning": Meeting(
        id="product-planning",
        title="Weekly Product Planning",
        description="Onboarding experiment, billing migration risk, and action owners.",
        filename="product-planning.vtt",
        meeting_date="2026-08-10",
    ),
    "customer-feedback": Meeting(
        id="customer-feedback",
        title="Education Customer Feedback Review",
        description="Interview findings, September release priorities, and follow-ups.",
        filename="customer-feedback.vtt",
        meeting_date="2026-08-11",
    ),
}

def get_meeting(meeting_id: str) -> Meeting | None:
    return MEETINGS.get(meeting_id)

def load_meeting_transcript(meeting: Meeting) -> tuple[str, int]:
    captions = parse_vtt((SAMPLES_DIR / meeting.filename).read_text(encoding="utf-8"))
    return transcript_from_captions(captions), len(captions)

def meeting_participants(meeting: Meeting) -> list[str]:
    """Get unique speaker names in first-appearance order from VTT cue text."""
    captions = parse_vtt((SAMPLES_DIR / meeting.filename).read_text(encoding="utf-8"))
    names: list[str] = []
    for caption in captions:
        possible_name, separator, _ = caption.text.partition(":")
        name = possible_name.strip()
        if separator and name and name not in names:
            names.append(name)
    return names
