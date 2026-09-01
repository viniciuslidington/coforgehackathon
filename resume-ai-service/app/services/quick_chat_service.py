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
from app.core.vtt import Caption
from app.schemas.quick_chat import BriefingResponse, KeyPoint, ReferencedMeeting
from app.services.database import get_cached_briefing, save_briefing
from app.services.meeting_scope import MeetingCard, ResolvedScope
from app.services.transcripts import transcript_repository

logger = logging.getLogger("meeting-insights")

UNKNOWN_MEETING_TEXT = "the meeting"

# Meeting ids look like "00021_convo_2p_Chris" — a sequence number, then
# words. Used to tell a citation the model mangled from bracketed prose that
# was never a citation at all.
MEETING_ID_SHAPE = re.compile(r"^\d{2,}[\w.-]*$")

# A Quick Chat answer spans many meetings, so a bare timestamp in it is
# ambiguous. The agent is asked to write `[[meeting:<id>@<start>-<end>]]`, which
# rides inside the existing marker grammar: `MEETING_MARKER`'s body class
# already admits `@ : . -`, and `VALID_MARKER`/`CITATION_RUN` both match the
# longer form, so the debris sweep and the citation cap keep working unchanged.
TIME = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
# En dash is what the transcript feeds the model; the others are it improvising.
DASH = r"\s*[\u2013\u2014-]\s*"
TIME_SUFFIX = re.compile(rf"^\s*({TIME})(?:{DASH}({TIME}))?\s*$")

# A citation the model wrote without attaching a meeting. Excludes `[[...]]` so
# it can never claim half of a real marker.
MARKER_OR_BARE_TIME = re.compile(
    r"(?P<marker>\[\[meeting:(?P<mid>[^\]\n]+)\]\])"
    rf"|(?P<bare>(?<!\[)\[\s*(?P<t1>{TIME})(?:{DASH}(?P<t2>{TIME}))?\s*\](?!\]))"
)

# How far outside a cue a citation may land and still count as naming it. The
# model tends to cite a cue boundary rather than its interior.
CUE_TOLERANCE_SECONDS = 1.0


def _clock_seconds(raw: str) -> float | None:
    """Seconds from "M:SS", "H:MM:SS" or "HH:MM:SS.mmm". None when unparseable.

    Deliberately not `vtt.timestamp_seconds`, which assumes milliseconds are
    present and raises without them.
    """
    parts = raw.strip().replace(",", ".").split(":")
    if not 2 <= len(parts) <= 3:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    hours, minutes, seconds = ([0.0, *numbers] if len(parts) == 2 else numbers)
    return hours * 3600 + minutes * 60 + seconds


