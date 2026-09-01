"""The transcript endpoint must expose anchors a chat citation can resolve to.

`t` is lossy on purpose (display only), so these tests pin the raw cue bounds
that the UI matches a `[HH:MM:SS.mmm]` citation against.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.vtt import Caption
from app.main import app
from app.services.meeting_service import caption_to_segment
from app.services.transcripts import transcript_repository

client = TestClient(app)

VTT = (
    "WEBVTT\n\n"
    "00:12:45.500 --> 00:12:56.300\nJames: We closed the entire Dell position.\n\n"
    "00:14:06.700 --> 00:14:10.400\nAlex: I'll watch the order flow into the bell.\n"
)


def test_caption_to_segment_keeps_raw_bounds_beside_display_time():
    segment = caption_to_segment(
        Caption(start="00:12:45.500", end="00:12:56.300", text="James: We closed it.")
    )
    assert segment.start == "00:12:45.500"
    assert segment.end == "00:12:56.300"
    # `t` is lossy, and not merely by truncation: 765.5s rounds to 766 under
    # banker's rounding, so the display reads a second later than the cue
    # actually starts. Matching a citation against it would be wrong here.
    assert segment.t == "12:46"
    assert segment.sp == "James"
    assert segment.tx == "We closed it."


def test_caption_without_speaker_still_carries_bounds():
    segment = caption_to_segment(
        Caption(start="00:00:01.000", end="00:00:04.000", text="No speaker prefix here")
    )
    assert (segment.start, segment.end) == ("00:00:01.000", "00:00:04.000")
    assert segment.sp == ""
    assert segment.tx == "No speaker prefix here"


def test_transcript_endpoint_returns_bounds(db_path, monkeypatch):
    monkeypatch.setattr("app.routers.meeting_summaries.list_r2_vtt_files", lambda: ["m1.vtt"])
    monkeypatch.setattr("app.routers.meeting_summaries.get_r2_vtt_content", lambda key: VTT)
    monkeypatch.setattr(
        "app.routers.meeting_summaries.execute_overview",
        lambda transcript: ("Dell desk sync", "The team closed the Dell position.", ["dell"]),
    )
    client.post("/sync-meetings")
    # The repository caches parsed captions per meeting, so clear it before
    # pointing R2 at this fixture.
    monkeypatch.setattr("app.services.transcripts.get_r2_vtt_content", lambda key: VTT)
    transcript_repository._cache.clear()

    response = client.get("/meeting-summaries/m1/transcript")
    assert response.status_code == 200
    segments = response.json()
    assert [(s["start"], s["end"]) for s in segments] == [
        ("00:12:45.500", "00:12:56.300"),
        ("00:14:06.700", "00:14:10.400"),
    ]
    # A citation of "00:14:06.700" must land on the second cue, not the first.
    assert segments[1]["tx"].startswith("I'll watch the order flow")
