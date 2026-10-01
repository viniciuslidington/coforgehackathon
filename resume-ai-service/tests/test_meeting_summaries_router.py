from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.vtt import Caption
from app.main import app
from app.services import database, priority, transcript_index
from app.services.transcript_index import index_meeting

client = TestClient(app)


def test_sync_stores_topic_embedding(db_path, monkeypatch):
    monkeypatch.setattr("app.routers.meeting_summaries.list_r2_vtt_files", lambda: ["m1.vtt"])
    monkeypatch.setattr("app.routers.meeting_summaries.get_r2_vtt_content", lambda key: "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nAna: Let's talk about the budget.\n")
    monkeypatch.setattr("app.routers.meeting_summaries.execute_overview", lambda transcript: ("Budget sync", "The team discussed the budget.", ["budget"]))

    response = client.post("/sync-meetings")
    assert response.status_code == 200

    rows, _ = database.list_summaries(offset=0, limit=10)
    assert rows[0]["topic_embedding"] is not None


def test_list_endpoint_without_topics_omits_priority(db_path, monkeypatch):
    monkeypatch.setattr("app.routers.meeting_summaries.list_r2_vtt_files", lambda: ["m1.vtt"])
    monkeypatch.setattr("app.routers.meeting_summaries.get_r2_vtt_content", lambda key: "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nAna: Let's talk about the budget.\n")
    monkeypatch.setattr("app.routers.meeting_summaries.execute_overview", lambda transcript: ("Budget sync", "The team discussed the budget.", ["budget"]))
    client.post("/sync-meetings")

    response = client.get("/meeting-summaries")
    assert response.status_code == 200
    assert response.json()["items"][0]["priority_score"] is None


def test_list_endpoint_with_topics_includes_priority(db_path, monkeypatch):
    monkeypatch.setattr("app.routers.meeting_summaries.list_r2_vtt_files", lambda: ["m1.vtt"])
    monkeypatch.setattr("app.routers.meeting_summaries.get_r2_vtt_content", lambda key: "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nAna: Let's talk about the budget.\n")
    monkeypatch.setattr("app.routers.meeting_summaries.execute_overview", lambda transcript: ("Budget sync", "The team discussed the budget.", ["budget"]))
    client.post("/sync-meetings")

    response = client.get("/meeting-summaries", params={"topics": ["budget"]})
    assert response.status_code == 200
    assert response.json()["items"][0]["priority_score"] is not None


def _seed(meeting_id: str, title: str, summary: str, lines: list[tuple[str, str]], meeting_date: str = "2026-09-01") -> None:
    database.upsert_summary(
        meeting_id=meeting_id, title=title, meeting_date=meeting_date,
        participants=["Ana"], simple_summary=summary, keywords=[], duration_seconds=60,
        topic_embedding=priority.vector_to_blob(priority.embed_passages([f"{title} {summary}"])[0]),
    )
    index_meeting(meeting_id, [
        Caption(start=start, end=start.replace(".000", ".900"), text=text) for start, text in lines
    ])


@pytest.fixture()
def searchable(db_path, fake_embedder):
    _seed("m1", "Rates huddle", "Morning rates check.", [
        ("00:00:01.000", "Ana: Quick check on the curve."),
        ("00:00:42.000", "Bo: Nomura showed a bid in JGBs."),
    ], meeting_date="2026-09-03")
    _seed("m2", "Energy desk", "Brent crude update.", [
        ("00:00:01.000", "Cy: OPEC headline hit the tape."),
    ], meeting_date="2026-09-02")
    _seed("m3", "Lunch order", "Who wants pizza.", [
        ("00:00:01.000", "Di: Sandwich for me."),
    ], meeting_date="2026-09-01")


def test_search_finds_a_meeting_by_what_was_said_and_points_at_the_moment(searchable):
    body = client.get("/meeting-summaries", params={"q": "Nomura"}).json()

    assert body["total"] == 1
    (item,) = body["items"]
    assert item["meeting_id"] == "m1"
    assert item["match"] == {
        "source": "transcript",
        "snippet": "Bo: Nomura showed a bid in JGBs.",
        "start": "00:00:42.000",
    }


def test_search_reports_an_overview_match_without_a_moment(searchable):
    (item,) = client.get("/meeting-summaries", params={"q": "Energy"}).json()["items"]

    assert item["match"] == {"source": "title", "snippet": None, "start": None}


def test_search_without_a_match_returns_an_empty_page(searchable):
    body = client.get("/meeting-summaries", params={"q": "zebra"}).json()

    assert body == {"items": [], "total": 0, "page": 1, "page_size": 15}


