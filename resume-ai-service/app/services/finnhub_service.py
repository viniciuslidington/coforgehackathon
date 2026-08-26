"""Small, cached seam around the Finnhub REST API."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import re
from threading import Lock
from time import monotonic
from typing import Any, Callable, TypeVar

import httpx

from app.core.config import FINNHUB_API_KEY

BASE_URL = "https://finnhub.io/api/v1"
TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 300.0

T = TypeVar("T")
_cache: dict[tuple[str, str], tuple[float, object]] = {}
_cache_lock = Lock()
_client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS)


class FinnhubError(Exception):
    """Base error exposed by the Finnhub service seam."""


class FinnhubTimeoutError(FinnhubError):
    """The Finnhub request exceeded the configured timeout."""


def _normalized(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _cached(function_name: str, argument: str, loader: Callable[[], T]) -> T:
    key = (function_name, _normalized(argument))
    now = monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            return cached[1]  # type: ignore[return-value]
    value = loader()
    with _cache_lock:
        _cache[key] = (now + CACHE_TTL_SECONDS, value)
    return value


def _get(path: str, **params: str) -> Any:
    if not FINNHUB_API_KEY:
        return None
    try:
        response = _client.get(path, params={**params, "token": FINNHUB_API_KEY})
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise FinnhubTimeoutError("A consulta ao Finnhub excedeu o tempo limite.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise FinnhubError("Finnhub could not complete the request.") from exc


def search_symbol(query: str) -> str | None:
    """Resolve a company or asset name to Finnhub's best ticker match."""
    query = query.strip()
    if not query:
        return None

    def load() -> str | None:
        payload = _get("/search", q=query)
        results = payload.get("result", []) if isinstance(payload, dict) else []
        if not results:
            return None
        wanted = _normalized(query)
        exact = next(
            (
                item for item in results
                if _normalized(str(item.get("symbol", ""))) == wanted
                or _normalized(str(item.get("displaySymbol", ""))) == wanted
                or _normalized(str(item.get("description", ""))) == wanted
            ),
            None,
        )
        match = exact or results[0]
        symbol = match.get("symbol") or match.get("displaySymbol")
        return str(symbol).upper() if symbol else None

    return _cached("search_symbol", query, load)


def get_quote(ticker: str) -> dict[str, Any] | None:
    """Fetch the latest quote fields for a ticker."""
    ticker = ticker.strip().upper()
    if not ticker:
        return None

    def load() -> dict[str, Any] | None:
        payload = _get("/quote", symbol=ticker)
        if not isinstance(payload, dict) or not payload.get("t"):
            return None
        quote_time = datetime.fromtimestamp(float(payload["t"]), tz=UTC).isoformat()
        return {
            "ticker": ticker,
            "current_price": payload.get("c"),
            "change": payload.get("d"),
            "percent_change": payload.get("dp"),
            "high": payload.get("h"),
            "low": payload.get("l"),
            "open": payload.get("o"),
            "previous_close": payload.get("pc"),
            "quote_time": quote_time,
            "fetched_at": datetime.now(UTC).isoformat(),
            "source": "Finnhub",
        }

    return _cached("get_quote", ticker, load)


def get_news(ticker_or_term: str) -> list[dict[str, Any]]:
    """Fetch recent company news, resolving natural-language names when needed."""
    query = ticker_or_term.strip()
    if not query:
        return []

    def load() -> list[dict[str, Any]]:
        looks_like_ticker = bool(re.fullmatch(r"[A-Z][A-Z0-9.:-]{0,11}", query))
        symbol = query if looks_like_ticker else search_symbol(query)
        articles: list[dict[str, Any]] = []
        if symbol:
            today = date.today()
            payload = _get(
                "/company-news",
                symbol=symbol,
                **{"from": (today - timedelta(days=14)).isoformat(), "to": today.isoformat()},
            )
            if isinstance(payload, list):
                articles = payload
        else:
            payload = _get("/news", category="general")
            if isinstance(payload, list):
                needle = _normalized(query)
                articles = [
                    article for article in payload
                    if needle in _normalized(
                        f"{article.get('headline', '')} {article.get('summary', '')}"
                    )
                ]

        return [
            {
                "headline": str(article.get("headline", "")),
                "summary": str(article.get("summary", "")),
                "source": str(article.get("source", "Finnhub")),
                "url": str(article.get("url", "")),
                "published_at": (
                    datetime.fromtimestamp(float(article["datetime"]), tz=UTC).isoformat()
                    if article.get("datetime") else None
                ),
            }
            for article in articles[:5]
        ]

    return _cached("get_news", query, load)


def clear_cache() -> None:
    """Clear the process-local cache (primarily useful for tests)."""
    with _cache_lock:
        _cache.clear()
