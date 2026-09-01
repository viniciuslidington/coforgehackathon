"""Timestamp citations in Quick Chat answers.

A Quick Chat answer spans many meetings, so a moment must name the meeting it
belongs to. These pin the deterministic gate: a citation only survives when the
meeting is in scope *and* the transcript actually contains the moment.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.vtt import Caption
from app.main import app
from app.routers import quick_chat as router_module
from app.services.database import upsert_summary
from app.services.meeting_scope import MeetingCard
from app.services.quick_chat_service import resolve_markers

from tests.test_quick_chat_router import SESSION, FakeGraph, _frames


def _card(meeting_id: str, title: str) -> MeetingCard:
    return MeetingCard(
        meeting_id=meeting_id, title=title, meeting_date="2026-08-27",
        participants=[], keywords=[], simple_summary="",
        refreshed_at="2026-08-27T00:00:00+00:00", duration_seconds=600,
        topic_embedding=None,
    )


CARDS = {"m1": _card("m1", "EUR/USD block"), "m2": _card("m2", "Options flow hoot")}

CAPTIONS = {
    "m1": [
        Caption(start="00:06:00.600", end="00:06:08.500", text="Jessica: trim the position"),
        Caption(start="00:06:08.800", end="00:06:12.300", text="Emma: on it"),
    ],
    "m2": [Caption(start="00:02:14.000", end="00:02:20.000", text="Mike: vol is spiking")],
}


def _captions(meeting_id: str) -> list[Caption] | None:
    return CAPTIONS.get(meeting_id)


def _resolve(text: str):
    return resolve_markers(text, CARDS, captions_for=_captions)


def test_a_cited_moment_backed_by_a_cue_survives() -> None:
    text, referenced = _resolve("Jessica said [[meeting:m1@00:06:00.600-00:06:08.500]] to trim.")

    # Normalized to an en dash, matching what the transcript itself uses.
    assert text == "Jessica said [[meeting:m1@00:06:00.600–00:06:08.500]] to trim."
    assert [meeting.meeting_id for meeting in referenced] == ["m1"]


def test_a_single_point_citation_keeps_its_moment() -> None:
    text, _ = _resolve("Emma answered [[meeting:m1@00:06:08.800]].")
    assert text == "Emma answered [[meeting:m1@00:06:08.800]]."


def test_a_moment_no_cue_supports_degrades_to_a_plain_meeting_link() -> None:
    """The meeting is real, so keep it; only the invented moment is dropped."""
    text, referenced = _resolve("Per [[meeting:m1@00:99:00.000]] we act.")

    assert text == "Per [[meeting:m1]] we act."
    assert [meeting.meeting_id for meeting in referenced] == ["m1"]


def test_a_timestamp_on_an_unknown_meeting_is_dropped_whole() -> None:
    text, referenced = _resolve("Per [[meeting:ghost@00:06:00.600]] we act.")

    assert "[[" not in text
    assert text == "Per we act."
    assert referenced == []


def test_a_bare_timestamp_is_attributed_to_the_meeting_just_cited() -> None:
    text, _ = _resolve("In [[meeting:m1]], Emma placed it [00:06:08.800-00:06:12.300].")

    assert text == (
        "In [[meeting:m1]], Emma placed it "
        "[[meeting:m1@00:06:08.800–00:06:12.300]]."
    )


def test_a_bare_timestamp_with_nothing_cited_before_it_stays_prose() -> None:
    text, referenced = _resolve("Someone said it at [00:06:00.600] today.")

    assert text == "Someone said it at [00:06:00.600] today."
    assert referenced == []


def test_a_bare_timestamp_absent_from_the_cited_meeting_stays_prose() -> None:
    """Attribution by position is a guess; the transcript is what settles it."""
    text, _ = _resolve("In [[meeting:m2]], see [00:06:00.600].")

    assert text == "In [[meeting:m2]], see [00:06:00.600]."


def test_moments_from_different_meetings_keep_their_own_ids() -> None:
    text, referenced = _resolve(
        "[[meeting:m1@00:06:00.600]] then [[meeting:m2@00:02:14.000]]."
    )

    assert "[[meeting:m1@00:06:00.600]]" in text
    assert "[[meeting:m2@00:02:14.000]]" in text
    assert [meeting.meeting_id for meeting in referenced] == ["m1", "m2"]


def test_a_title_written_beside_a_timestamped_marker_is_still_removed() -> None:
    text, _ = _resolve('See "EUR/USD block" [[meeting:m1@00:06:00.600]] now.')
    assert text == "See [[meeting:m1@00:06:00.600]] now."


def test_validation_never_refetches_a_meetings_captions() -> None:
    calls: list[str] = []

    def counting(meeting_id: str) -> list[Caption] | None:
        calls.append(meeting_id)
        return CAPTIONS.get(meeting_id)

    resolve_markers(
        "[[meeting:m1@00:06:00.600]] and [[meeting:m1@00:06:08.800]] and [00:06:00.600].",
        CARDS,
        captions_for=counting,
    )

    assert calls == ["m1"]


def test_the_endpoint_validates_moments_against_the_real_transcript(
    client_and_seed, monkeypatch
) -> None:
    client = client_and_seed
    monkeypatch.setattr(
        "app.services.quick_chat_service.transcript_repository.get_captions",
        lambda meeting_id: CAPTIONS.get("m1"),
    )
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Jessica said [[meeting:m1@00:06:00.600-00:06:08.500]], "
        "but [[meeting:m1@00:99:00.000]] is invented."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "When was it said?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert "[[meeting:m1@00:06:00.600–00:06:08.500]]" in answer["text"]
    assert "00:99:00.000" not in answer["text"]


@pytest.fixture()
def client_and_seed(db_path) -> TestClient:
    upsert_summary(
        meeting_id="m1", title="EUR/USD block", meeting_date="2026-08-27",
        participants=["Alex"], simple_summary="Alex flagged a block trade.",
        keywords=["eurusd"], duration_seconds=60,
    )
    return TestClient(app)
