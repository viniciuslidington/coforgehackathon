from __future__ import annotations

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
