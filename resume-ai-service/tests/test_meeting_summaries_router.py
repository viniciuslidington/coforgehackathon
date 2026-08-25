from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import database

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
