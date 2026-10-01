from __future__ import annotations

import pytest

from app.core.vtt import Caption
from app.services import priority, retrieval
from app.services.transcript_index import index_meeting

MEETINGS = {
    "rates-call": [
        ("00:00:01.000", "Ana: Morning everyone, quick desk check."),
        ("00:00:05.000", "Ana: Treasuries sold off hard overnight and yields are up."),
        ("00:00:09.000", "Bo: Nomura was showing a bid in ten year JGB paper."),
    ],
    "oil-call": [
        ("00:00:01.000", "Cy: Brent crude jumped after the OPEC headline."),
        ("00:00:05.000", "Di: Barrel spreads are blowing out."),
    ],
    "lunch-chat": [
        ("00:00:01.000", "Ed: Who wants pizza for lunch?"),
        ("00:00:05.000", "Fi: 我们 午饭 吃 什么 野村證券 sandwich please."),
    ],
}


def _caption(start: str, text: str) -> Caption:
    return Caption(start=start, end=start.replace(".000", ".900"), text=text)


@pytest.fixture()
def indexed(db_path, fake_embedder) -> list[str]:
    for meeting_id, lines in MEETINGS.items():
        index_meeting(meeting_id, [_caption(start, text) for start, text in lines])
    return list(MEETINGS)


def test_results_never_include_a_meeting_outside_the_allow_list(indexed) -> None:
    hits = retrieval.search_chunks("crude", ["rates-call", "lunch-chat"])

    assert {hit.meeting_id for hit in hits} <= {"rates-call", "lunch-chat"}
    assert not any(hit.lexical for hit in hits)


def test_an_empty_allow_list_returns_nothing(indexed) -> None:
    assert retrieval.search_chunks("crude", []) == []
    assert retrieval.rank_meetings("crude", []) == []


def test_a_literal_mention_is_found_and_flagged(indexed) -> None:
    (top, *_) = retrieval.search_chunks("Nomura", indexed)

    assert top.meeting_id == "rates-call"
    assert top.lexical is True


def test_a_paraphrase_is_found_semantically(indexed) -> None:
    (top, *_) = retrieval.search_chunks("bond yields", indexed)

    assert top.meeting_id == "rates-call"
    assert top.semantic > 0.5


def test_trigram_index_matches_inside_cjk_text(indexed) -> None:
    hits = retrieval.search_chunks("野村", indexed)

    assert hits[0].meeting_id == "lunch-chat"
    assert hits[0].lexical is True


def test_queries_too_short_for_trigrams_fall_back_to_substring(indexed) -> None:
    hits = retrieval.search_chunks("Bo", indexed)

    assert any(hit.meeting_id == "rates-call" and hit.lexical for hit in hits)


def test_fts_syntax_in_a_query_is_treated_as_text(indexed) -> None:
    # Quotes and operators must not reach FTS5 as query syntax.
    assert isinstance(retrieval.search_chunks('crude" OR "x', indexed), list)
    assert isinstance(retrieval.search_chunks("NEAR(a b)", indexed), list)


def test_one_meeting_cannot_take_more_than_its_share(db_path, fake_embedder) -> None:
    lines = [_caption(f"00:{i:02d}:00.000", "Ana: " + "oil " * 60) for i in range(10)]
    index_meeting("long", lines)
    index_meeting("short", [_caption("00:00:01.000", "Bo: crude oil again")])

    hits = retrieval.search_chunks("oil", ["long", "short"], k=8, per_meeting=2)

    assert sum(hit.meeting_id == "long" for hit in hits) == 2
    assert any(hit.meeting_id == "short" for hit in hits)


