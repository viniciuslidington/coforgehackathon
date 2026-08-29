"""The last-10 briefing cache: round-tripping, LRU bump, and eviction."""
from __future__ import annotations

from pathlib import Path

from app.services.database import (
    BRIEFING_CACHE_LIMIT,
    get_cached_briefing,
    list_briefings,
    save_briefing,
)


def _save(fingerprint: str, **overrides) -> None:
    fields = {
        "fingerprint": fingerprint,
        "selection_json": '{"kind":"last_n","count":5}',
        "meeting_ids": ["a", "b"],
        "meeting_count": 2,
        "range_start": "2026-08-26",
        "range_end": "2026-08-27",
        "summary": "One.\n\nTwo.\n\nThree.",
        "key_points": [{"text": "Answer CITI-FX", "tone": "urgent", "meeting_id": "a"}],
        "referenced_meetings": [
            {"meeting_id": "a", "title": "Hoot call", "meeting_date": "2026-08-27"}
        ],
        "model": "test-model",
        "prompt_version": "test-v1",
    }
    fields.update(overrides)
    save_briefing(**fields)


def test_round_trip_preserves_structured_fields(db_path: Path) -> None:
    """Key points and references are objects, so they ride as JSON, not CSV."""
    _save("fp-1")

    row = get_cached_briefing("fp-1")

    assert row is not None
    assert row["meeting_ids"] == ["a", "b"]
    assert row["key_points"] == [
        {"text": "Answer CITI-FX", "tone": "urgent", "meeting_id": "a"}
    ]
    assert row["referenced_meetings"][0]["title"] == "Hoot call"


def test_missing_fingerprint_returns_none(db_path: Path) -> None:
    assert get_cached_briefing("absent") is None


def test_reading_a_briefing_marks_it_recently_used(db_path: Path) -> None:
    _save("fp-1")
    created = get_cached_briefing("fp-1")["created_at"]

    reread = get_cached_briefing("fp-1")

    assert reread["last_used_at"] >= created


def test_eviction_keeps_only_the_cache_limit(db_path: Path) -> None:
    for index in range(BRIEFING_CACHE_LIMIT + 5):
        _save(f"fp-{index:02d}")

    assert len(list_briefings(limit=100)) == BRIEFING_CACHE_LIMIT


def test_eviction_keeps_the_most_recently_used_not_the_newest(db_path: Path) -> None:
    """An old briefing the user keeps returning to must survive newer ones."""
    _save("fp-old")
    for index in range(BRIEFING_CACHE_LIMIT - 1):
        _save(f"fp-mid-{index:02d}")

    # Touch the oldest so it becomes the most recently used, then overflow.
    get_cached_briefing("fp-old")
    _save("fp-newest")

    survivors = {row["fingerprint"] for row in list_briefings(limit=100)}
    assert "fp-old" in survivors
    assert "fp-mid-00" not in survivors
    assert len(survivors) == BRIEFING_CACHE_LIMIT


def test_resaving_the_same_fingerprint_updates_in_place(db_path: Path) -> None:
    _save("fp-1")
    _save("fp-1", summary="Rewritten.")

    assert len(list_briefings(limit=100)) == 1
    assert get_cached_briefing("fp-1")["summary"] == "Rewritten."
