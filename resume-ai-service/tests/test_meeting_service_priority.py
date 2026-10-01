from __future__ import annotations

import struct

import pytest

from app.core.vtt import Caption
from app.services import database, priority
from app.services.meeting_service import compute_topic_embedding_blob, get_stored_summaries
from app.services.transcript_index import index_meeting


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


def _store(meeting_id: str, summary: str, lines: list[str] | None = None) -> None:
    database.upsert_summary(
        meeting_id=meeting_id, title=meeting_id, meeting_date="2026-09-01", participants=[],
        simple_summary=summary, keywords=[], duration_seconds=60,
        topic_embedding=compute_topic_embedding_blob(summary),
    )
    if lines is not None:
        index_meeting(meeting_id, [
            Caption(start=f"00:00:{index:02d}.000", end=f"00:00:{index:02d}.900", text=text)
            for index, text in enumerate(lines)
        ])


def test_a_topic_named_only_in_the_transcript_still_raises_priority(db_path, fake_embedder):
    _store("named", "A quick desk check-in.", ["Ana: Morning.", "Bo: JGB paper looked heavy overnight."])
    _store("silent", "A quick desk check-in.", ["Ana: Morning.", "Bo: Nothing new."])

    page = get_stored_summaries(page=1, page_size=10, topics=["JGB"])

    named, silent = page.items
    assert named.meeting_id == "named"
    assert named.priority_tier in ("high", "urgent")
    assert named.priority_reason is not None
    assert named.priority_reason.kind == "mentioned"
    assert named.priority_reason.mentions == 1
    assert named.priority_reason.start == "00:00:01.000"
    assert "JGB" in (named.priority_reason.snippet or "")
    assert silent.priority_score < named.priority_score
    assert silent.priority_reason is not None
    assert silent.priority_reason.kind != "mentioned"


def test_the_reason_names_the_topic_that_scored_highest(db_path, fake_embedder):
    _store("m1", "Desk check-in.", ["Bo: Brent crude jumped on the OPEC headline."])

    (item,) = get_stored_summaries(page=1, page_size=10, topics=["lunch", "Energy & Crude"]).items

    assert item.priority_reason is not None
    assert item.priority_reason.topic == "Energy & Crude"


def test_an_unindexed_meeting_keeps_the_summary_only_score(db_path, fake_embedder):
    _store("m1", "Treasuries and yields all morning.")

    (item,) = get_stored_summaries(page=1, page_size=10, topics=["rates"]).items

    expected = priority.score_meeting(
        priority.blob_to_vector(compute_topic_embedding_blob("Treasuries and yields all morning.")),
        [priority.embed_topic("rates")],
    )
    assert item.priority_score == pytest.approx(expected)
    assert item.priority_reason is not None
    assert item.priority_reason.kind == "summary"
    assert item.priority_reason.start is None


def test_ties_on_score_are_broken_by_mentions(db_path, fake_embedder):
    _store("few", "Check-in.", [f"Ana: inflation {n}" for n in range(1)] + ["Bo: ok"])
    _store("many", "Check-in.", [f"Ana: {'word ' * 80} inflation" for _ in range(9)])

    items = get_stored_summaries(page=1, page_size=10, topics=["inflation"]).items

    assert [item.meeting_id for item in items][0] == "many"