def test_rank_meetings_prefers_literal_mentions_and_names_the_source(indexed) -> None:
    texts = [
        retrieval.MeetingText(meeting_id="rates-call", title="Rates open"),
        retrieval.MeetingText(meeting_id="oil-call", title="Energy desk", keywords=["crude"]),
        retrieval.MeetingText(meeting_id="lunch-chat", title="Lunch"),
    ]

    ranked = retrieval.rank_meetings("crude", texts)

    assert ranked[0].meeting_id == "oil-call"
    assert ranked[0].lexical_source == "keywords"
    assert ranked[0].moment is not None
    assert ranked[0].moment.start == "00:00:01.000"


def test_rank_meetings_points_at_the_cue_that_mentions_the_query(indexed) -> None:
    texts = [retrieval.MeetingText(meeting_id=mid) for mid in indexed]

    (top, *_) = retrieval.rank_meetings("Nomura", texts)

    assert top.lexical_source == "transcript"
    assert top.moment is not None
    assert top.moment.start == "00:00:09.000"
    assert "Nomura" in top.moment.snippet


def test_rank_meetings_uses_the_overview_embedding_when_unindexed(db_path, fake_embedder) -> None:
    blob = priority.vector_to_blob(priority.embed_passages(["gold bullion"])[0])
    texts = [
        retrieval.MeetingText(meeting_id="metals", topic_embedding=blob),
        retrieval.MeetingText(meeting_id="other"),
    ]

    ranked = retrieval.rank_meetings("bullion", texts)

    assert ranked[0].meeting_id == "metals"
    assert ranked[0].semantic > 0.9
    assert ranked[0].moment is None


def test_chunk_at_returns_the_passage_containing_a_moment(indexed) -> None:
    passages = retrieval.chunk_at("rates-call", "00:00:09.000")

    assert passages
    assert "Nomura" in retrieval.merge_chunks(passages)


def test_chunk_at_ignores_a_moment_the_meeting_does_not_have(indexed) -> None:
    assert retrieval.chunk_at("rates-call", "02:00:00.000") == []


def test_reindexing_refreshes_the_cached_corpus(indexed) -> None:
    assert retrieval.search_chunks("Nomura", indexed)

    index_meeting("rates-call", [_caption("00:00:01.000", "Ana: Nothing to report.")])

    assert not any(hit.lexical for hit in retrieval.search_chunks("Nomura", indexed))


def test_topic_evidence_counts_mentions_and_points_at_the_first(indexed) -> None:
    evidence = retrieval.topic_evidence("JGB", indexed)

    assert evidence["rates-call"].mentions == 1
    assert evidence["rates-call"].moment is not None
    assert evidence["rates-call"].moment.start == "00:00:09.000"
    assert evidence["oil-call"].mentions == 0


def test_topic_evidence_splits_composite_topics(indexed) -> None:
    evidence = retrieval.topic_evidence("Energy & Crude", indexed)

    assert evidence["oil-call"].mentions == 1
    assert evidence["rates-call"].mentions == 0


def test_topic_evidence_respects_the_allow_list(indexed) -> None:
    assert set(retrieval.topic_evidence("crude", ["rates-call"])) == {"rates-call"}


def test_topic_evidence_omits_meetings_without_an_index(indexed) -> None:
    assert retrieval.topic_evidence("crude", ["never-indexed"]) == {}


def test_topic_evidence_measures_unnamed_discussion(indexed) -> None:
    evidence = retrieval.topic_evidence("bullion", indexed)
    rates = retrieval.topic_evidence("treasuries", indexed)

    # "treasuries" is a paraphrase of the rates call; nothing is about gold.
    assert rates["rates-call"].chunk_cosine > rates["lunch-chat"].chunk_cosine
    assert all(item.mentions == 0 for item in evidence.values())


def test_topic_evidence_is_recomputed_after_a_reindex(indexed) -> None:
    assert retrieval.topic_evidence("JGB", indexed)["rates-call"].mentions == 1

    index_meeting("rates-call", [_caption("00:00:01.000", "Ana: Nothing to report.")])

    assert retrieval.topic_evidence("JGB", indexed)["rates-call"].mentions == 0
