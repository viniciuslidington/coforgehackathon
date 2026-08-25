# resume-ai-service/app/services/priority.py
"""Deterministic, non-generative topic-relevance scoring for meetings.

The only module in this service that knows a local embedding model exists.
Everything downstream (database.py, meeting_service.py) works with plain
float vectors and never imports fastembed directly.
"""
from __future__ import annotations

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
