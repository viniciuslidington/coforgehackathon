from __future__ import annotations

import struct

from app.services import database
from app.services.meeting_service import compute_topic_embedding_blob, get_stored_summaries


def _seed(meeting_id: str, text: str) -> None:
    database.upsert_summary(
        meeting_id=meeting_id, title=text, meeting_date="2026-08-24",
        participants=[], simple_summary=text, keywords=[],
        duration_seconds=60, topic_embedding=compute_topic_embedding_blob(text),
    )


def test_no_topics_returns_summaries_without_priority_fields(db_path):
    _seed("m1", "Quarterly budget review")
    page = get_stored_summaries(page=1, page_size=10)
    assert page.items[0].priority_score is None
    assert page.items[0].priority_tier is None


def test_topics_attach_priority_fields(db_path):
    _seed("m1", "Quarterly budget review with finance")
    page = get_stored_summaries(page=1, page_size=10, topics=["budget"])
    assert page.items[0].priority_score is not None
    assert page.items[0].priority_tier is not None


def test_sorting_by_priority_ranks_more_relevant_meeting_first(db_path):
    _seed("unrelated", "Team watched a documentary about deep sea fish")
    _seed("related", "Quarterly budget review with finance and cost overruns")
    page = get_stored_summaries(page=1, page_size=10, topics=["budget"])
    ids_in_order = [item.meeting_id for item in page.items]
    assert ids_in_order.index("related") < ids_in_order.index("unrelated")


def test_priority_sort_is_correct_across_pagination(db_path):
    # 3 meetings, page_size=1: the single most relevant one must land on page 1
    # regardless of insertion/date order — proves sorting happens before slicing.
    _seed("low", "Team watched a documentary about deep sea fish")
    _seed("mid", "General staff meeting notes")
    _seed("high", "Quarterly budget review with finance and cost overruns")
    page_one = get_stored_summaries(page=1, page_size=1, topics=["budget"])
    assert page_one.items[0].meeting_id == "high"
    assert page_one.total == 3


def test_meeting_without_topic_embedding_has_no_priority_when_topics_active(db_path):
    database.upsert_summary(
        meeting_id="legacy", title="Old meeting", meeting_date="2026-08-24",
        participants=[], simple_summary="no embedding computed", keywords=[],
        duration_seconds=60,
    )
    page = get_stored_summaries(page=1, page_size=10, topics=["budget"])
    assert page.items[0].priority_score is None
    assert page.items[0].priority_tier is None


def test_blank_and_whitespace_topics_are_ignored_like_no_topics(db_path):
    _seed("m1", "Quarterly budget review")
    page = get_stored_summaries(page=1, page_size=10, topics=["", "   "])
    assert page.items[0].priority_score is None
    assert page.items[0].priority_tier is None


def test_overlong_topic_is_truncated_not_rejected(db_path):
    _seed("m1", "Quarterly budget review with finance")
    long_topic = "budget " + ("x" * 500)
    # Should not raise, and should still attach priority fields (truncated
    # topic text still embeds successfully).
    page = get_stored_summaries(page=1, page_size=10, topics=[long_topic])
    assert page.items[0].priority_score is not None


def test_sort_time_orders_by_meeting_date_even_with_topics_active(db_path):
    database.upsert_summary(
        meeting_id="older", title="Team watched a documentary about deep sea fish",
        meeting_date="2026-08-20", participants=[], simple_summary="unrelated",
        keywords=[], duration_seconds=60,
        topic_embedding=compute_topic_embedding_blob("Team watched a documentary about deep sea fish"),
    )
    database.upsert_summary(
        meeting_id="newer", title="Quarterly budget review with finance and cost overruns",
        meeting_date="2026-08-24", participants=[], simple_summary="related",
        keywords=[], duration_seconds=60,
        topic_embedding=compute_topic_embedding_blob("Quarterly budget review with finance and cost overruns"),
    )
    # By priority, "newer" (more relevant) should be first.
    priority_page = get_stored_summaries(page=1, page_size=10, topics=["budget"], sort="priority")
    assert priority_page.items[0].meeting_id == "newer"
    # By time, the most recent meeting_date should be first regardless of
    # relevance — and both items must still carry priority fields.
    time_page = get_stored_summaries(page=1, page_size=10, topics=["budget"], sort="time")
    assert time_page.items[0].meeting_id == "newer"
    assert time_page.items[1].meeting_id == "older"
    assert all(item.priority_score is not None for item in time_page.items)


def test_dimension_mismatch_degrades_to_no_priority_instead_of_raising(db_path):
    # A well-formed but wrong-dimension vector (two nonzero float32s, not the
    # current model's real output dimension) — simulates a stored embedding
    # from a previous model. Must not have a zero norm, or cosine_similarity's
    # own zero-denominator guard would short-circuit before reaching np.dot.
    mismatched_dim_blob = struct.pack("<2f", 1.0, 1.0)
    database.upsert_summary(
        meeting_id="bad-dim", title="Old model meeting", meeting_date="2026-08-24",
        participants=[], simple_summary="stored with a different-dimension model",
        keywords=[], duration_seconds=60, topic_embedding=mismatched_dim_blob,
    )
    page = get_stored_summaries(page=1, page_size=10, topics=["budget"])
    assert page.items[0].priority_score is None
    assert page.items[0].priority_tier is None