def test_search_paginates_over_matches_only(searchable):
    first = client.get("/meeting-summaries", params={"q": "e", "page_size": 1}).json()

    assert first["total"] >= 2
    assert len(first["items"]) == 1


def test_search_by_time_keeps_date_order(searchable):
    body = client.get("/meeting-summaries", params={"q": "crude oil", "sort": "time"}).json()

    dates = [item["meeting_date"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)


def test_search_and_topics_combine(searchable):
    body = client.get(
        "/meeting-summaries", params={"q": "Nomura", "topics": ["bonds"]},
    ).json()

    (item,) = body["items"]
    assert item["priority_score"] is not None
    assert item["match"]["source"] == "transcript"


def test_without_a_search_items_carry_no_match(searchable):
    items = client.get("/meeting-summaries").json()["items"]

    assert all(item["match"] is None for item in items)


def test_sync_indexes_stored_meetings_without_calling_the_llm(db_path, fake_embedder, monkeypatch):
    database.upsert_summary(
        meeting_id="m1", title="Old", meeting_date="2026-09-01", participants=["Ana"],
        simple_summary="Stored before retrieval existed.", keywords=["budget"], duration_seconds=2,
    )
    monkeypatch.setattr("app.routers.meeting_summaries.list_r2_vtt_files", lambda: ["m1.vtt"])
    monkeypatch.setattr(
        "app.services.transcript_index.transcript_repository.get_captions",
        lambda _id: [Caption(start="00:00:00.000", end="00:00:02.000", text="Ana: budget talk")],
    )
    monkeypatch.setattr(
        "app.routers.meeting_summaries.execute_overview",
        lambda _transcript: (_ for _ in ()).throw(AssertionError("the LLM was called")),
    )

    response = client.post("/sync-meetings")

    assert response.status_code == 200
    assert response.json()["skipped"] == 1
    assert transcript_index.is_indexed("m1")


def _meeting(meeting_id: str, keywords: list[str], meeting_date: str = "2026-09-10", participants: list[str] | None = None) -> None:
    database.upsert_summary(
        meeting_id=meeting_id, title=meeting_id, meeting_date=meeting_date,
        participants=participants or ["Ana"], simple_summary="s", keywords=keywords,
        duration_seconds=60,
    )


def test_topic_suggestions_rank_keywords_by_how_many_meetings_share_them(db_path, fake_embedder):
    _meeting("m1", ["CPI", "Brent"])
    _meeting("m2", ["cpi", "Brent"])
    _meeting("m3", ["CPI", "gold"])
    _meeting("m4", ["gold", "oil"])

    body = client.get("/topic-suggestions", params={"limit": 3}).json()

    assert body["suggestions"] == [
        {"topic": "CPI", "meetings": 3},
        {"topic": "Brent", "meetings": 2},
        {"topic": "gold", "meetings": 2},
    ]


def test_topic_suggestions_skip_one_off_keywords_and_participant_names(db_path, fake_embedder):
    _meeting("m1", ["Ana", "CPI", "once"], participants=["Ana"])
    _meeting("m2", ["Ana", "CPI"], participants=["Ana"])

    topics = [item["topic"] for item in client.get("/topic-suggestions").json()["suggestions"]]

    assert topics == ["CPI"]


def test_topic_suggestions_merge_keywords_with_the_same_meaning(db_path, fake_embedder):
    # The fake model maps "yields" and "treasuries" to the same concept.
    _meeting("m1", ["yields", "treasuries"])
    _meeting("m2", ["yields", "treasuries"])
    _meeting("m3", ["yields"])

    topics = [item["topic"] for item in client.get("/topic-suggestions").json()["suggestions"]]

    assert topics == ["yields"]


def test_topic_suggestions_prefer_recent_meetings_and_fall_back_to_all(db_path, fake_embedder):
    for index in range(2):
        _meeting(f"old{index}", ["oil"], meeting_date="2026-01-01")
        _meeting(f"new{index}", ["gold"], meeting_date="2026-09-10")

    recent = client.get("/topic-suggestions", params={"limit": 1}).json()
    padded = client.get("/topic-suggestions", params={"limit": 2}).json()

    assert [item["topic"] for item in recent["suggestions"]] == ["gold"]
    assert recent["date_from"] == "2026-09-04"
    assert {item["topic"] for item in padded["suggestions"]} == {"gold", "oil"}
    assert padded["date_from"] is None


def test_topic_suggestions_are_empty_without_meetings(db_path):
    assert client.get("/topic-suggestions").json()["suggestions"] == []
