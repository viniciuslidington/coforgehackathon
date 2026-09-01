"""Briefing orchestration and meeting-marker validation for Quick Chat.

The agent is prompted to reference meetings as `[[meeting:<id>]]`, but a model
will occasionally invent an id. `resolve_markers` is the deterministic gate
that keeps invented ids off the wire, so the frontend only ever needs a
lookup — never a guard.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable, Iterable, Iterator, Mapping

from app.core.config import OPENROUTER_MODEL
from app.graphs.quick_chat.briefing import BriefingDraft, generate_briefing, stream_briefing
from app.graphs.quick_chat.prompts import (
    BRIEFING_PROMPT_VERSION,
    MAX_INLINE_CITATIONS,
    MEETING_MARKER,
)
from app.schemas.quick_chat import BriefingResponse, KeyPoint, ReferencedMeeting
from app.services.database import get_cached_briefing, save_briefing
from app.services.meeting_scope import MeetingCard, ResolvedScope

logger = logging.getLogger("meeting-insights")

UNKNOWN_MEETING_TEXT = "the meeting"

# Meeting ids look like "00021_convo_2p_Chris" — a sequence number, then
# words. Used to tell a citation the model mangled from bracketed prose that
# was never a citation at all.
MEETING_ID_SHAPE = re.compile(r"^\d{2,}[\w.-]*$")


def _is_citation(whole_match: str, body: str) -> bool:
    """Whether a `[[...]]` was meant as a meeting citation.

    Checks the whole match for the prefix, not the captured body — the
    pattern consumes `meeting:` into a non-capturing group.
    """
    if "meeting" in whole_match.casefold():
        return True
    parts = [part.strip() for part in body.split(",") if part.strip()]
    return bool(parts) and all(MEETING_ID_SHAPE.match(part) for part in parts)


def resolve_markers(
    text: str,
    cards: Mapping[str, MeetingCard],
) -> tuple[str, list[ReferencedMeeting]]:
    """Validate `[[meeting:<id>]]` markers against the scope.

    In-scope ids are kept verbatim and collected in first-appearance order.
    An out-of-scope id is repaired when it actually names a meeting title,
    and otherwise replaced with plain prose so the client never receives an
    id it cannot resolve.
    """
    referenced: dict[str, ReferencedMeeting] = {}
    titles = {card.title.casefold(): card for card in cards.values()}

    def lookup(raw: str) -> MeetingCard | None:
        cleaned = raw.strip().removeprefix("meeting:").strip().strip("\"'“”‘’")
        if not cleaned:
            return None
        # The model sometimes emits the title where an id belongs.
        card = cards.get(cleaned) or titles.get(cleaned.casefold())
        if card is not None:
            return card
        # It also truncates ids, dropping the trailing name ("00021_convo_2p"
        # for "00021_convo_2p_Chris"). Ids begin with a unique sequence
        # number, so an unambiguous prefix recovers the intended meeting.
        matches = [c for c in cards.values() if c.meeting_id.startswith(cleaned)]
        return matches[0] if len(matches) == 1 else None

    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        # One marker may carry several comma-separated meetings.
        found = [card for card in (lookup(part) for part in body.split(",")) if card]

        if not found:
            logger.warning("Dropped unknown meeting marker %r", body)
            # Markers sit in the text as citations, not as nouns, so an
            # unresolvable one is removed outright — substituting prose would
            # read as "yield spikes the meeting". Bracketed text that was
            # never a citation is left alone rather than deleted.
            return "" if _is_citation(match.group(0), body) else match.group(0)

        for card in found:
            referenced.setdefault(card.meeting_id, ReferencedMeeting(
                meeting_id=card.meeting_id,
                title=card.title,
                meeting_date=card.meeting_date,
            ))
        return "".join(f"[[meeting:{card.meeting_id}]]" for card in found)

    resolved = _cap_citation_runs(MEETING_MARKER.sub(replace, text))
    resolved = _drop_duplicated_titles(resolved, referenced.values())
    return _tidy_spacing(_strip_citation_debris(resolved)), list(referenced.values())


VALID_MARKER = re.compile(r"\[\[meeting:[^\]\n]+\]\]")
# Bracketed id-ish debris: the model also emits unbalanced forms like
# "[00032]]" that never matched the marker pattern in the first place.
CITATION_DEBRIS = re.compile(
    r"\[+\s*(?:meeting\s*:)?\s*\d{2,}[\w.-]*(?:\s*,\s*(?:meeting\s*:)?\s*\d{2,}[\w.-]*)*\s*\]+"
)


def _strip_citation_debris(text: str) -> str:
    """Remove bracket fragments left by malformed citations.

    Every real citation has already been normalized to `[[meeting:<id>]]`, so
    anything still bracketed and id-shaped is debris. Valid markers are held
    aside while sweeping so they are never touched.
    """
    pieces = VALID_MARKER.split(text)
    markers = VALID_MARKER.findall(text)
    cleaned = [CITATION_DEBRIS.sub("", piece) for piece in pieces]
    # Re-interleave: split() yields one more piece than there are markers.
    return "".join(
        piece + (markers[index] if index < len(markers) else "")
        for index, piece in enumerate(cleaned)
    )


def _tidy_spacing(text: str) -> str:
    """Close the gaps left by removed markers."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


