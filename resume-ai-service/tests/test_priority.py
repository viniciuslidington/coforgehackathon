# resume-ai-service/tests/test_priority.py
from __future__ import annotations

import numpy as np
import pytest

from app.services import priority


def test_embed_topic_is_deterministic():
    first = priority.embed_topic("budget overruns")
    second = priority.embed_topic("budget overruns")
    assert np.array_equal(first, second)


def test_embed_topic_uses_cache_for_normalized_text():
    priority._topic_cache.clear()
    priority.embed_topic("Budget Overruns")
    assert len(priority._topic_cache) == 1
    priority.embed_topic("  budget overruns  ")
    assert len(priority._topic_cache) == 1


def test_vector_blob_round_trip():
    vector = priority.embed_passage("quarterly budget review with finance team")
    blob = priority.vector_to_blob(vector)
    restored = priority.blob_to_vector(blob)
    assert np.allclose(vector, restored, atol=1e-6)


def test_cosine_similarity_of_identical_vectors_is_one():
    vector = priority.embed_passage("client escalation about missed deadline")
    assert priority.cosine_similarity(vector, vector) == pytest.approx(1.0, abs=1e-4)


def test_related_text_scores_higher_than_unrelated_text():
    topic_vectors = [priority.embed_topic("budget")]
    related = priority.embed_passage("The team reviewed the quarterly budget and cost overruns.")
    unrelated = priority.embed_passage("The team watched a documentary about deep sea fish.")
    related_score = priority.score_meeting(related, topic_vectors)
    unrelated_score = priority.score_meeting(unrelated, topic_vectors)
    assert related_score > unrelated_score


def test_score_meeting_takes_max_across_topics():
    topic_vectors = [priority.embed_topic("deep sea fish"), priority.embed_topic("budget")]
    text_vector = priority.embed_passage("The team reviewed the quarterly budget and cost overruns.")
    combined_score = priority.score_meeting(text_vector, topic_vectors)
    budget_only_score = priority.score_meeting(text_vector, [priority.embed_topic("budget")])
    assert combined_score == pytest.approx(budget_only_score, abs=1e-6)


def test_score_meeting_with_no_topics_is_zero():
    text_vector = priority.embed_passage("anything")
    assert priority.score_meeting(text_vector, []) == 0.0


def test_tier_thresholds():
    assert priority.tier_for_score(55.0) == "urgent"
    assert priority.tier_for_score(54.999) == "high"
    assert priority.tier_for_score(30.0) == "high"
    assert priority.tier_for_score(29.999) == "normal"
