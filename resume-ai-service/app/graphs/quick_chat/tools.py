"""Deterministic retrieval tools for the scoped Quick Chat agent.

Every tool that names a meeting validates it against `state["meeting_ids"]`
first. Scope containment is enforced here in code rather than by prompt, so a
hallucinated id cannot read a meeting the user did not select.

No external/market tools live here: Quick Chat answers from the selected
meetings only. Market and geopolitical lookups stay in the per-meeting chat.
"""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from app.core.vtt import transcript_from_captions
from app.graphs.quick_chat.state import QuickChatState
from app.services import retrieval, transcript_index
from app.services.transcripts import transcript_repository

MAX_SEARCH_RESULTS = 8
MAX_SUMMARY_LOOKUPS = 8
MAX_TRANSCRIPT_MATCHES = 15
# The full-transcript tool is a last resort now that passages are searchable.
MAX_TRANSCRIPT_CHARS = 6_000
MAX_PASSAGES = 8
# Below this, a semantic-only match is noise: a name nobody mentioned still
# scores ~0.2 against everything with this model.
MIN_SEARCH_SIMILARITY = 0.3


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


def _scope_texts(state: QuickChatState, meeting_ids: list[str]) -> list[retrieval.MeetingText]:
    summaries = state.get("summaries", {})
    embeddings = state.get("embeddings", {})
    catalog = {entry["meeting_id"]: entry for entry in state.get("catalog", [])}
    return [
        retrieval.MeetingText(
            meeting_id=mid,
            title=catalog.get(mid, {}).get("title", ""),
            summary=summaries.get(mid, ""),
            keywords=catalog.get(mid, {}).get("keywords", []),
            participants=catalog.get(mid, {}).get("participants", []),
            topic_embedding=embeddings.get(mid),
        )
        for mid in meeting_ids
    ]


def _with_unindexed(result: dict[str, Any], unindexed: list[str]) -> dict[str, Any]:
    if unindexed:
        result["unindexed"] = unindexed
        result["note"] = (
            "These meetings' transcripts are not searchable yet; only their "
            "summaries were checked."
        )
    return result


@tool
def search_scope(
    query: str,
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Find the meetings in scope most relevant to a query.

    Searches titles, summaries and keywords and also what was said in every
    transcript, matching both exact mentions and paraphrases. Each match
    carries its best moment: a timestamp you can cite and a short snippet.
    """
    needle = query.strip()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty query."}

    meeting_ids = list(state.get("meeting_ids", []))
    unindexed = transcript_index.ensure_scope_indexed(meeting_ids)
    ranked = [
        match for match in retrieval.rank_meetings(needle, _scope_texts(state, meeting_ids))
        if match.lexical_source is not None or match.semantic >= MIN_SEARCH_SIMILARITY
    ]
    catalog = {entry["meeting_id"]: entry for entry in state.get("catalog", [])}
    matches = []
    for match in ranked[:MAX_SEARCH_RESULTS]:
        entry = catalog.get(match.meeting_id, {})
        found: dict[str, Any] = {
            "meeting_id": match.meeting_id,
            "title": entry.get("title", ""),
            "meeting_date": entry.get("meeting_date", ""),
            "score": match.score,
            "why": (
                f"mentions the term in its {match.lexical_source}"
                if match.lexical_source else "semantically related"
            ),
        }
        if match.moment is not None:
            found["best_moment"] = {"start": match.moment.start, "snippet": match.moment.snippet}
        matches.append(found)
    return _with_unindexed(
        {"ok": True, "query": needle, "matches": matches, "total": len(ranked)},
        unindexed,
    )


@tool
def search_transcripts(
    query: str,
    state: Annotated[QuickChatState, InjectedState],
    meeting_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Find the passages where a topic was discussed, across the scope.

    Returns short timestamped excerpts of what was actually said, best first,
    matching exact mentions and paraphrases. Pass meeting_ids to search only
    those meetings. This is the main way to gather evidence and quotes.
    """
    needle = query.strip()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty query."}
    in_scope = list(state.get("meeting_ids", []))
    if meeting_ids:
        invalid = [mid for mid in meeting_ids if mid not in set(in_scope)]
        if invalid:
            return _out_of_scope(invalid)
        targets = list(dict.fromkeys(meeting_ids))
    else:
        targets = in_scope

    unindexed = transcript_index.ensure_scope_indexed(targets)
    hits = [
        hit for hit in retrieval.search_chunks(needle, targets, k=MAX_PASSAGES)
        if hit.lexical or hit.semantic >= MIN_SEARCH_SIMILARITY
    ]
    return _with_unindexed(
        {"ok": True, "query": needle, "passages": [hit.to_dict() for hit in hits]},
        unindexed,
    )


@tool
def read_transcript_around(
    meeting_id: str,
    start: str,
    state: Annotated[QuickChatState, InjectedState],
) -> dict[str, Any]:
    """Read the stretch of one meeting around a moment, for more context.

    `start` is a timestamp taken from a search result. Returns the passage
    that contains it plus the passages just before and after.
    """
    if meeting_id not in set(state.get("meeting_ids", [])):
        return _out_of_scope([meeting_id])
    transcript_index.ensure_indexed(meeting_id)
    passages = retrieval.chunk_at(meeting_id, start, radius=1)
    if not passages:
        return {"ok": False, "reason": "No passage of that meeting covers that moment."}
    return {
        "ok": True,
        "meeting_id": meeting_id,
        "start": passages[0].start,
        "end": passages[-1].end,
        "excerpt": retrieval.merge_chunks(passages),
    }


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
    """Read the full transcript of one meeting in the current scope.

    Expensive and truncated for long meetings: prefer search_transcripts and
    read_transcript_around, and use this only for a whole-meeting walkthrough.
    """
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
    search_transcripts,
    read_transcript_around,
    get_meeting_summaries,
    search_meeting_transcript,
    get_meeting_transcript,
]