CITATION_RUN = re.compile(r"(?:\[\[meeting:[^\]\n]+\]\])+")


def _cap_citation_runs(text: str) -> str:
    """Trim any run of adjacent citations to a readable number.

    The cap has to apply to the run, not the individual marker: the model
    cites either as one grouped marker or as a chain of single ones, and a
    chain of seventeen titles buries the sentence just as thoroughly.
    Everything trimmed here is still listed in `referenced_meetings`.
    """
    def trim(match: re.Match[str]) -> str:
        markers = MEETING_MARKER.findall(match.group(0))
        return "".join(f"[[meeting:{marker}]]" for marker in markers[:MAX_INLINE_CITATIONS])

    return CITATION_RUN.sub(trim, text)


def _drop_duplicated_titles(text: str, meetings: Iterable[ReferencedMeeting]) -> str:
    """Remove a title written immediately before its own marker.

    The prompt tells the model to write the marker *instead of* the title, but
    it often writes both — and since the UI renders the marker as the title,
    that shows the name twice in a row.
    """
    for meeting in meetings:
        pattern = re.compile(
            rf'["“‘]?{re.escape(meeting.title)}["”’]?[,:]?\s*'
            rf'(\[\[meeting:{re.escape(meeting.meeting_id)}\]\])',
            re.IGNORECASE,
        )
        text = pattern.sub(r"\1", text)
    return text


def _cached_response(row: Mapping[str, object], resolved: ResolvedScope) -> BriefingResponse:
    return BriefingResponse(
        summary=str(row["summary"]),
        key_points=[KeyPoint(**point) for point in row["key_points"]],  # type: ignore[arg-type]
        referenced_meetings=[
            ReferencedMeeting(**meeting) for meeting in row["referenced_meetings"]  # type: ignore[arg-type]
        ],
        scope=resolved.to_resolution(),
        cached=True,
        # Persisted, so a shortened briefing keeps saying so on every reload
        # instead of silently looking complete once it comes from cache.
        truncated=bool(row["truncated"]),
        created_at=str(row["created_at"]),
    )


def cached_briefing_for_scope(resolved: ResolvedScope) -> BriefingResponse | None:
    row = get_cached_briefing(resolved.fingerprint)
    return _cached_response(row, resolved) if row else None


def stream_briefing_for_scope(
    resolved: ResolvedScope,
    *,
    force: bool = False,
) -> Iterator[tuple[str, object]]:
    """Yield ("step", label) as the briefing is built, then ("briefing", response).

    A cache hit yields the briefing immediately with no steps and no model call.
    """
    if not force:
        cached = cached_briefing_for_scope(resolved)
        if cached is not None:
            yield "briefing", cached
            return

    draft = None
    for kind, payload in stream_briefing(resolved.cards):
        if kind == "step":
            yield "step", payload
        else:
            draft = payload

    yield "briefing", _persist_draft(resolved, draft)


def briefing_for_scope(
    resolved: ResolvedScope,
    *,
    force: bool = False,
    on_step: Callable[[str], None] | None = None,
) -> BriefingResponse:
    """Return a briefing for the scope, generating one only on a cache miss."""
    if not force:
        cached = cached_briefing_for_scope(resolved)
        if cached is not None:
            return cached
    return _persist_draft(resolved, generate_briefing(resolved.cards, on_step))


def _persist_draft(resolved: ResolvedScope, draft: BriefingDraft | None) -> BriefingResponse:
    """Validate a draft's meeting markers, cache it, and shape the response."""
    if draft is None:  # pragma: no cover - stream_briefing always yields a draft
        raise RuntimeError("The briefing generator produced no draft.")

    cards_by_id = resolved.cards_by_id
    summary, referenced = resolve_markers(draft.summary, cards_by_id)
    key_points = [
        KeyPoint(
            text=point.text,
            tone=point.tone,  # type: ignore[arg-type]
            meeting_id=point.meeting_id if point.meeting_id in cards_by_id else None,
        )
        for point in draft.key_points
    ]

    # A key point can cite a meeting the prose never names, so fold those in
    # too — referenced_meetings is what the whole briefing draws on.
    seen = {meeting.meeting_id for meeting in referenced}
    for point in key_points:
        if point.meeting_id and point.meeting_id not in seen:
            card = cards_by_id[point.meeting_id]
            referenced.append(ReferencedMeeting(
                meeting_id=card.meeting_id,
                title=card.title,
                meeting_date=card.meeting_date,
            ))
            seen.add(card.meeting_id)

    created_at = resolved.resolved_at
    save_briefing(
        fingerprint=resolved.fingerprint,
        selection_json=json.dumps(resolved.selection.model_dump()),
        meeting_ids=resolved.meeting_ids,
        meeting_count=len(resolved.cards),
        range_start=resolved.range_start,
        range_end=resolved.range_end,
        summary=summary,
        key_points=[point.model_dump() for point in key_points],
        referenced_meetings=[meeting.model_dump() for meeting in referenced],
        model=OPENROUTER_MODEL,
        prompt_version=BRIEFING_PROMPT_VERSION,
        truncated=draft.truncated,
    )

    return BriefingResponse(
        summary=summary,
        key_points=key_points,
        referenced_meetings=referenced,
        scope=resolved.to_resolution(),
        cached=False,
        truncated=draft.truncated,
        created_at=created_at,
    )
