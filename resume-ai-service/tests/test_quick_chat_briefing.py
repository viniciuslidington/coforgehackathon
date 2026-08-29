"""Briefing generation: labelled-line parsing, map-reduce, and truncation."""
from __future__ import annotations

import pytest

from app.graphs.quick_chat import briefing as briefing_module
from app.graphs.quick_chat.briefing import (
    BRIEFING_DIRECT_LIMIT,
    generate_briefing,
    stream_briefing,
)
from app.services.meeting_scope import MeetingCard

WELL_FORMED = """PARAGRAPH1: The desk traded through a heavy EUR/USD session.
PARAGRAPH2: Spreads widened and two desks disagreed on the hedge.
PARAGRAPH3: One block trade is still unanswered before the cutoff.
POINT: urgent | Answer the CITI-FX block | [[meeting:m0]]
POINT: teal | Flatten the 2s10s steepener |
POINT: nonsense | Liquidity thinning into the close |
"""


class StubModel:
    """Stands in for ChatOpenAI, counting calls and replaying canned text."""

    def __init__(self, responses: list[str], finish_reason: str = "stop") -> None:
        self.responses = responses
        self.finish_reason = finish_reason
        self.calls = 0

    def invoke(self, _messages):
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return type(
            "Response",
            (),
            {
                "content": self.responses[index],
                "response_metadata": {"finish_reason": self.finish_reason},
            },
        )()


def _cards(count: int) -> list[MeetingCard]:
    return [
        MeetingCard(
            meeting_id=f"m{index}",
            title=f"Meeting {index}",
            meeting_date="2026-08-27",
            participants=["Alex"],
            simple_summary=f"Summary {index}.",
            keywords=["eurusd"],
            duration_seconds=60,
            refreshed_at="2026-08-27T20:00:00+00:00",
            topic_embedding=None,
        )
        for index in range(count)
    ]


@pytest.fixture()
def stub_model(monkeypatch):
    def install(responses: list[str], finish_reason: str = "stop") -> StubModel:
        model = StubModel(responses, finish_reason)
        monkeypatch.setattr(briefing_module, "get_model", lambda **_kwargs: model)
        return model

    return install


def test_parses_three_paragraphs_and_key_points(stub_model) -> None:
    stub_model([WELL_FORMED])

    draft = generate_briefing(_cards(3))

    assert draft.summary.split("\n\n") == [
        "The desk traded through a heavy EUR/USD session.",
        "Spreads widened and two desks disagreed on the hedge.",
        "One block trade is still unanswered before the cutoff.",
    ]
    assert [(p.tone, p.meeting_id) for p in draft.key_points] == [
        ("urgent", "m0"),
        ("teal", None),
        ("muted", None),  # an unrecognized tone degrades rather than raising
    ]


def test_empty_scope_never_calls_the_model(stub_model) -> None:
    model = stub_model([WELL_FORMED])

    draft = generate_briefing([])

    assert model.calls == 0
    assert "No meetings" in draft.summary


def test_malformed_response_degrades_instead_of_raising(stub_model) -> None:
    stub_model(["PARAGRAPH1: Only one paragraph.\nPOINT: broken\nPOINT: urgent | Kept |"])

    draft = generate_briefing(_cards(2))

    assert draft.summary == "Only one paragraph."
    assert [point.text for point in draft.key_points] == ["Kept"]


def test_response_with_no_labels_falls_back_to_raw_text(stub_model) -> None:
    stub_model(["The model ignored the format entirely."])

    draft = generate_briefing(_cards(2))

    assert draft.summary == "The model ignored the format entirely."
    assert draft.key_points == []


def test_key_points_are_capped(stub_model) -> None:
    many = "PARAGRAPH1: A.\n" + "\n".join(
        f"POINT: muted | Point {index} |" for index in range(20)
    )
    stub_model([many])

    assert len(generate_briefing(_cards(2)).key_points) == 6


def test_small_scope_uses_a_single_call(stub_model) -> None:
    model = stub_model([WELL_FORMED])

    generate_briefing(_cards(BRIEFING_DIRECT_LIMIT))

    assert model.calls == 1


def test_large_scope_maps_then_reduces(stub_model) -> None:
    model = stub_model(["digest", "digest", "digest", WELL_FORMED])

    generate_briefing(_cards(50))  # 3 batches of 20 -> 3 digests + 1 reduce

    assert model.calls == 4


def test_truncated_response_is_flagged(stub_model) -> None:
    stub_model([WELL_FORMED], finish_reason="length")

    assert generate_briefing(_cards(2)).truncated is True


def test_stream_emits_steps_before_the_draft(stub_model) -> None:
    """Steps must arrive as work happens, not batched at the end."""
    stub_model(["digest", "digest", "digest", WELL_FORMED])

    kinds = [kind for kind, _payload in stream_briefing(_cards(50))]

    assert kinds[-1] == "draft"
    assert kinds.count("step") == 4  # one per batch, plus the reduce
    assert "draft" not in kinds[:-1]


def test_a_marker_inside_the_bullet_text_is_extracted_not_left_inline(stub_model) -> None:
    """The model routinely writes the marker in the bullet instead of field 3."""
    stub_model([
        "PARAGRAPH1: A.\n"
        "POINT: teal | Analyze dark pool activity [[meeting:m0]] |"
    ])

    point = generate_briefing(_cards(2)).key_points[0]

    assert point.text == "Analyze dark pool activity"
    assert point.meeting_id == "m0"


def test_the_dedicated_marker_field_still_wins(stub_model) -> None:
    stub_model(["PARAGRAPH1: A.\nPOINT: urgent | Answer it | [[meeting:m1]]"])

    point = generate_briefing(_cards(3)).key_points[0]

    assert point.text == "Answer it"
    assert point.meeting_id == "m1"


def test_a_bullet_that_is_only_a_marker_is_dropped(stub_model) -> None:
    stub_model(["PARAGRAPH1: A.\nPOINT: teal | [[meeting:m0]] |\nPOINT: teal | Real point |"])

    points = generate_briefing(_cards(2)).key_points

    assert [point.text for point in points] == ["Real point"]
