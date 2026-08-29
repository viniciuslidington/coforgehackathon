"""Resolve a client's meeting-scope selection into a concrete meeting set.

Everything downstream — the briefing, the agent's catalog, its tools' access
checks, and the briefing cache key — reads from the `ResolvedScope` produced
here, so scope is decided exactly once per request.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Sequence

from fastapi import HTTPException

from app.core.config import OPENROUTER_MODEL
from app.schemas.quick_chat import (
    MAX_SCOPE_MEETINGS,
    DateRangeScope,
    ExplicitScope,
    LastDayScope,
    LastNScope,
    MeetingScopeSelection,
    ScopeResolution,
)
from app.services.database import (
    list_summaries,
    list_summaries_between,
    list_summaries_by_ids,
    max_meeting_date,
)

FINGERPRINT_VERSION = "v1"
SCOPE_WARNING_THRESHOLD = 15


@dataclass(frozen=True)
class MeetingCard:
    """The stored facts about one meeting, without its transcript."""
    meeting_id: str
    title: str
    meeting_date: str
    participants: list[str]
    simple_summary: str
    keywords: list[str]
    duration_seconds: int
    refreshed_at: str
    topic_embedding: bytes | None


@dataclass(frozen=True)
class ResolvedScope:
    selection: MeetingScopeSelection
    cards: tuple[MeetingCard, ...]
    range_start: str | None
    range_end: str | None
    resolved_at: str
    truncated: bool
    missing_meeting_ids: tuple[str, ...]
    fingerprint: str

    @property
    def meeting_ids(self) -> tuple[str, ...]:
        return tuple(card.meeting_id for card in self.cards)

    @property
    def cards_by_id(self) -> dict[str, MeetingCard]:
        return {card.meeting_id: card for card in self.cards}

    def to_resolution(self) -> ScopeResolution:
        return ScopeResolution(
            fingerprint=self.fingerprint,
            meeting_ids=list(self.meeting_ids),
            meeting_count=len(self.cards),
            range_start=self.range_start,
            range_end=self.range_end,
            resolved_at=self.resolved_at,
            truncated=self.truncated,
            missing_meeting_ids=list(self.missing_meeting_ids),
        )


def _row_to_card(row: dict[str, object]) -> MeetingCard:
    return MeetingCard(
        meeting_id=str(row["meeting_id"]),
        title=str(row["title"]),
        meeting_date=str(row["meeting_date"]),
        participants=[p.strip() for p in str(row["participants"]).split(",") if p.strip()],
        simple_summary=str(row["simple_summary"]),
        keywords=[k.strip() for k in str(row["keywords"]).split(",") if k.strip()],
        duration_seconds=int(row["duration_seconds"] or 0),
        refreshed_at=str(row["refreshed_at"]),
        topic_embedding=row.get("topic_embedding"),  # type: ignore[arg-type]
    )


def scope_fingerprint(cards: Sequence[MeetingCard], prompt_version: str) -> str:
    """A stable, content-derived cache key for a set of meetings.

    Sorted, so the same meetings in a different order share one cache entry.
    Includes each meeting's `refreshed_at` so re-syncing invalidates, and the
    model and prompt version so changing either never serves stale text.

    Deliberately excludes the selection kind: "Last 5 meetings" and an
    explicit page listing those same 5 deserve the same briefing.
    """
    payload = "|".join([
        FINGERPRINT_VERSION,
        OPENROUTER_MODEL,
        prompt_version,
        *sorted(f"{card.meeting_id}@{card.refreshed_at}" for card in cards),
    ])
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _date_bounds(cards: Sequence[MeetingCard]) -> tuple[str | None, str | None]:
    if not cards:
        return None, None
    dates = sorted(card.meeting_date for card in cards)
    return dates[0], dates[-1]


def resolve_scope(selection: MeetingScopeSelection, *, prompt_version: str) -> ResolvedScope:
    """Turn a scope selection into an ordered, de-duplicated meeting set."""
    truncated = False
    missing: tuple[str, ...] = ()

    if isinstance(selection, LastNScope):
        rows, _ = list_summaries(offset=0, limit=selection.count)
        cards = tuple(_row_to_card(row) for row in rows)
        range_start, range_end = _date_bounds(cards)

    elif isinstance(selection, LastDayScope):
        # Anchored to the data, not the wall clock: meeting_date records the
        # sync date, so a literal today/yesterday window resolves to nothing
        # whenever syncing has paused for a day.
        anchor = max_meeting_date() or date.today().isoformat()
        previous = (date.fromisoformat(anchor) - timedelta(days=1)).isoformat()
        rows = list_summaries_between(date_from=previous, date_to=anchor)
        cards = tuple(_row_to_card(row) for row in rows)
        range_start, range_end = previous, anchor

    elif isinstance(selection, DateRangeScope):
        if selection.date_from > selection.date_to:
            raise HTTPException(
                status_code=422,
                detail="date_from must be on or before date_to.",
            )
        rows = list_summaries_between(date_from=selection.date_from, date_to=selection.date_to)
        cards = tuple(_row_to_card(row) for row in rows)
        if len(cards) > MAX_SCOPE_MEETINGS:
            # Rows arrive newest-first, so this keeps the most recent.
            cards = cards[:MAX_SCOPE_MEETINGS]
            truncated = True
        range_start, range_end = selection.date_from, selection.date_to

    elif isinstance(selection, ExplicitScope):
        rows = list_summaries_by_ids(selection.meeting_ids)
        by_id = {str(row["meeting_id"]): row for row in rows}
        # Preserve the order the client sent, which is the order on screen.
        cards = tuple(
            _row_to_card(by_id[mid]) for mid in selection.meeting_ids if mid in by_id
        )
        missing = tuple(mid for mid in selection.meeting_ids if mid not in by_id)
        range_start, range_end = _date_bounds(cards)

    else:  # pragma: no cover - the discriminated union makes this unreachable
        raise HTTPException(status_code=422, detail="Unsupported meeting scope.")

    return ResolvedScope(
        selection=selection,
        cards=cards,
        range_start=range_start,
        range_end=range_end,
        resolved_at=datetime.now(UTC).isoformat(),
        truncated=truncated,
        missing_meeting_ids=missing,
        fingerprint=scope_fingerprint(cards, prompt_version),
    )