def _cue_contains(captions: list[Caption] | None, seconds: float) -> bool:
    """Whether a cited second falls inside a cue the meeting actually has.

    An invented moment looks exactly like a real one, so the only way to tell
    is to check it against the transcript. Without this, a hallucinated
    timestamp becomes a link that scrolls the user somewhere arbitrary.
    """
    if not captions:
        return False
    for caption in captions:
        start = _clock_seconds(caption.start)
        end = _clock_seconds(caption.end)
        if start is None:
            continue
        upper = end if end is not None else start
        if start - CUE_TOLERANCE_SECONDS <= seconds <= upper + CUE_TOLERANCE_SECONDS:
            return True
    return False


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
    *,
    captions_for: Callable[[str], list[Caption] | None] | None = None,
) -> tuple[str, list[ReferencedMeeting]]:
    """Validate `[[meeting:<id>]]` markers against the scope.

    In-scope ids are kept verbatim and collected in first-appearance order.
    An out-of-scope id is repaired when it actually names a meeting title,
    and otherwise replaced with plain prose so the client never receives an
    id it cannot resolve.

    A marker may also carry `@<start>-<end>`, naming a moment inside that
    meeting. The time is checked against the meeting's real cues: a citation
    the transcript does not support loses its time and stays a plain meeting
    link, rather than becoming a link that scrolls somewhere arbitrary.
    `captions_for` defaults to the transcript repository, which caches
    parsed captions in memory, so validation costs at most one fetch per cited
    meeting per process.
    """
    referenced: dict[str, ReferencedMeeting] = {}
    titles = {card.title.casefold(): card for card in cards.values()}
    caption_cache: dict[str, list[Caption] | None] = {}
    # Resolved here rather than as a default argument: a default binds at
    # import time, which would make the repository impossible to substitute.
    load_captions = captions_for or transcript_repository.get_captions

    def captions(meeting_id: str) -> list[Caption] | None:
        if meeting_id not in caption_cache:
            caption_cache[meeting_id] = load_captions(meeting_id)
        return caption_cache[meeting_id]

    def valid_time(card: MeetingCard, raw: str) -> str | None:
        """The normalized `start[-end]` when the cited moment is real."""
        found = TIME_SUFFIX.match(raw)
        if found is None:
            return None
        start = _clock_seconds(found.group(1))
        if start is None or not _cue_contains(captions(card.meeting_id), start):
            logger.warning(
                "Dropped unsupported timestamp %r for meeting %s", raw, card.meeting_id
            )
            return None
        end = found.group(2)
        return f"{found.group(1)}\u2013{end}" if end else found.group(1)

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
        # One marker may carry several comma-separated meetings, and each may
        # carry its own `@time`.
        found: list[tuple[MeetingCard, str | None]] = []
        for part in body.split(","):
            reference, _, raw_time = part.partition("@")
            card = lookup(reference)
            if card is not None:
                found.append((card, valid_time(card, raw_time) if raw_time else None))

        if not found:
            logger.warning("Dropped unknown meeting marker %r", body)
            # Markers sit in the text as citations, not as nouns, so an
            # unresolvable one is removed outright — substituting prose would
            # read as "yield spikes the meeting". Bracketed text that was
            # never a citation is left alone rather than deleted.
            return "" if _is_citation(match.group(0), body) else match.group(0)

        for card, _ in found:
            referenced.setdefault(card.meeting_id, ReferencedMeeting(
                meeting_id=card.meeting_id,
                title=card.title,
                meeting_date=card.meeting_date,
            ))
        return "".join(
            f"[[meeting:{card.meeting_id}@{moment}]]" if moment
            else f"[[meeting:{card.meeting_id}]]"
            for card, moment in found
        )

    resolved = _cap_citation_runs(MEETING_MARKER.sub(replace, text))
    # After the cap, so a moment the agent attributed by position is never
    # trimmed away as if it were one more meeting citation.
    resolved = _attribute_bare_timestamps(resolved, cards, captions)
    resolved = _drop_duplicated_titles(resolved, referenced.values())
    return _tidy_spacing(_strip_citation_debris(resolved)), list(referenced.values())


def _attribute_bare_timestamps(
    text: str,
    cards: Mapping[str, MeetingCard],
    captions: Callable[[str], list[Caption] | None],
) -> str:
    """Give a timestamp the meeting it was written next to.

    The agent still writes bare moments despite the prompt. Reading left to
    right, the meeting most recently cited is the one a following timestamp
    belongs to — but only when that meeting's transcript actually contains the
    moment. A timestamp that fails that check keeps its plain text: a link to
    a guessed meeting is worse than no link.
    """
    current: str | None = None

    def rewrite(match: re.Match[str]) -> str:
        nonlocal current
        if match.group("marker"):
            current = match.group("mid").partition("@")[0]
            return match.group(0)

        if current is None or current not in cards:
            return match.group(0)
        start = _clock_seconds(match.group("t1"))
        if start is None or not _cue_contains(captions(current), start):
            return match.group(0)

        end = match.group("t2")
        moment = f"{match.group('t1')}\u2013{end}" if end else match.group("t1")
        return f"[[meeting:{current}@{moment}]]"

    return MARKER_OR_BARE_TIME.sub(rewrite, text)


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
            rf'(\[\[meeting:{re.escape(meeting.meeting_id)}(?:@[^\]\n]*)?\]\])',
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
