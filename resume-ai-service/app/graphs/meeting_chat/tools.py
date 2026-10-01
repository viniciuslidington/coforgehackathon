"""Tools available to the per-meeting chat agent."""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from app.graphs.meeting_chat.nodes import synthesize_geopolitical_analysis
from app.graphs.meeting_chat.state import ChatState
from app.services import finnhub_service, retrieval, transcript_index

MAX_SEARCH_PASSAGES = 6
# Below this a semantic-only passage is noise with the local model.
MIN_SEARCH_SIMILARITY = 0.3


def _external_failure(exc: Exception | None = None) -> dict[str, Any]:
    if isinstance(exc, finnhub_service.FinnhubTimeoutError):
        reason = "The Finnhub request timed out."
    else:
        reason = "Finnhub is unavailable or not configured."
    return {"ok": False, "reason": reason, "source": "Finnhub"}


@tool
def get_meeting_metadata(
    state: Annotated[ChatState, InjectedState],
) -> dict[str, Any]:
    """Return participants, date, duration and keywords for the current meeting."""
    metadata = state.get("metadata") or {}
    return {"ok": True, **metadata}


@tool
def search_transcript_keyword(
    term: str,
    state: Annotated[ChatState, InjectedState],
) -> dict[str, Any]:
    """Find exact, case-insensitive occurrences of a term in the current meeting."""
    needle = term.strip().casefold()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty term."}
    matches = [
        {
            "start": caption.get("start", ""),
            "end": caption.get("end", ""),
            "text": caption.get("text", ""),
        }
        for caption in state.get("captions", [])
        if needle in caption.get("text", "").casefold()
    ]
    return {"ok": True, "term": term, "matches": matches[:20], "total": len(matches)}


@tool
def get_statements_by_speaker(
    name: str,
    state: Annotated[ChatState, InjectedState],
) -> dict[str, Any]:
    """Return timestamped statements made by one participant in the current meeting."""
    wanted = name.strip().casefold()
    statements: list[dict[str, str]] = []
    for caption in state.get("captions", []):
        speaker, separator, statement = caption.get("text", "").partition(":")
        if separator and speaker.strip().casefold() == wanted:
            statements.append({
                "start": caption.get("start", ""),
                "end": caption.get("end", ""),
                "speaker": speaker.strip(),
                "text": statement.strip(),
            })
    return {"ok": True, "speaker": name, "statements": statements, "total": len(statements)}


@tool
def search_meeting(
    query: str,
    state: Annotated[ChatState, InjectedState],
) -> dict[str, Any]:
    """Find the passages of the current meeting about a topic.

    Matches exact mentions and paraphrases, so it finds a discussion even
    when it used different words. Returns timestamped excerpts, best first.
    """
    needle = query.strip()
    if not needle:
        return {"ok": False, "reason": "Provide a non-empty query."}
    meeting_id = state.get("meeting_id", "")
    if not transcript_index.ensure_indexed(meeting_id):
        return {"ok": False, "reason": "This meeting cannot be searched; use search_transcript_keyword."}
    hits = [
        hit for hit in retrieval.search_chunks(
            needle, [meeting_id], k=MAX_SEARCH_PASSAGES, per_meeting=MAX_SEARCH_PASSAGES,
        )
        if hit.lexical or hit.semantic >= MIN_SEARCH_SIMILARITY
    ]
    return {
        "ok": True,
        "query": needle,
        "passages": [
            {"start": hit.start, "end": hit.end, "excerpt": hit.transcript}
            for hit in hits
        ],
    }


@tool
def read_transcript_around(
    start: str,
    state: Annotated[ChatState, InjectedState],
) -> dict[str, Any]:
    """Read the stretch of the current meeting around a timestamp.

    Returns the passage containing `start` plus the passages just before and
    after it.
    """
    meeting_id = state.get("meeting_id", "")
    if not transcript_index.ensure_indexed(meeting_id):
        return {"ok": False, "reason": "This meeting cannot be read by passage."}
    passages = retrieval.chunk_at(meeting_id, start, radius=1)
    if not passages:
        return {"ok": False, "reason": "No passage of this meeting covers that moment."}
    return {
        "ok": True,
        "start": passages[0].start,
        "end": passages[-1].end,
        "excerpt": retrieval.merge_chunks(passages),
    }


@tool
def resolve_symbol(name: str) -> dict[str, Any]:
    """Resolve a natural-language company or asset name to a market ticker."""
    try:
        symbol = finnhub_service.search_symbol(name)
    except Exception as exc:
        return _external_failure(exc)
    if not symbol:
        return _external_failure()
    return {"ok": True, "query": name, "ticker": symbol, "source": "Finnhub"}


@tool
def get_market_quote(ticker: str) -> dict[str, Any]:
    """Get the latest market price and change for a ticker from Finnhub."""
    try:
        quote = finnhub_service.get_quote(ticker)
    except Exception as exc:
        return _external_failure(exc)
    if not quote:
        return _external_failure()
    return {"ok": True, **quote}


def _market_news(ticker_or_term: str) -> dict[str, Any]:
    try:
        articles = finnhub_service.get_news(ticker_or_term)
    except Exception as exc:
        return _external_failure(exc)
    if not articles:
        return _external_failure()
    return {
        "ok": True,
        "query": ticker_or_term,
        "source": "Finnhub",
        "articles": articles,
    }


@tool
def get_market_news(ticker_or_term: str) -> dict[str, Any]:
    """Get recent Finnhub news for a ticker, company, asset or market term."""
    return _market_news(ticker_or_term)


@tool
def get_geopolitical_analysis(asset_or_topic: str) -> dict[str, Any]:
    """Create a short geopolitical analysis grounded in current Finnhub articles."""
    news = _market_news(asset_or_topic)
    if not news.get("ok"):
        return news
    try:
        analysis = synthesize_geopolitical_analysis(news["articles"])
    except Exception as exc:
        return {
            "ok": False,
            "reason": "The news was found, but the geopolitical synthesis failed.",
            "source": "Finnhub",
            "articles": news["articles"],
            "error_type": type(exc).__name__,
        }
    return {
        "ok": True,
        "topic": asset_or_topic,
        "source": "Finnhub",
        "articles": news["articles"],
        "analysis": analysis,
    }


MEETING_CHAT_TOOLS: list[BaseTool] = [
    get_meeting_metadata,
    search_transcript_keyword,
    get_statements_by_speaker,
    search_meeting,
    read_transcript_around,
    resolve_symbol,
    get_market_quote,
    get_market_news,
    get_geopolitical_analysis,
]
