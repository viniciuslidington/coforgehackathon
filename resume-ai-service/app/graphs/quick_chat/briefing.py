"""Generate a three-paragraph briefing plus key points over a meeting scope.

A plain function rather than a StateGraph: there is no tool loop here, just a
map-reduce over stored summaries, so a graph would add indirection and buy
nothing.

Reads only what is already in SQLite (title, summary, keywords, participants).
It never fetches a transcript from R2 — that would mean one network round trip
per meeting for text the summary already condenses.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import OPENROUTER_BRIEFING_MAX_TOKENS
from app.graphs.model import get_model
from app.graphs.quick_chat.prompts import (
    BRIEFING_DIGEST_SYSTEM_PROMPT,
    BRIEFING_SYSTEM_PROMPT,
    EMPTY_SCOPE_SUMMARY,
    MEETING_MARKER,
)
from app.services.meeting_scope import MeetingCard

logger = logging.getLogger("meeting-insights")

BRIEFING_DIRECT_LIMIT = 25
BRIEFING_BATCH_SIZE = 20
# Sized against real batch output, not the prompt's 120-word target: models
# routinely overshoot it, and a clipped digest silently drops meetings from
# the briefing that reduces them.
BRIEFING_DIGEST_MAX_TOKENS = 800
MAX_KEY_POINTS = 6
VALID_TONES = {"urgent", "teal", "muted"}


@dataclass
class KeyPointDraft:
    text: str
    tone: str
    meeting_id: str | None


@dataclass
class BriefingDraft:
    summary: str
    key_points: list[KeyPointDraft] = field(default_factory=list)
    truncated: bool = False


def _card_block(card: MeetingCard) -> str:
    participants = ", ".join(card.participants) or "unknown participants"
    keywords = ", ".join(card.keywords)
    return (
        f"[[meeting:{card.meeting_id}]] ({card.meeting_date}) {card.title}\n"
        f"  participants: {participants}\n"
        f"  keywords: {keywords}\n"
        f"  summary: {card.simple_summary}"
    )


def _was_truncated(response: object) -> bool:
    metadata = getattr(response, "response_metadata", None) or {}
    return metadata.get("finish_reason") == "length"


def _parse_briefing(text: str) -> BriefingDraft:
    """Parse the labelled-line format, degrading rather than raising.

    Mirrors `graphs/summary/nodes.py::create_overview`: labelled lines survive
    a chatty or partially-truncated model response far better than JSON, and
    nothing in this service uses structured output.
    """
    paragraphs: list[str] = []
    points: list[KeyPointDraft] = []

    for line in text.splitlines():
        stripped = line.strip()
        for label in ("PARAGRAPH1:", "PARAGRAPH2:", "PARAGRAPH3:"):
            if stripped.startswith(label):
                body = stripped.removeprefix(label).strip()
                if body:
                    paragraphs.append(body)
                break
        else:
            if stripped.startswith("POINT:"):
                point = _parse_point(stripped.removeprefix("POINT:"))
                if point is not None:
                    points.append(point)

    summary = "\n\n".join(paragraphs) if paragraphs else text.strip()
    return BriefingDraft(summary=summary, key_points=points[:MAX_KEY_POINTS])


def _parse_point(raw: str) -> KeyPointDraft | None:
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 2:
        return None
    tone = parts[0].lower()
    text = parts[1]
    if not text:
        return None

    # The marker belongs in the third field, but the model routinely writes it
    # inline in the bullet instead. Take it from wherever it landed and strip
    # it out, so the chip text never shows raw marker syntax.
    marker_source = " ".join(parts[2:]) if len(parts) > 2 else ""
    found = MEETING_MARKER.search(marker_source) or MEETING_MARKER.search(text)
    meeting_id = found.group(1).strip() if found else None

    text = MEETING_MARKER.sub("", text).strip(" ,;–-")
    if not text:
        return None

    return KeyPointDraft(
        text=text,
        tone=tone if tone in VALID_TONES else "muted",
        meeting_id=meeting_id or None,
    )


def _invoke(system_prompt: str, user_content: str, *, max_tokens: int) -> tuple[str, bool]:
    response = get_model(max_tokens=max_tokens).invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ])
    return str(response.content), _was_truncated(response)


def stream_briefing(cards: Sequence[MeetingCard]) -> Iterator[tuple[str, Any]]:
    """Summarize a meeting scope, yielding progress as it goes.

    A generator rather than a callback so the router can flush each step to
    the client *before* the next model call starts. A map-reduce over ninety
    meetings takes the better part of a minute; collecting labels and
    flushing them at the end would show the user nothing until it finished.

    Yields ("step", label) zero or more times, then exactly one
    ("draft", BriefingDraft).
    """
    if not cards:
        # Deterministic and free — never spend a model call on an empty scope.
        yield "draft", BriefingDraft(summary=EMPTY_SCOPE_SUMMARY, key_points=[])
        return

    if len(cards) <= BRIEFING_DIRECT_LIMIT:
        yield "step", f"Summarizing {len(cards)} meetings…"
        blocks = "\n\n".join(_card_block(card) for card in cards)
        text, truncated = _invoke(
            BRIEFING_SYSTEM_PROMPT, f"Meetings in scope:\n\n{blocks}",
            max_tokens=OPENROUTER_BRIEFING_MAX_TOKENS,
        )
        draft = _parse_briefing(text)
        draft.truncated = truncated
        yield "draft", draft
        return

    # Map-reduce: too many meetings to summarize in a single call.
    batches = [
        cards[index:index + BRIEFING_BATCH_SIZE]
        for index in range(0, len(cards), BRIEFING_BATCH_SIZE)
    ]
    digests: list[str] = []
    # A clipped digest loses meetings before the reduce step ever sees them, so
    # it counts as a truncated briefing just as much as a clipped final call.
    digest_truncated = False
    for number, batch in enumerate(batches, start=1):
        yield "step", f"Reading meetings, batch {number} of {len(batches)}…"
        blocks = "\n\n".join(_card_block(card) for card in batch)
        digest, was_truncated = _invoke(
            BRIEFING_DIGEST_SYSTEM_PROMPT, f"Meetings:\n\n{blocks}",
            max_tokens=BRIEFING_DIGEST_MAX_TOKENS,
        )
        digest_truncated = digest_truncated or was_truncated
        digests.append(digest.strip())

    yield "step", "Writing the briefing…"
    joined = "\n\n".join(f"Notes {index}:\n{digest}" for index, digest in enumerate(digests, start=1))
    text, truncated = _invoke(
        BRIEFING_SYSTEM_PROMPT,
        f"Condensed notes covering {len(cards)} meetings:\n\n{joined}",
        max_tokens=OPENROUTER_BRIEFING_MAX_TOKENS,
    )
    draft = _parse_briefing(text)
    draft.truncated = truncated or digest_truncated
    yield "draft", draft


def generate_briefing(
    cards: Sequence[MeetingCard],
    on_step: Callable[[str], None] | None = None,
) -> BriefingDraft:
    """Drain `stream_briefing` into a single draft, for non-streaming callers."""
    step = on_step or (lambda _label: None)
    draft = BriefingDraft(summary=EMPTY_SCOPE_SUMMARY)
    for kind, payload in stream_briefing(cards):
        if kind == "step":
            step(payload)
        else:
            draft = payload
    return draft
