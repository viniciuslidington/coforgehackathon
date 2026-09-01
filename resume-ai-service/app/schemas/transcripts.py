from __future__ import annotations

from pydantic import BaseModel

class TranscriptSegment(BaseModel):
    """One transcript cue.

    `t` is for display ("12:45"): elapsed, rounded to the second, and dropping
    the hour when the meeting is shorter than one. `start`/`end` are the raw VTT
    cue bounds ("00:12:45.500"), kept because the chat agent cites those exact
    strings back and the UI has to map a citation to the cue it names — which
    `t` cannot do, having lost the milliseconds and the end.
    """

    t: str
    sp: str
    tx: str
    start: str
    end: str
