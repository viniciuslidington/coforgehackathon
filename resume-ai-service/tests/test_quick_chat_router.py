"""Quick Chat endpoints: SSE framing, marker validation, and cache behaviour."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.main import app
from app.routers import quick_chat as router_module
from app.services.database import upsert_summary

SESSION = "11111111-1111-1111-1111-111111111111"


@pytest.fixture()
def client(db_path: Path) -> TestClient:
    return TestClient(app)


def _seed(meeting_id: str = "m1", title: str = "EUR/USD block") -> None:
    upsert_summary(
        meeting_id=meeting_id,
        title=title,
        meeting_date="2026-08-27",
        participants=["Alex"],
        simple_summary="Alex flagged an unanswered block trade.",
        keywords=["eurusd"],
        duration_seconds=60,
    )


def _frames(text: str) -> list[dict]:
    """Parse the bare `data: {json}` SSE format both routers emit."""
    events = []
    for frame in text.split("\n\n"):
        payload = "\n".join(
            line.removeprefix("data:").strip()
            for line in frame.splitlines()
            if line.startswith("data:")
        )
        if payload:
            events.append(json.loads(payload))
    return events


class FakeGraph:
    """Replays a scripted node sequence in the shape LangGraph streams."""

    def __init__(self, answer_text: str) -> None:
        self.answer_text = answer_text

    def stream(self, _graph_input, config=None, stream_mode=None):
        yield {"agent": {"messages": [
            AIMessage(content="", tool_calls=[
                {"name": "search_scope", "args": {}, "id": "call-1"}
            ])
        ]}}
        yield {"synthesize": {"messages": [AIMessage(content=self.answer_text)]}}


def test_lookup_resolves_scope_without_a_cached_briefing(client: TestClient) -> None:
    _seed()

    response = client.post(
        "/quick-chat/briefings/lookup", json={"scope": {"kind": "last_n", "count": 5}}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["briefing"] is None
    assert body["scope"]["meeting_count"] == 1
    assert body["scope"]["fingerprint"]


def test_lookup_reports_unknown_explicit_ids(client: TestClient) -> None:
    _seed()

    body = client.post("/quick-chat/briefings/lookup", json={
        "scope": {"kind": "explicit", "meeting_ids": ["m1", "ghost"]}
    }).json()

    assert body["scope"]["meeting_ids"] == ["m1"]
    assert body["scope"]["missing_meeting_ids"] == ["ghost"]


def test_date_range_reversed_bounds_are_rejected(client: TestClient) -> None:
    response = client.post("/quick-chat/briefings/lookup", json={
        "scope": {"kind": "date_range", "date_from": "2026-08-27", "date_to": "2026-08-01"}
    })

    assert response.status_code == 422


def test_question_stream_emits_step_frames_then_an_answer(
    client: TestClient, monkeypatch
) -> None:
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph("All clear."))

    response = client.post("/quick-chat/questions", json={
        "question": "What needs my answer?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    })

    events = _frames(response.text)
    assert [event["type"] for event in events] == ["step", "step", "answer"]
    assert events[-1]["text"] == "All clear."
    assert events[-1]["meeting_count"] == 1


def test_a_valid_meeting_marker_survives_and_is_reported(
    client: TestClient, monkeypatch
) -> None:
    _seed()
    monkeypatch.setattr(
        router_module, "quick_chat_graph", FakeGraph("See [[meeting:m1]] for detail.")
    )

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert "[[meeting:m1]]" in answer["text"]
    assert answer["referenced_meetings"] == [
        {"meeting_id": "m1", "title": "EUR/USD block", "meeting_date": "2026-08-27"}
    ]


def test_a_hallucinated_meeting_marker_never_reaches_the_client(
    client: TestClient, monkeypatch
) -> None:
    """The model invents ids; the server is the gate that removes them."""
    _seed()
    monkeypatch.setattr(
        router_module, "quick_chat_graph", FakeGraph("Per [[meeting:invented]], act now.")
    )

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert "invented" not in answer["text"]
    assert "[[" not in answer["text"]
    assert answer["text"] == "Per, act now."
    assert answer["referenced_meetings"] == []


def test_a_marker_naming_a_title_is_repaired_to_its_id(
    client: TestClient, monkeypatch
) -> None:
    _seed()
    monkeypatch.setattr(
        router_module, "quick_chat_graph", FakeGraph("See [[meeting:EUR/USD block]].")
    )

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert "[[meeting:m1]]" in answer["text"]


def test_empty_scope_answers_without_invoking_the_graph(
    client: TestClient, monkeypatch
) -> None:
    def explode(*_args, **_kwargs):  # pragma: no cover - must never run
        raise AssertionError("the graph ran for an empty scope")

    monkeypatch.setattr(router_module.quick_chat_graph, "stream", explode)

    events = _frames(client.post("/quick-chat/questions", json={
        "question": "Anything for me?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)

    assert [event["type"] for event in events] == ["answer"]
    assert events[0]["meeting_count"] == 0
    assert "no meetings" in events[0]["text"].lower()


def test_briefing_is_served_from_cache_on_the_second_request(
    client: TestClient, monkeypatch
) -> None:
    _seed()
    calls = {"count": 0}

    def fake_stream(cards):
        calls["count"] += 1
        yield "step", "Summarizing…"
        yield "draft", router_module_draft()

    def router_module_draft():
        from app.graphs.quick_chat.briefing import BriefingDraft, KeyPointDraft
        return BriefingDraft(
            summary="One.\n\nTwo.\n\nThree.",
            key_points=[KeyPointDraft(text="Answer it", tone="urgent", meeting_id="m1")],
        )

    monkeypatch.setattr(
        "app.services.quick_chat_service.stream_briefing", fake_stream
    )
    scope = {"scope": {"kind": "last_n", "count": 5}}

    first = _frames(client.post("/quick-chat/briefings", json=scope).text)
    assert [event["type"] for event in first] == ["step", "briefing"]
    assert first[-1]["briefing"]["cached"] is False
    assert calls["count"] == 1

    lookup = client.post("/quick-chat/briefings/lookup", json=scope).json()
    assert lookup["briefing"]["cached"] is True
    assert lookup["briefing"]["summary"] == "One.\n\nTwo.\n\nThree."

    second = _frames(client.post("/quick-chat/briefings", json=scope).text)
    assert [event["type"] for event in second] == ["briefing"]
    assert calls["count"] == 1  # the cache hit spent no model call


def test_force_bypasses_the_cache(client: TestClient, monkeypatch) -> None:
    _seed()
    calls = {"count": 0}

    def fake_stream(cards):
        from app.graphs.quick_chat.briefing import BriefingDraft
        calls["count"] += 1
        yield "draft", BriefingDraft(summary="Regenerated.")

    monkeypatch.setattr("app.services.quick_chat_service.stream_briefing", fake_stream)

    client.post("/quick-chat/briefings", json={"scope": {"kind": "last_n", "count": 5}})
    client.post("/quick-chat/briefings", json={
        "scope": {"kind": "last_n", "count": 5}, "force": True
    })

    assert calls["count"] == 2


def test_a_title_written_beside_its_own_marker_is_not_duplicated(
    client: TestClient, monkeypatch
) -> None:
    """The UI renders the marker as the title, so both would read twice."""
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        'The most urgent is "EUR/USD block" [[meeting:m1]], flagged by Alex.'
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "The most urgent is [[meeting:m1]], flagged by Alex."


def test_an_unquoted_title_beside_its_marker_is_also_removed(
    client: TestClient, monkeypatch
) -> None:
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "See EUR/USD block [[meeting:m1]] for detail."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "See [[meeting:m1]] for detail."


def test_a_title_mentioned_away_from_its_marker_is_left_alone(
    client: TestClient, monkeypatch
) -> None:
    """Only an adjacent duplicate is noise; prose elsewhere is the answer."""
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "The EUR/USD block was busy. Alex spoke in [[meeting:m1]]."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "Which meeting?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "The EUR/USD block was busy. Alex spoke in [[meeting:m1]]."


def test_a_grouped_marker_without_the_prefix_is_normalized(
    client: TestClient, monkeypatch
) -> None:
    """The model packs several ids into one marker and drops the prefix."""
    _seed("m1", "EUR/USD block")
    _seed("m2", "Dark pool alert")
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Rotation is underway [[m1, m2]]."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "Rotation is underway [[meeting:m1]][[meeting:m2]]."
    assert {m["meeting_id"] for m in answer["referenced_meetings"]} == {"m1", "m2"}


def test_a_grouped_marker_drops_only_its_unknown_ids(
    client: TestClient, monkeypatch
) -> None:
    _seed("m1", "EUR/USD block")
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Per [[m1, ghost]] we act."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "Per [[meeting:m1]] we act."
    assert [m["meeting_id"] for m in answer["referenced_meetings"]] == ["m1"]


def test_inline_citations_are_capped_but_all_are_still_referenced(
    client: TestClient, monkeypatch
) -> None:
    """Linking a dozen titles mid-sentence would bury the prose."""
    for index in range(5):
        _seed(f"m{index}", f"Meeting {index}")
    group = ", ".join(f"m{index}" for index in range(5))
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(f"Broad move [[{group}]]."))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 10},
    }).text)[-1]

    assert answer["text"].count("[[meeting:") == 3
    assert len(answer["referenced_meetings"]) == 5


def test_unrelated_bracketed_text_is_left_untouched(
    client: TestClient, monkeypatch
) -> None:
    """A loose pattern must not mangle prose that was never a citation."""
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "The desk uses [[TODO]] notation internally."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "The desk uses [[TODO]] notation internally."


def test_a_truncated_meeting_id_is_repaired_by_prefix(
    client: TestClient, monkeypatch
) -> None:
    """The model drops the trailing name; ids start with a unique sequence."""
    _seed("00021_convo_2p_Chris", "Rebalance talk")
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Rotation underway [[00021_convo_2p]]."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "Rotation underway [[meeting:00021_convo_2p_Chris]]."
    assert answer["referenced_meetings"][0]["title"] == "Rebalance talk"


def test_an_ambiguous_id_prefix_is_not_guessed(client: TestClient, monkeypatch) -> None:
    """Two candidates means we cannot know which was meant — drop it."""
    _seed("00021_convo_2p_Chris", "First")
    _seed("00021_convo_2p_Olivia", "Second")
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Rotation underway [[00021_convo_2p]]."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "Rotation underway."
    assert answer["referenced_meetings"] == []


def test_an_unresolvable_id_shaped_marker_becomes_prose(
    client: TestClient, monkeypatch
) -> None:
    """Bare id-shaped groups are citations even without the prefix."""
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Per [[00999_convo_9p_Nobody]] we act."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert "[[" not in answer["text"]
    assert answer["text"] == "Per we act."


def test_a_chain_of_adjacent_markers_is_capped(client: TestClient, monkeypatch) -> None:
    """The model chains single markers as well as grouping ids."""
    for index in range(6):
        _seed(f"m{index}", f"Meeting {index}")
    chain = "".join(f"[[meeting:m{index}]]" for index in range(6))
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(f"Broad move {chain}."))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 10},
    }).text)[-1]

    assert answer["text"].count("[[meeting:") == 3
    assert len(answer["referenced_meetings"]) == 6


def test_the_cap_applies_per_run_not_per_paragraph(client: TestClient, monkeypatch) -> None:
    """Separate sentences each get their own citations."""
    for index in range(6):
        _seed(f"m{index}", f"Meeting {index}")
    first = "".join(f"[[meeting:m{index}]]" for index in range(4))
    second = "".join(f"[[meeting:m{index}]]" for index in range(4, 6))
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        f"One {first}. Two {second}."
    ))

    text = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 10},
    }).text)[-1]["text"]

    one, two = text.split(". ")
    assert one.count("[[meeting:") == 3   # trimmed from four
    assert two.count("[[meeting:") == 2   # already under the cap


def test_malformed_bracket_debris_is_swept(client: TestClient, monkeypatch) -> None:
    """The model also emits unbalanced brackets the marker pattern misses."""
    _seed("m1", "EUR/USD block")
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "Volatility rose [[meeting:m1]][00032]] across the desk."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "Volatility rose [[meeting:m1]] across the desk."


def test_ordinary_bracketed_prose_survives_the_sweep(
    client: TestClient, monkeypatch
) -> None:
    """Only id-shaped bracket content is debris."""
    _seed()
    monkeypatch.setattr(router_module, "quick_chat_graph", FakeGraph(
        "The note said [see appendix] and [[TODO]] remains."
    ))

    answer = _frames(client.post("/quick-chat/questions", json={
        "question": "What happened?",
        "session_id": SESSION,
        "scope": {"kind": "last_n", "count": 5},
    }).text)[-1]

    assert answer["text"] == "The note said [see appendix] and [[TODO]] remains."
