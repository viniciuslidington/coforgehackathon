"""Transcript lookup, abstracted from where captions actually live.

Callers depend only on TranscriptRepository. Today's implementation reads
sample .vtt files from disk; a future DatabaseTranscriptRepository can read
persisted captions instead without changing any caller.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import SAMPLES_DIR
from app.core.vtt import Caption, parse_vtt
from app.services.sample_meetings import get_meeting


class TranscriptRepository(Protocol):
    def get_captions(self, meeting_id: str) -> list[Caption] | None: ...


class FileTranscriptRepository:
    """Resolves captions from the MEETINGS catalog + sample .vtt files on disk.

    Meeting lookup is O(1) via the existing MEETINGS dict; parsed captions are
    cached in memory so repeat requests for the same meeting skip disk I/O and
    re-parsing.
    """

    def __init__(self, samples_dir: Path = SAMPLES_DIR) -> None:
        self._samples_dir = samples_dir
        self._cache: dict[str, list[Caption]] = {}

    def get_captions(self, meeting_id: str) -> list[Caption] | None:
        if meeting_id in self._cache:
            return self._cache[meeting_id]
        meeting = get_meeting(meeting_id)
        if meeting is None:
            return None
        raw_vtt = (self._samples_dir / meeting.filename).read_text(encoding="utf-8")
        captions = parse_vtt(raw_vtt)
        self._cache[meeting_id] = captions
        return captions


transcript_repository: TranscriptRepository = FileTranscriptRepository()
