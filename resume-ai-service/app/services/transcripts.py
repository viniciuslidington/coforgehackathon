"""Transcript lookup, abstracted from where captions actually live.

Callers depend only on TranscriptRepository. Captions are resolved from the
R2 bucket the transcript generator writes into.
"""
from __future__ import annotations

from typing import Protocol

from app.core.vtt import Caption, parse_vtt
from app.services.r2_storage import get_r2_vtt_content


class TranscriptRepository(Protocol):
    def get_captions(self, meeting_id: str) -> list[Caption] | None: ...


class R2TranscriptRepository:
    """Resolves captions from R2-hosted meeting VTTs, uploaded by the transcript generator.

    Meeting ids are the object key without its ".vtt" suffix. Parsed captions
    are cached in memory so repeat requests skip the network round trip.
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[Caption]] = {}

    def get_captions(self, meeting_id: str) -> list[Caption] | None:
        if meeting_id in self._cache:
            return self._cache[meeting_id]
        try:
            raw_vtt = get_r2_vtt_content(f"{meeting_id}.vtt")
        except Exception:
            return None
        captions = parse_vtt(raw_vtt)
        self._cache[meeting_id] = captions
        return captions


transcript_repository: TranscriptRepository = R2TranscriptRepository()
