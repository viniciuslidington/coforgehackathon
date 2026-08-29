"""Deterministic retrieval tools for the scoped Quick Chat agent.

Every tool that names a meeting validates it against `state["meeting_ids"]`
first. Scope containment is enforced here in code rather than by prompt, so a
hallucinated id cannot read a meeting the user did not select.

No external/market tools live here: Quick Chat answers from the selected
meetings only. Market and geopolitical lookups stay in the per-meeting chat.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from app.core.vtt import transcript_from_captions
from app.graphs.quick_chat.state import QuickChatState
from app.services import priority
from app.services.transcripts import transcript_repository

logger = logging.getLogger("meeting-insights")

MAX_SEARCH_RESULTS = 8
MAX_SUMMARY_LOOKUPS = 8
MAX_TRANSCRIPT_MATCHES = 15
MAX_TRANSCRIPT_CHARS = 12_000


def _out_of_scope(meeting_ids: list[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": "Those meetings are not in the current scope.",
        "invalid_ids": meeting_ids,
    }


@tool
def list_scope_meetings(
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """List every meeting in the current scope with its date, title and keywords."""
    catalog = state.get("catalog", [])
    return {"ok": True, "meetings": catalog, "total": len(catalog)}


@tool
def search_scope(
    query: str,
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Find the meetings in scope most relevant to a query.

    Combines literal keyword matching with semantic similarity, so it finds
    both exact mentions and paraphrases.
    """
    needle = query.strip()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty query."}

    folded = needle.casefold()
    summaries = state.get("summaries", {})
    embeddings = state.get("embeddings", {})

    query_vector = None
    try:
        query_vector = priority.embed_topic(needle)
    except Exception:  # pragma: no cover - embedding model unavailable
        logger.warning("Semantic search unavailable; falling back to keyword only")

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in state.get("catalog", []):
        meeting_id = entry["meeting_id"]
        haystack = " ".join([
            entry.get("title", ""),
            " ".join(entry.get("keywords", [])),
            summaries.get(meeting_id, ""),
        ]).casefold()

        keyword_hit = folded in haystack
        semantic = 0.0
        blob = embeddings.get(meeting_id)
        if query_vector is not None and blob:
            try:
                semantic = priority.cosine_similarity(
                    priority.blob_to_vector(blob), query_vector
                )
            except ValueError:
                # A stored embedding from a previous model dimension.
                semantic = 0.0

        if not keyword_hit and semantic <= 0.0:
            continue

        # A literal mention is stronger evidence than similarity alone, so it
        # dominates the ranking rather than merely nudging it.
        score = semantic + (1.0 if keyword_hit else 0.0)
        scored.append((score, {
            "meeting_id": meeting_id,
            "title": entry.get("title", ""),
            "meeting_date": entry.get("meeting_date", ""),
            "score": round(score, 4),
            "why": "mentions the term" if keyword_hit else "semantically related",
        }))

    scored.sort(key=lambda item: item[0], reverse=True)
    matches = [item[1] for item in scored[:MAX_SEARCH_RESULTS]]
    return {"ok": True, "query": needle, "matches": matches, "total": len(scored)}


@tool
def get_meeting_summaries(
    meeting_ids: list[str],
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Read the stored summaries for specific meetings in the current scope."""
    in_scope = set(state.get("meeting_ids", []))
    invalid = [mid for mid in meeting_ids if mid not in in_scope]
    if invalid:
        return _out_of_scope(invalid)

    summaries = state.get("summaries", {})
    catalog = {entry["meeting_id"]: entry for entry in state.get("catalog", [])}
    results = [
        {
            "meeting_id": mid,
            "title": catalog.get(mid, {}).get("title", ""),
            "meeting_date": catalog.get(mid, {}).get("meeting_date", ""),
            "participants": catalog.get(mid, {}).get("participants", []),
            "summary": summaries.get(mid, ""),
        }
        for mid in meeting_ids[:MAX_SUMMARY_LOOKUPS]
    ]
    return {"ok": True, "meetings": results}


@tool
def search_meeting_transcript(
    meeting_id: str,
    term: str,
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Find exact, case-insensitive occurrences of a term inside one meeting."""
    if meeting_id not in set(state.get("meeting_ids", [])):
        return _out_of_scope([meeting_id])
    needle = term.strip().casefold()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty term."}

    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        return {"ok": False, "reason": "No transcript is available for that meeting."}

    matches = [
        {"start": caption.start, "end": caption.end, "text": caption.text}
        for caption in captions
        if needle in caption.text.casefold()
    ]
    return {
        "ok": True,
        "meeting_id": meeting_id,
        "term": term,
        "matches": matches[:MAX_TRANSCRIPT_MATCHES],
        "total": len(matches),
    }


@tool
def get_meeting_transcript(
    meeting_id: str,
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Read the full transcript of one meeting in the current scope."""
    if meeting_id not in set(state.get("meeting_ids", [])):
        return _out_of_scope([meeting_id])

    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        return {"ok": False, "reason": "No transcript is available for that meeting."}

    transcript = transcript_from_captions(captions)
    truncated = len(transcript) > MAX_TRANSCRIPT_CHARS
    return {
        "ok": True,
        "meeting_id": meeting_id,
        "transcript": transcript[:MAX_TRANSCRIPT_CHARS],
        "truncated": truncated,
    }


QUICK_CHAT_TOOLS: list[BaseTool] = [
    list_scope_meetings,
    search_scope,
    get_meeting_summaries,
    search_meeting_transcript,
    get_meeting_transcript,
]
