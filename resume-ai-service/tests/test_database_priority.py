from __future__ import annotations

from app.services import database


def test_upsert_summary_persists_topic_embedding(db_path):
    blob = b"\x00\x01\x02\x03"
    database.upsert_summary(
        meeting_id="m1", title="Budget sync", meeting_date="2026-08-24",
        participants=["Ana"], simple_summary="Budget review", keywords=["budget"],
        duration_seconds=120, topic_embedding=blob,
    )
    rows, _ = database.list_summaries(offset=0, limit=10)
    assert rows[0]["topic_embedding"] == blob


def test_upsert_summary_without_embedding_stores_null(db_path):
    database.upsert_summary(
        meeting_id="m1", title="Budget sync", meeting_date="2026-08-24",
        participants=["Ana"], simple_summary="Budget review", keywords=["budget"],
        duration_seconds=120,
    )
    rows, _ = database.list_summaries(offset=0, limit=10)
    assert rows[0]["topic_embedding"] is None


def test_list_summaries_for_priority_ignores_pagination(db_path):
    for index in range(3):
        database.upsert_summary(
            meeting_id=f"m{index}", title=f"Meeting {index}", meeting_date="2026-08-24",
            participants=[], simple_summary="summary", keywords=[],
            duration_seconds=60, topic_embedding=b"\x01\x02\x03\x04",
        )
    rows = database.list_summaries_for_priority(date_from=None)
    assert len(rows) == 3
    assert all(row["topic_embedding"] == b"\x01\x02\x03\x04" for row in rows)


def test_list_summaries_for_priority_applies_date_filter(db_path):
    database.upsert_summary(
        meeting_id="old", title="Old", meeting_date="2020-01-01",
        participants=[], simple_summary="s", keywords=[], duration_seconds=1,
    )
    database.upsert_summary(
        meeting_id="new", title="New", meeting_date="2026-08-24",
        participants=[], simple_summary="s", keywords=[], duration_seconds=1,
    )
    rows = database.list_summaries_for_priority(date_from="2026-01-01")
    assert [row["meeting_id"] for row in rows] == ["new"]
