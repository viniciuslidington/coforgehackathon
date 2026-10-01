from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.services import database


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point database.py at a fresh, empty SQLite file for this test only."""
    path = tmp_path / "test_meeting_insights.db"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    return path


# Words that mean the same thing share a dimension, so the fake model
# "understands" paraphrase the way the real one does — deterministically.
CONCEPTS = (
    ("rates", "yields", "bonds", "treasuries", "duration", "jgb", "jgbs"),
    ("oil", "crude", "brent", "barrel", "opec"),
    ("gold", "bullion"),
    ("lunch", "sandwich", "pizza"),
    ("inflation", "cpi", "prices"),
)


class FakeEmbeddingModel:
    def embed(self, texts):
        for text in texts:
            words = [word.strip(".,!?:;'\"").casefold() for word in text.split()]
            vector = np.full(len(CONCEPTS) + 1, 0.01, dtype=np.float32)
            for index, concept in enumerate(CONCEPTS):
                vector[index] += sum(word in concept for word in words)
            yield vector


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> FakeEmbeddingModel:
    """Swap the local embedding model for a tiny deterministic one."""
    from app.services import priority, retrieval

    model = FakeEmbeddingModel()
    monkeypatch.setattr(priority, "_get_model", lambda: model)
    monkeypatch.setattr(priority, "_topic_cache", {})
    monkeypatch.setattr(retrieval, "_cache", None)
    return model
