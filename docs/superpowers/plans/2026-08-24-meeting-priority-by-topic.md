# Meeting Priority by Topic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user define one or more topics of interest and see each meeting's relevance to those topics as a deterministic, non-generative `priority_score`/`priority_tier`, computed via local multilingual embeddings.

**Architecture:** A new backend module (`app/services/priority.py`) is the single seam that knows a local embedding model exists. It computes and caches vectors; `database.py` stores a per-meeting vector (computed once at sync time) and does plain numeric cosine-similarity ranking without ever loading the model itself. `meeting_service.py` orchestrates: when `topics` are passed, it scores every meeting matching the date filter, sorts by score, then paginates in Python (SQL `ORDER BY` cannot express a request-time vector comparison). The frontend gets a `topics` input and a working sort selector, and inherits the `Priority`/`tier`/`score` vocabulary from the legacy `entities/call` (types + `PriorityBadge` only — the trading-specific mocks and `CallFlag`/`mentions` are dropped, not ported).

**Tech Stack:** FastAPI + SQLite (backend, `resume-ai-service/`), `fastembed` (ONNX-based local multilingual embeddings, no GPU/torch), `pytest` + `httpx` (new backend test infra — none existed), Next.js App Router + TypeScript (frontend, no test runner exists — frontend tasks use manual browser verification, matching this repo's existing MVP convention documented in `docs/superpowers/specs/2026-08-23-meeting-features-design.md`).

**Spec:** [docs/superpowers/specs/2026-08-24-meeting-priority-by-topic.md](../specs/2026-08-24-meeting-priority-by-topic.md) — also see [CONTEXT.md](../../../CONTEXT.md) for vocabulary and [ADR-0001](../../adr/0001-deterministic-local-embeddings-for-priority.md) for why embeddings-over-LLM was chosen.

## Global Constraints

- Deterministic, no generative AI: the embedding model is a local ONNX model run offline — never call an LLM or an external API to score priority.
- Multi-topic combination is **max** across topics, never average or sum (a meeting only needs to strongly match one topic to be prioritized).
- Score is `0`–`100`, tiers are `urgent >= 70`, `high >= 40`, else `normal` — implemented as named constants in `priority.py`, expected to be recalibrated later, not hardcoded inline at call sites.
- No topic active → `priority_score`/`priority_tier` are `None`/absent, never a fake "normal" default.
- Topics are never persisted server-side (no user/auth model exists) — passed per-request as a query param, optionally cached client-side in `localStorage`.
- Sorting by priority must be correct across pagination: compute scores for the whole date-filtered dataset, sort, then slice — never sort only the current page.
- `entities/call`'s `CallFlag` type and `SortKey = 'mentions'` are legacy and must not be ported to the meeting domain.

---

## File Structure

**Backend (`resume-ai-service/`):**
- `app/services/priority.py` (new) — embedding model singleton, `embed_passage`/`embed_topic` (with topic cache), `vector_to_blob`/`blob_to_vector`, `cosine_similarity`, `score_meeting`, `tier_for_score`, threshold constants. The only file that imports `fastembed`.
- `app/services/database.py` (modify) — schema gains `topic_embedding BLOB`; `upsert_summary` accepts and stores an optional precomputed blob; new `list_summaries_for_priority` returns the full date-filtered set (no pagination) including the raw blob, for `meeting_service` to score.
- `app/services/meeting_service.py` (modify) — `get_stored_summaries` gains `topics: list[str] | None`; when present, scores/sorts/paginates in Python via `priority`; new small helper `compute_topic_embedding_blob` used by the sync router.
- `app/schemas/meetings.py` (modify) — `StoredMeetingSummary` gains optional `priority_score`/`priority_tier`.
- `app/routers/meeting_summaries.py` (modify) — `_sync_from_r2` computes the embedding blob via `meeting_service.compute_topic_embedding_blob` and passes it to `upsert_summary`; `GET /meeting-summaries` accepts an optional `topics` query param.
- `tests/conftest.py` (new) — isolates `database.DATABASE_PATH` per test via a temp file.
- `tests/test_priority.py`, `tests/test_database_priority.py`, `tests/test_meeting_service_priority.py`, `tests/test_meeting_summaries_router.py` (new).
- `pyproject.toml` (modify) — add `fastembed` runtime dependency, `pytest`/`httpx` dev dependency group.

**Frontend (`src/`):**
- `entities/meeting/model/types.ts` (modify) — add `Priority`, `SortKey` types; add optional `priority_score`/`priority_tier` to `MeetingSummary`.
- `entities/meeting/lib/helpers.ts` (new) — `tierColor`, `tierLabel`, `sortMeetings`, moved/adapted from `entities/call/lib/helpers.ts`.
- `entities/meeting/ui/PriorityBadge.tsx` + `.module.css` (new) — moved from `entities/call/ui/`.
- `entities/meeting/ui/CallRow.tsx` + `.module.css` (moved from `entities/call/ui/`) — gains conditional `PriorityBadge` rendering.
- `entities/call/` (delete entirely, once nothing imports from it) — `CallFlag`, `Call`, mock `CALLS` data, `FlagBadge`, `generateAnswer` are legacy and unused going forward.
- `features/call-filters/model/useCallFilters.ts` (modify) — repoint its `SortKey` import to `entities/meeting`, drop the unused `'mentions'` default concern (already only ever `'priority'`/`'time'` conceptually — confirm no other key was relied upon).
- `shared/api/meetings.ts` (modify) — `getMeetingSummaries` gains an optional `topics: string[]` param, serialized as repeated `topics` query params.
- `widgets/call-history/ui/CallHistory.tsx` (modify) — imports `CallRow` from `entities/meeting`; adds a topics text input (session state, mirrored to `localStorage`) and wires `useCallFilters`' sort selector to actually reorder `data.items` via `sortMeetings`.

---

## Task 1: Backend test infrastructure

**Files:**
- Create: `resume-ai-service/tests/__init__.py` (empty)
- Create: `resume-ai-service/tests/conftest.py`
- Modify: `resume-ai-service/pyproject.toml`

**Interfaces:**
- Produces: a `db_path` fixture (function-scoped) that monkeypatches `app.services.database.DATABASE_PATH` to a fresh temp file, so every test starts with an empty `meeting_summaries` table.

No tests exist in this project yet — this task only sets up the ability to write and run them; there is no "failing test" step here.

- [ ] **Step 1: Add dev dependencies**

```bash
cd resume-ai-service
env -u VIRTUAL_ENV uv add fastembed
env -u VIRTUAL_ENV uv add --dev pytest httpx
```

- [ ] **Step 2: Create the conftest fixture**

```python
# resume-ai-service/tests/conftest.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import database


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point database.py at a fresh, empty SQLite file for this test only."""
    path = tmp_path / "test_meeting_insights.db"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    return path
```

- [ ] **Step 3: Create the empty test package marker**

```python
# resume-ai-service/tests/__init__.py
```

- [ ] **Step 4: Verify pytest collects zero tests without error**

Run: `cd resume-ai-service && .venv/bin/pytest tests/ -v`
Expected: `no tests ran` (exit code 5) or `0 passed` — not a collection error.

- [ ] **Step 5: Commit**

```bash
git add resume-ai-service/tests/__init__.py resume-ai-service/tests/conftest.py resume-ai-service/pyproject.toml resume-ai-service/uv.lock
git commit -m "test: add pytest infra with isolated database fixture"
```

---

## Task 2: `priority.py` — deterministic embedding, scoring, and tiering

**Files:**
- Create: `resume-ai-service/app/services/priority.py`
- Test: `resume-ai-service/tests/test_priority.py`

**Interfaces:**
- Produces:
  - `embed_passage(text: str) -> numpy.ndarray` — embeds meeting-side text (title+summary+keywords), no cache.
  - `embed_topic(topic: str) -> numpy.ndarray` — embeds a user topic, cached by normalized (`strip().lower()`) text.
  - `vector_to_blob(vector: numpy.ndarray) -> bytes` / `blob_to_vector(blob: bytes) -> numpy.ndarray` — round-trippable `float32` serialization for SQLite `BLOB` storage.
  - `cosine_similarity(a: numpy.ndarray, b: numpy.ndarray) -> float`
  - `score_meeting(meeting_vector: numpy.ndarray, topic_vectors: list[numpy.ndarray]) -> float` — `0`–`100`, max across topics.
  - `tier_for_score(score: float) -> Literal["urgent", "high", "normal"]`
  - `URGENT_THRESHOLD = 70.0`, `HIGH_THRESHOLD = 40.0` (module-level constants).

- [ ] **Step 1: Write the failing tests**

```python
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
    assert priority.tier_for_score(70.0) == "urgent"
    assert priority.tier_for_score(69.999) == "high"
    assert priority.tier_for_score(40.0) == "high"
    assert priority.tier_for_score(39.999) == "normal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_priority.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.priority'`

- [ ] **Step 3: Write the implementation**

```python
# resume-ai-service/app/services/priority.py
"""Deterministic, non-generative topic-relevance scoring for meetings.

The only module in this service that knows a local embedding model exists.
Everything downstream (database.py, meeting_service.py) works with plain
float vectors and never imports fastembed directly.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "intfloat/multilingual-e5-small"

URGENT_THRESHOLD = 70.0
HIGH_THRESHOLD = 40.0

_model: TextEmbedding | None = None
_topic_cache: dict[str, np.ndarray] = {}


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_passage(text: str) -> np.ndarray:
    """Embed meeting-side text (title + simple_summary + keywords)."""
    (vector,) = _get_model().embed([f"passage: {text}"])
    return vector


def embed_topic(topic: str) -> np.ndarray:
    """Embed a user-supplied topic, cached by normalized text."""
    key = topic.strip().lower()
    if key not in _topic_cache:
        (vector,) = _get_model().embed([f"query: {topic}"])
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
    clamped = max(-1.0, min(1.0, best_cosine))
    return (clamped + 1.0) / 2.0 * 100.0


def tier_for_score(score: float) -> Literal["urgent", "high", "normal"]:
    if score >= URGENT_THRESHOLD:
        return "urgent"
    if score >= HIGH_THRESHOLD:
        return "high"
    return "normal"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_priority.py -v`
Expected: PASS (first run downloads the ONNX model to a local cache — allow extra time; if `TextEmbedding(MODEL_NAME)` raises on load, see the fallback note below)

**Fallback if the model fails to load:** `intfloat/multilingual-e5-small` must appear in `TextEmbedding.list_supported_models()`. If it does not, or loading fails, print `[m["model"] for m in TextEmbedding.list_supported_models()]`, pick another multilingual entry from that list (avoid `multilingual-e5-large` and `jina-embeddings-v3`, which have a known onnxruntime 1.24.1 loading bug), and update `MODEL_NAME` accordingly before continuing.

- [ ] **Step 5: Commit**

```bash
git add resume-ai-service/app/services/priority.py resume-ai-service/tests/test_priority.py
git commit -m "feat: add deterministic local-embedding priority scoring"
```

---

## Task 3: Persist and query meeting embeddings in `database.py`

**Files:**
- Modify: `resume-ai-service/app/services/database.py`
- Test: `resume-ai-service/tests/test_database_priority.py`

**Interfaces:**
- Consumes: nothing from `priority.py` — this module only stores/reads bytes, never computes embeddings.
- Produces:
  - `upsert_summary(..., topic_embedding: bytes | None = None)` — existing signature plus one new optional keyword-only-by-convention parameter (all others already keyword-only via existing call sites).
  - `list_summaries_for_priority(*, date_from: str | None = None) -> list[dict[str, object]]` — every row matching the date filter (no `LIMIT`/`OFFSET`), each dict including `topic_embedding: bytes | None`.

- [ ] **Step 1: Write the failing tests**

```python
# resume-ai-service/tests/test_database_priority.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_database_priority.py -v`
Expected: FAIL — `upsert_summary() got an unexpected keyword argument 'topic_embedding'` and `AttributeError: module 'app.services.database' has no attribute 'list_summaries_for_priority'`

- [ ] **Step 3: Implement the schema and function changes**

Modify `SCHEMA` and the migration block in `connection()`:

```python
SCHEMA = """
    CREATE TABLE IF NOT EXISTS meeting_summaries (
        meeting_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        meeting_date TEXT NOT NULL,
        participants TEXT NOT NULL,
        simple_summary TEXT NOT NULL,
        keywords TEXT NOT NULL DEFAULT '',
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        refreshed_at TEXT NOT NULL,
        topic_embedding BLOB
    )
"""
```

```python
        if "duration_seconds" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN duration_seconds INTEGER NOT NULL DEFAULT 0")
        if "topic_embedding" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN topic_embedding BLOB")
```

Modify `upsert_summary`:

```python
def upsert_summary(*, meeting_id: str, title: str, meeting_date: str, participants: list[str], simple_summary: str, keywords: list[str], duration_seconds: int, topic_embedding: bytes | None = None) -> None:
    with connection() as conn:
        conn.execute("""
            INSERT INTO meeting_summaries (meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                title=excluded.title,
                meeting_date=excluded.meeting_date,
                participants=excluded.participants,
                simple_summary=excluded.simple_summary,
                keywords=excluded.keywords,
                duration_seconds=excluded.duration_seconds,
                refreshed_at=excluded.refreshed_at,
                topic_embedding=excluded.topic_embedding
        """, (meeting_id, title, meeting_date, ", ".join(participants), simple_summary, ", ".join(keywords), duration_seconds, datetime.now(UTC).isoformat(), topic_embedding))
```

Add the new query function (after `list_summaries`):

```python
def list_summaries_for_priority(*, date_from: str | None = None) -> list[dict[str, object]]:
    """Every summary matching the date filter, unpaginated, with its raw
    topic_embedding blob — used to score+sort the full dataset before the
    caller paginates in Python."""
    with connection() as conn:
        where = "WHERE meeting_date >= ?" if date_from else ""
        parameters: tuple[object, ...] = (date_from,) if date_from else ()
        rows = conn.execute(f"""
            SELECT meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding
            FROM meeting_summaries {where} ORDER BY meeting_date DESC, refreshed_at DESC
        """, parameters).fetchall()
    return [dict(row) for row in rows]
```

Note: `list_summaries`'s existing `SELECT` (line 76) does not list `topic_embedding`, but `dict(row)` there is unaffected since it only selects named columns — no change needed there, but the test above expects `rows[0]["topic_embedding"]` from `list_summaries`, so add `topic_embedding` to that `SELECT` list too:

```python
        rows = conn.execute("""
            SELECT meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding
            FROM meeting_summaries {where} ORDER BY meeting_date DESC, refreshed_at DESC LIMIT ? OFFSET ?
        """.format(where=where), (*parameters, limit, offset)).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_database_priority.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd resume-ai-service && .venv/bin/pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add resume-ai-service/app/services/database.py resume-ai-service/tests/test_database_priority.py
git commit -m "feat: persist and query per-meeting topic embeddings"
```

---

## Task 4: Topic-scored, correctly-paginated `get_stored_summaries`

**Files:**
- Modify: `resume-ai-service/app/services/meeting_service.py`
- Modify: `resume-ai-service/app/schemas/meetings.py`
- Test: `resume-ai-service/tests/test_meeting_service_priority.py`

**Interfaces:**
- Consumes: `priority.embed_topic`, `priority.blob_to_vector`, `priority.score_meeting`, `priority.tier_for_score` (Task 2); `database.list_summaries_for_priority`, `database.upsert_summary`'s `topic_embedding` param (Task 3).
- Produces:
  - `StoredMeetingSummary.priority_score: float | None = None`, `StoredMeetingSummary.priority_tier: Literal["urgent","high","normal"] | None = None`.
  - `get_stored_summaries(page, page_size, period="all", topics: list[str] | None = None) -> SummaryPage` — existing signature plus one new optional parameter.
  - `compute_topic_embedding_blob(text: str) -> bytes` — used by the router in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# resume-ai-service/tests/test_meeting_service_priority.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_meeting_service_priority.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_topic_embedding_blob'` and `TypeError: get_stored_summaries() got an unexpected keyword argument 'topics'`

- [ ] **Step 3: Add the schema fields**

```python
# resume-ai-service/app/schemas/meetings.py — add to StoredMeetingSummary
from typing import Literal

class StoredMeetingSummary(BaseModel):
    meeting_id: str
    title: str
    meeting_date: str
    participants: list[str]
    simple_summary: str
    keywords: list[str]
    duration_seconds: int
    refreshed_at: str
    priority_score: float | None = None
    priority_tier: Literal["urgent", "high", "normal"] | None = None
```

- [ ] **Step 4: Implement `compute_topic_embedding_blob` and the scored branch of `get_stored_summaries`**

```python
# resume-ai-service/app/services/meeting_service.py
# add to imports:
from app.services import priority
from app.services.database import list_summaries, list_summaries_for_priority

# new function, near execute_overview:
def compute_topic_embedding_blob(text: str) -> bytes:
    return priority.vector_to_blob(priority.embed_passage(text))

# replace get_stored_summaries:
def _row_to_summary(row: dict[str, object], *, priority_score: float | None = None, priority_tier: str | None = None) -> StoredMeetingSummary:
    data = dict(row)
    data.pop("topic_embedding", None)
    data["participants"] = [name.strip() for name in data["participants"].split(",") if name.strip()]
    data["keywords"] = [keyword.strip() for keyword in data["keywords"].split(",") if keyword.strip()]
    return StoredMeetingSummary(**data, priority_score=priority_score, priority_tier=priority_tier)

def get_stored_summaries(page: int, page_size: int, period: Literal["day", "week", "30d", "all"] = "all", topics: list[str] | None = None) -> SummaryPage:
    date_from = {
        "day": date.today().isoformat(),
        "week": (date.today() - timedelta(days=6)).isoformat(),
        "30d": (date.today() - timedelta(days=29)).isoformat(),
        "all": None,
    }[period]

    if not topics:
        rows, total = list_summaries(offset=(page - 1) * page_size, limit=page_size, date_from=date_from)
        items = [_row_to_summary(row) for row in rows]
        return SummaryPage(items=items, total=total, page=page, page_size=page_size)

    topic_vectors = [priority.embed_topic(topic) for topic in topics]
    all_rows = list_summaries_for_priority(date_from=date_from)
    scored: list[tuple[float | None, str | None, dict[str, object]]] = []
    for row in all_rows:
        blob = row.get("topic_embedding")
        if blob:
            meeting_vector = priority.blob_to_vector(blob)
            score = priority.score_meeting(meeting_vector, topic_vectors)
            tier = priority.tier_for_score(score)
        else:
            score, tier = None, None
        scored.append((score, tier, row))
    scored.sort(key=lambda entry: entry[0] if entry[0] is not None else -1.0, reverse=True)

    total = len(scored)
    start = (page - 1) * page_size
    page_slice = scored[start:start + page_size]
    items = [_row_to_summary(row, priority_score=score, priority_tier=tier) for score, tier, row in page_slice]
    return SummaryPage(items=items, total=total, page=page, page_size=page_size)
```

Remove the old inline loop body of `get_stored_summaries` (the `rows, total = list_summaries(...)` + manual `items = []` loop) — it is fully replaced by the `if not topics:` branch above, which reuses the new `_row_to_summary` helper.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_meeting_service_priority.py -v`
Expected: PASS

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `cd resume-ai-service && .venv/bin/pytest tests/ -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add resume-ai-service/app/services/meeting_service.py resume-ai-service/app/schemas/meetings.py resume-ai-service/tests/test_meeting_service_priority.py
git commit -m "feat: score and rank meetings by topic relevance before pagination"
```

---

## Task 5: Wire embedding computation into sync, and `topics` into the router

**Files:**
- Modify: `resume-ai-service/app/routers/meeting_summaries.py`
- Test: `resume-ai-service/tests/test_meeting_summaries_router.py`

**Interfaces:**
- Consumes: `meeting_service.compute_topic_embedding_blob` (Task 4), `meeting_service.get_stored_summaries(..., topics=...)` (Task 4), `database.upsert_summary(..., topic_embedding=...)` (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# resume-ai-service/tests/test_meeting_summaries_router.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_meeting_summaries_router.py -v`
Expected: FAIL — first test fails because `topic_embedding` is `None` (sync doesn't compute it yet); third test fails because the `topics` query param has no effect yet

- [ ] **Step 3: Wire it in**

In `app/routers/meeting_summaries.py`, add to imports:

```python
from app.services.meeting_service import caption_to_segment, compute_topic_embedding_blob, execute_chat, execute_overview, get_stored_summaries
```

In `_sync_from_r2`, after computing `title, simple_summary, keywords` and before `upsert_summary(...)`:

```python
        topic_embedding = compute_topic_embedding_blob(f"{title} {simple_summary} {' '.join(keywords)}")
        upsert_summary(meeting_id=meeting_id, title=title, meeting_date=date.today().isoformat(), participants=participants, simple_summary=simple_summary, keywords=keywords, duration_seconds=duration, topic_embedding=topic_embedding)
```

(replacing the existing `upsert_summary(...)` call, which lacked `topic_embedding`).

Update `get_meeting_summaries`:

```python
@router.get("/meeting-summaries", response_model=SummaryPage)
def get_meeting_summaries(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100), period: Literal["day", "week", "30d", "all"] = "all", topics: list[str] | None = Query(None)) -> SummaryPage:
    """Return persisted meeting overviews, filtered by meeting date and paginated.

    When `topics` is given, each item also carries `priority_score`/`priority_tier`
    and the page is ordered by relevance to those topics (computed deterministically,
    no LLM) instead of by date.
    """
    return get_stored_summaries(page, page_size, period, topics)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd resume-ai-service && .venv/bin/pytest tests/test_meeting_summaries_router.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd resume-ai-service && .venv/bin/pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add resume-ai-service/app/routers/meeting_summaries.py resume-ai-service/tests/test_meeting_summaries_router.py
git commit -m "feat: compute topic embeddings on sync and expose topics filter on the list endpoint"
```

---

## Task 6: Migrate `Priority`/`tier`/`score` vocabulary into `entities/meeting`

**Files:**
- Modify: `src/entities/meeting/model/types.ts`
- Create: `src/entities/meeting/lib/helpers.ts`
- Create: `src/entities/meeting/ui/PriorityBadge.tsx`
- Create: `src/entities/meeting/ui/PriorityBadge.module.css` (copy verbatim from `src/entities/call/ui/PriorityBadge.module.css`)

No automated frontend test runner exists in this repo (confirmed: no `vitest`/`jest` config, no `*.test.*` files) — this project's own precedent (`docs/superpowers/specs/2026-08-23-meeting-features-design.md`, "Testes" section) is manual verification via the running UI. This task and Tasks 7-8 are verified by `npm run dev` + browser check at the end of Task 8, and by TypeScript compiling cleanly after each step.

- [ ] **Step 1: Extend the meeting types**

Add to `src/entities/meeting/model/types.ts` (after `MeetingPeriod`):

```typescript
export type Priority = 'urgent' | 'high' | 'normal';

export type SortKey = 'priority' | 'time';
```

And add two optional fields to `MeetingSummary`:

```typescript
export interface MeetingSummary {
  meeting_id: string;
  title: string;
  meeting_date: string;
  participants: string[];
  simple_summary: string;
  keywords: string[];
  duration_seconds: number;
  refreshed_at: string;
  priority_score?: number | null;
  priority_tier?: Priority | null;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/viniciuslidington/Projects/coforgehackathon && npx tsc --noEmit`
Expected: no new errors (existing `entities/call` files still reference the old `Priority`/`SortKey` locally, unaffected so far)

- [ ] **Step 3: Create the meeting-domain helpers**

```typescript
// src/entities/meeting/lib/helpers.ts
import { colors } from '@/shared/config/tokens';
import type { MeetingSummary, Priority, SortKey } from '../model/types';

export function tierColor(tier: Priority): string {
  switch (tier) {
    case 'urgent': return colors.urgent;
    case 'high':   return colors.high;
    default:       return colors.textDimmest;
  }
}

export function tierLabel(tier: Priority): string {
  switch (tier) {
    case 'urgent': return 'Urgent';
    case 'high':   return 'High';
    default:       return 'Routine';
  }
}

export function sortMeetings(meetings: MeetingSummary[], key: SortKey): MeetingSummary[] {
  const sorted = [...meetings];
  if (key === 'priority') {
    return sorted.sort((a, b) => (b.priority_score ?? -1) - (a.priority_score ?? -1));
  }
  return sorted.sort((a, b) => (a.meeting_date < b.meeting_date ? 1 : -1));
}
```

- [ ] **Step 4: Create `PriorityBadge`**

```bash
cp src/entities/call/ui/PriorityBadge.module.css src/entities/meeting/ui/PriorityBadge.module.css
```

```typescript
// src/entities/meeting/ui/PriorityBadge.tsx
'use client';

import type { Priority } from '../model/types';
import { tierColor, tierLabel } from '../lib/helpers';
import styles from './PriorityBadge.module.css';

interface PriorityBadgeProps {
  tier: Priority;
  score: number;
}

export function PriorityBadge({ tier, score }: PriorityBadgeProps) {
  const color = tierColor(tier);
  const label = tierLabel(tier);
  const isRoutine = tier === 'normal';

  return (
    <div className={styles.wrapper}>
      <div className={styles.labelRow}>
        <div className={styles.dot} style={{ background: color }} />
        <span
          className={styles.label}
          style={{ color: isRoutine ? 'var(--text-dim)' : color, fontWeight: 500 }}
        >
          {label}
        </span>
      </div>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${score}%`, background: color }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd /Users/viniciuslidington/Projects/coforgehackathon && npx tsc --noEmit`
Expected: no new errors

- [ ] **Step 6: Commit**

```bash
git add src/entities/meeting/model/types.ts src/entities/meeting/lib/helpers.ts src/entities/meeting/ui/PriorityBadge.tsx src/entities/meeting/ui/PriorityBadge.module.css
git commit -m "feat: add priority vocabulary and badge to entities/meeting"
```

---

## Task 7: Move `CallRow` into `entities/meeting`, render the badge

**Files:**
- Create: `src/entities/meeting/ui/CallRow.tsx` (moved from `src/entities/call/ui/CallRow.tsx`)
- Create: `src/entities/meeting/ui/CallRow.module.css` (moved from `src/entities/call/ui/CallRow.module.css`)
- Delete: `src/entities/call/ui/CallRow.tsx`, `src/entities/call/ui/CallRow.module.css`
- Modify: `src/widgets/call-history/ui/CallHistory.tsx`

**Interfaces:**
- Consumes: `PriorityBadge` from `src/entities/meeting/ui/PriorityBadge` (Task 6).

- [ ] **Step 1: Move the files**

```bash
git mv src/entities/call/ui/CallRow.tsx src/entities/meeting/ui/CallRow.tsx
git mv src/entities/call/ui/CallRow.module.css src/entities/meeting/ui/CallRow.module.css
```

- [ ] **Step 2: Update the import inside the moved file and render the badge**

In `src/entities/meeting/ui/CallRow.tsx`, change the CSS import (path is now relative to the new location, `./CallRow.module.css` — unchanged) and change `import type { MeetingSummary } from '@/entities/meeting/model/types';` to a relative import `import type { MeetingSummary } from '../model/types';` for consistency with the rest of `entities/meeting`. Add the badge:

```typescript
import { PriorityBadge } from './PriorityBadge';
```

Add a new column, after the `keywords` div and before the closing `</article>`:

```typescript
      {meeting.priority_tier && meeting.priority_score != null && (
        <div className={styles.priority}>
          <PriorityBadge tier={meeting.priority_tier} score={meeting.priority_score} />
        </div>
      )}
```

- [ ] **Step 3: Add the `.priority` class to the moved CSS module**

Append to `src/entities/meeting/ui/CallRow.module.css`:

```css
.priority {
  min-width: 96px;
}
```

- [ ] **Step 4: Update `CallHistory.tsx`'s import**

In `src/widgets/call-history/ui/CallHistory.tsx`, change:

```typescript
import { CallRow } from '@/entities/call/ui/CallRow';
```

to:

```typescript
import { CallRow } from '@/entities/meeting/ui/CallRow';
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd /Users/viniciuslidington/Projects/coforgehackathon && npx tsc --noEmit`
Expected: no new errors

- [ ] **Step 6: Commit**

```bash
git add -A src/entities/meeting/ui/CallRow.tsx src/entities/meeting/ui/CallRow.module.css src/entities/call/ui/CallRow.tsx src/entities/call/ui/CallRow.module.css src/widgets/call-history/ui/CallHistory.tsx
git commit -m "refactor: move CallRow into entities/meeting, render priority badge"
```

---

## Task 8: Wire a topics input and a working sort selector into `CallHistory`

**Files:**
- Modify: `src/shared/api/meetings.ts`
- Modify: `src/features/call-filters/model/useCallFilters.ts`
- Modify: `src/widgets/call-history/ui/CallHistory.tsx`
- Modify: `src/widgets/call-history/ui/CallHistory.module.css`

**Interfaces:**
- Consumes: `sortMeetings` from `entities/meeting/lib/helpers` (Task 6); `SortKey` from `entities/meeting/model/types` (Task 6).

Note: `useCallFilters` exists but nothing currently imports/renders it — `CallHistory` has no sort UI and no topics input today. This task adds both, since "sort by priority" and "define topics" are the feature's actual user-facing entry points.

- [ ] **Step 1: Add `topics` to the API client**

```typescript
// src/shared/api/meetings.ts — replace getMeetingSummaries
export async function getMeetingSummaries(
  period: MeetingPeriod,
  page: number,
  pageSize: number,
  topics: string[] = [],
  signal?: AbortSignal,
): Promise<MeetingSummaryPage> {
  const params = new URLSearchParams({ period, page: String(page), page_size: String(pageSize) });
  for (const topic of topics) {
    if (topic.trim()) params.append('topics', topic.trim());
  }
  const response = await fetch(`${API_BASE_URL}/meeting-summaries?${params}`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load meetings (${response.status}).`);
  }
  return response.json() as Promise<MeetingSummaryPage>;
}
```

- [ ] **Step 2: Repoint `useCallFilters` at the meeting domain**

```typescript
// src/features/call-filters/model/useCallFilters.ts
import type { SortKey } from '@/entities/meeting/model/types';
```

(only the import line changes — `DEFAULT_SORT: SortKey = 'priority'` remains valid since `'priority'` is still a member of the new `SortKey`.)

- [ ] **Step 3: Wire topics + sort into `CallHistory`**

In `src/widgets/call-history/ui/CallHistory.tsx`, update imports:

```typescript
import { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import { sortMeetings } from '@/entities/meeting/lib/helpers';
```

Add topics state (after the existing `useState` declarations), reading an initial value from `localStorage`:

```typescript
  const [topicsInput, setTopicsInput] = useState('');
  const { sort, selectSort } = useCallFilters();

  useEffect(() => {
    const saved = window.localStorage.getItem('meeting-topics');
    if (saved) setTopicsInput(saved);
  }, []);

  const topics = topicsInput.split(',').map((t) => t.trim()).filter(Boolean);

  const applyTopics = (value: string) => {
    setTopicsInput(value);
    window.localStorage.setItem('meeting-topics', value);
  };
```

Update the data-fetching `useEffect` to pass `topics` and depend on it:

```typescript
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getMeetingSummaries(period, page, pageSize, topics, controller.signal)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((requestError: unknown) => {
        if (!active || (requestError instanceof DOMException && requestError.name === 'AbortError')) return;
        setError(requestError instanceof Error ? requestError.message : 'Could not load meetings.');
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, period, topicsInput]);
```

(`topicsInput` — not the derived `topics` array — is the dependency, since a new array identity on every render would otherwise refetch on every keystroke's re-render even without a value change; the array is cheap to recompute inline.)

Add the topics input and sort selector to the toolbar, inside `<div className={styles.controls}>`, before the `periods` div:

```typescript
          <input
            className={styles.topicsInput}
            placeholder="Topics (comma-separated)"
            value={topicsInput}
            onChange={(event) => applyTopics(event.target.value)}
          />
          <select
            aria-label="Sort by"
            value={sort}
            onChange={(event) => selectSort(event.target.value as typeof sort)}
          >
            <option value="time">Most recent</option>
            <option value="priority">Priority</option>
          </select>
```

Apply the sort to rendered items — replace `{data?.items.map((meeting) => (` with:

```typescript
        {(data ? sortMeetings(data.items, sort) : []).map((meeting) => (
```

- [ ] **Step 4: Add minimal styling for the new input**

Append to `src/widgets/call-history/ui/CallHistory.module.css`:

```css
.topicsInput {
  background: var(--surface-2, #1a1a1a);
  border: 1px solid var(--border, #333);
  border-radius: 4px;
  padding: 6px 10px;
  color: inherit;
  font-size: 13px;
}
```

(Reuses existing CSS custom properties already referenced elsewhere in this stylesheet — if `tsc`/lint flags an unresolved variable, check the actual token names in `src/shared/config/tokens` and align them; do not introduce new hardcoded colors as the primary style.)

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd /Users/viniciuslidington/Projects/coforgehackathon && npx tsc --noEmit`
Expected: no new errors

- [ ] **Step 6: Manual verification**

Run: `npm run dev` (frontend) and `npm run api` (backend, separate terminal), then in a browser:
1. Load the meetings list — confirm no `PriorityBadge` shows anywhere (no topics set) — Q10.
2. Type a topic that matches a real synced meeting's summary text (e.g. a keyword you know is in a sample `.vtt`) into the new input.
3. Confirm the matching row now shows a `PriorityBadge`; unrelated rows show none.
4. Switch the sort selector to "Priority" and confirm the most relevant row moves to the top; switch back to "Most recent" and confirm date ordering returns.
5. Reload the page — confirm the typed topic is restored from `localStorage`.

- [ ] **Step 7: Commit**

```bash
git add src/shared/api/meetings.ts src/features/call-filters/model/useCallFilters.ts src/widgets/call-history/ui/CallHistory.tsx src/widgets/call-history/ui/CallHistory.module.css
git commit -m "feat: add topics input and working priority sort to the meeting list"
```

---

## Task 9: Delete the legacy `entities/call` domain

**Files:**
- Delete: `src/entities/call/` (entire directory: `model/types.ts`, `model/data.ts`, `lib/helpers.ts`, `ui/PriorityBadge.tsx`, `ui/PriorityBadge.module.css`, `ui/FlagBadge.tsx`, `ui/FlagBadge.module.css`)

**Interfaces:**
- Consumes: nothing — this is a pure deletion, safe only once Tasks 6-8 have moved every still-needed export (`Priority`, `SortKey`, `tierColor`, `tierLabel`, `sortCalls`→`sortMeetings`, `PriorityBadge`, `CallRow`) out of this directory.

- [ ] **Step 1: Confirm nothing still imports from `entities/call`**

Run: `grep -rn "entities/call" /Users/viniciuslidington/Projects/coforgehackathon/src`
Expected: no output

If this finds anything, stop and resolve it before deleting — do not delete files still in use.

- [ ] **Step 2: Delete the directory**

```bash
git rm -r src/entities/call
```

- [ ] **Step 3: Verify TypeScript compiles and lint passes**

Run: `cd /Users/viniciuslidington/Projects/coforgehackathon && npx tsc --noEmit && npm run lint`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove legacy entities/call (mocked trading-desk domain, fully superseded)"
```

---

## Final check

- [ ] Run the full backend suite once more: `cd resume-ai-service && .venv/bin/pytest tests/ -v` — all PASS
- [ ] Re-run the Task 8 manual verification end to end
- [ ] Re-read the spec's "Critérios de aceitação" section and confirm each box is now true
