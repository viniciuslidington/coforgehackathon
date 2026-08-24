from __future__ import annotations

from pydantic import BaseModel

class TranscriptSegment(BaseModel):
    t: str
    sp: str
    tx: str
