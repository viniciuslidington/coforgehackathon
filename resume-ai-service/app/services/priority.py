# resume-ai-service/app/services/priority.py
"""Deterministic, non-generative topic-relevance scoring for meetings.

The only module in this service that knows a local embedding model exists.
Everything downstream (database.py, meeting_service.py) works with plain
float vectors and never imports fastembed directly.
"""
from __future__ import annotations

import re
import warnings
from typing import Literal

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# This model's cosine similarities for meeting-vs-topic text in this domain
# sit roughly in [0, 0.7], not the full [-1, 1] range, so thresholds are
# calibrated against that observed range rather than against a theoretical
# midpoint.
URGENT_THRESHOLD = 55.0
HIGH_THRESHOLD = 30.0

# Transcript evidence (see `combine`). A literal mention of a topic the user
# asked for is strong evidence on its own, so one mention lifts a meeting to
# at least High, and each further line that mentions it adds a step.
# Urgent from mentions alone takes five lines that name it — the topic was
# discussed, not just named. Calibrated on this corpus, like the thresholds.
MENTION_BASE = HIGH_THRESHOLD
MENTION_STEP = 6.0
MENTION_MAX_STEPS = 4
MENTION_BONUS = 5.0
# A meeting's transcript similarity is the mean of its best few passages: the
# single best one is noise, since nearly every finance chat has one passage
# loosely similar to a short topic.
TOP_CHUNKS = 3

_model: TextEmbedding | None = None
_topic_cache: dict[str, np.ndarray] = {}


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        with warnings.catch_warnings():
            # fastembed emits a UserWarning about mean-pooling vs. CLS pooling
            # when loading this model. The warning text itself names concrete
            # mitigations (pin fastembed==0.5.1, or add_custom_model), but
            # since we can't control the installed fastembed version here,
            # narrowly suppress just this message at the model-load call site
            # rather than masking UserWarnings process-wide.
            warnings.filterwarnings(
                "ignore",
                message=r".*mean pooling.*",
                category=UserWarning,
            )
            _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_passage(text: str) -> np.ndarray:
    """Embed meeting-side text (title + simple_summary + keywords).

    Note: MODEL_NAME is a plain sentence-transformers model, not an E5
    model, so it does not use "query:"/"passage:" instruction prefixes —
    text is embedded as-is.
    """
    (vector,) = _get_model().embed([text])
    return vector


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    """Embed many passages in one batched model call (transcript chunks)."""
    if not texts:
        return []
    return list(_get_model().embed(texts))


def embed_topic(topic: str) -> np.ndarray:
    """Embed a user-supplied topic, cached by normalized text."""
    key = topic.strip().lower()
    if key not in _topic_cache:
        (vector,) = _get_model().embed([topic])
        _topic_cache[key] = vector
    return _topic_cache[key]


def vector_to_blob(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def score_meeting(meeting_vector: np.ndarray, topic_vectors: list[np.ndarray]) -> float:
    """0-100 relevance score: the MAX cosine similarity across all topics."""
    if not topic_vectors:
        return 0.0
    best_cosine = max(cosine_similarity(meeting_vector, topic_vector) for topic_vector in topic_vectors)
    return max(0.0, best_cosine) * 100.0


def tier_for_score(score: float) -> Literal["urgent", "high", "normal"]:
    if score >= URGENT_THRESHOLD:
        return "urgent"
    if score >= HIGH_THRESHOLD:
        return "high"
    return "normal"


# Splits composite topics such as "Fed & Rates" or "FX, Rates and Credit".
TOPIC_SEPARATOR = re.compile(r"\s*(?:&|,|/|\band\b)\s*", re.IGNORECASE)


def topic_terms(topic: str) -> list[str]:
    """The phrases whose literal mention counts as mentioning a topic.

    The whole topic, plus each part of a composite one. Parts shorter than two
    characters are dropped; a topic that is itself a symbol ("M&A") is kept
    whole.
    """
    whole = topic.strip()
    if not whole:
        return []
    parts = [part for part in TOPIC_SEPARATOR.split(whole) if len(part) >= 2]
    return list(dict.fromkeys([whole, *parts]))


def mention_pattern(term: str) -> re.Pattern[str]:
    """A whole-word, case-insensitive match that also accepts a plural or
    possessive ("JGB" matches "JGBs", "Fed's"), so "oil" never matches "toil".

    A term with no letters from a space-separated script (e.g. CJK) has no
    word boundaries to anchor on, so it matches as a substring instead.
    """
    escaped = re.escape(term)
    if not re.search(r"[A-Za-z0-9\u00C0-\u024F\u0400-\u04FF]", term):
        return re.compile(escaped)
    return re.compile(rf"(?<!\w){escaped}(?:s|es|'s)?(?!\w)", re.IGNORECASE)


def combine(summary_cosine: float, chunk_cosine: float | None, mentions: int) -> float:
    """0-100 relevance of one meeting to one topic.

    `summary_cosine` compares the topic with the stored overview;
    `chunk_cosine` is the mean of the best TOP_CHUNKS transcript passages, or
    None when the meeting has no transcript index; `mentions` counts
    transcript lines that literally mention the topic.
    """
    semantic = max(0.0, summary_cosine, chunk_cosine or 0.0) * 100.0
    if mentions <= 0:
        return semantic
    floor = MENTION_BASE + MENTION_STEP * min(mentions - 1, MENTION_MAX_STEPS)
    return min(100.0, max(semantic, floor) + MENTION_BONUS)

