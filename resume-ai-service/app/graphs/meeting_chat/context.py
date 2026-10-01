"""What the meeting chat model reads about the meeting on each turn.

A short meeting is sent whole: retrieval over a few minutes of talk saves
little and risks missing the one line that matters. A longer meeting is sent
as its opening plus the passages most relevant to the question, and the agent
searches for anything else it needs.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.vtt import Caption, transcript_from_captions
from app.services import retrieval, transcript_index

# Roughly a ten-minute call. Above this, the meeting is sent as excerpts.
INLINE_TRANSCRIPT_CHARS = 8_000
OPENING_CHARS = 1_500
MAX_EXCERPT_CHUNKS = 8


@dataclass(frozen=True)
class MeetingContext:
    # The whole meeting, when it is short enough to send as is.
    transcript: str = ""
    # Otherwise: how the meeting opens, then passages chosen for the question.
    opening: str = ""
    excerpts: str = ""


def _opening(transcript: str) -> str:
    """The first cues of the meeting, cut at a line boundary."""
    if len(transcript) <= OPENING_CHARS:
        return transcript
    cut = transcript.rfind("\n", 0, OPENING_CHARS)
    return transcript[:cut if cut > 0 else OPENING_CHARS]


def build_meeting_context(meeting_id: str, captions: list[Caption], question: str) -> MeetingContext:
    transcript = transcript_from_captions(captions)
    if len(transcript) <= INLINE_TRANSCRIPT_CHARS:
        return MeetingContext(transcript=transcript)
    # Without an index there is nothing to retrieve from; sending the whole
    # meeting is costly but still answers the question.
    if not transcript_index.ensure_indexed(meeting_id):
        return MeetingContext(transcript=transcript)
    hits = retrieval.search_chunks(
        question, [meeting_id], k=MAX_EXCERPT_CHUNKS, per_meeting=MAX_EXCERPT_CHUNKS,
    )
    return MeetingContext(opening=_opening(transcript), excerpts=retrieval.merge_chunks(hits))
