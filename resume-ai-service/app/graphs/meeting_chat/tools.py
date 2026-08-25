"""Tools available to the per-meeting chat agent."""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState

from app.graphs.meeting_chat.nodes import synthesize_geopolitical_analysis
from app.graphs.meeting_chat.state import ChatState
from app.services import finnhub_service


def _external_failure(exc: Exception | None = None) -> dict[str, Any]:
    if isinstance(exc, finnhub_service.FinnhubTimeoutError):
        reason = "A consulta ao Finnhub excedeu o tempo limite."
    else:
        reason = "O Finnhub está indisponível ou não foi configurado."
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
        return {"ok": False, "reason": "Informe um termo não vazio."}
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
            "reason": "As notícias foram encontradas, mas a síntese geopolítica falhou.",
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
    resolve_symbol,
    get_market_quote,
    get_market_news,
    get_geopolitical_analysis,
]
