"""Scope resolution: the four presets, and the fingerprint's cache semantics."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.schemas.quick_chat import (
    DateRangeScope,
    ExplicitScope,
    LastDayScope,
    LastNScope,
)
from app.services.database import upsert_summary
from app.services.meeting_scope import resolve_scope, scope_fingerprint

PROMPT_VERSION = "test-v1"


def _seed(meeting_id: str, meeting_date: str, title: str = "Meeting") -> None:
    upsert_summary(
        meeting_id=meeting_id,
        title=title,
        meeting_date=meeting_date,
        participants=["Alex", "Mike"],
        simple_summary=f"Summary for {meeting_id}.",
        keywords=["eurusd", "hedge"],
        duration_seconds=60,
    )


def _resolve(selection):
    return resolve_scope(selection, prompt_version=PROMPT_VERSION)


def test_last_n_returns_the_newest_meetings(db_path: Path) -> None:
    for index in range(8):
        _seed(f"m{index}", f"2026-08-{10 + index:02d}")

    resolved = _resolve(LastNScope(count=3))

    assert len(resolved.cards) == 3
    assert resolved.meeting_ids == ("m7", "m6", "m5")
    assert resolved.range_end == "2026-08-17"


def test_last_day_anchors_on_the_newest_meeting_not_today(db_path: Path) -> None:
    """The corpus is older than today, so a wall-clock window would be empty."""
    _seed("old", "2026-08-01")
    _seed("previous", "2026-08-26")
    _seed("newest", "2026-08-27")

    resolved = _resolve(LastDayScope())

    assert set(resolved.meeting_ids) == {"previous", "newest"}
    assert (resolved.range_start, resolved.range_end) == ("2026-08-26", "2026-08-27")


def test_last_day_on_empty_database_falls_back_to_today(db_path: Path) -> None:
    resolved = _resolve(LastDayScope())

    assert resolved.cards == ()
    assert resolved.range_end == date.today().isoformat()
    assert resolved.range_start == (date.today() - timedelta(days=1)).isoformat()


def test_date_range_bounds_are_both_inclusive(db_path: Path) -> None:
    _seed("before", "2026-08-09")
    _seed("first", "2026-08-10")
    _seed("last", "2026-08-12")
    _seed("after", "2026-08-13")

    resolved = _resolve(DateRangeScope(date_from="2026-08-10", date_to="2026-08-12"))

    assert set(resolved.meeting_ids) == {"first", "last"}


def test_explicit_preserves_client_order_and_reports_unknown_ids(db_path: Path) -> None:
    _seed("a", "2026-08-10")
    _seed("b", "2026-08-11")

    resolved = _resolve(ExplicitScope(meeting_ids=["b", "ghost", "a"]))

    assert resolved.meeting_ids == ("b", "a")
    assert resolved.missing_meeting_ids == ("ghost",)


def test_fingerprint_ignores_ordering(db_path: Path) -> None:
    _seed("a", "2026-08-10")
    _seed("b", "2026-08-11")

    forwards = _resolve(ExplicitScope(meeting_ids=["a", "b"]))
    backwards = _resolve(ExplicitScope(meeting_ids=["b", "a"]))

    assert forwards.fingerprint == backwards.fingerprint


def test_fingerprint_changes_when_a_meeting_is_resynced(db_path: Path) -> None:
    _seed("a", "2026-08-10")
    before = _resolve(LastNScope(count=1)).fingerprint

    _seed("a", "2026-08-10", title="Re-synced title")
    after = _resolve(LastNScope(count=1)).fingerprint

    assert before != after


def test_fingerprint_changes_when_the_prompt_version_changes(db_path: Path) -> None:
    _seed("a", "2026-08-10")
    cards = _resolve(LastNScope(count=1)).cards

    assert scope_fingerprint(cards, "v1") != scope_fingerprint(cards, "v2")


def test_same_meetings_from_different_presets_share_a_fingerprint(db_path: Path) -> None:
    """A cached briefing is reusable whenever the meeting set is identical."""
    _seed("a", "2026-08-27")
    _seed("b", "2026-08-27")

    by_count = _resolve(LastNScope(count=2))
    by_ids = _resolve(ExplicitScope(meeting_ids=["a", "b"]))

    assert by_count.fingerprint == by_ids.fingerprint
