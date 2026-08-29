"""Routes for the scoped Quick Chat: briefings and cross-meeting Q&A.

Both streaming handlers are sync `def` on purpose. FastAPI runs them in a
threadpool, and `graph.stream(...)` is a blocking generator that would stall
the event loop if these were `async def`.
"""
from __future__ import annotations

import logging
from typing import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.graphs.quick_chat.graph import (
    QUICK_CHAT_RECURSION_LIMIT,
    quick_chat_graph,
    thread_id_for,
)
from app.graphs.quick_chat.prompts import (
    BRIEFING_PROMPT_VERSION,
    EMPTY_SCOPE_ANSWER,
    QUICK_CHAT_FALLBACK_STEP_LABEL,
    QUICK_CHAT_INITIAL_STEP_LABEL,
    QUICK_CHAT_SYNTHESIS_STEP_LABEL,
    QUICK_CHAT_TOOL_STEP_LABELS,
)
from app.schemas.agent import ErrorEvent, StepEvent
from app.schemas.quick_chat import (
    BriefingEvent,
    BriefingLookupRequest,
    BriefingLookupResponse,
    BriefingRequest,
    QuickChatAnswerEvent,
    QuickChatRequest,
)
from app.services.meeting_scope import ResolvedScope, resolve_scope
from app.services.quick_chat_service import (
    cached_briefing_for_scope,
    resolve_markers,
    stream_briefing_for_scope,
)
from app.services.sse import message_text, sse

logger = logging.getLogger("meeting-insights")

router = APIRouter(tags=["quick-chat"])


def _resolve(selection) -> ResolvedScope:
    return resolve_scope(selection, prompt_version=BRIEFING_PROMPT_VERSION)


@router.post("/quick-chat/briefings/lookup", response_model=BriefingLookupResponse)
def lookup_briefing(request: BriefingLookupRequest) -> BriefingLookupResponse:
    """Resolve a scope and return its cached briefing, if one exists.

    Never calls the model. This is the one round trip that drives the initial
    render, every scope switch, and the "many meetings" warning count.
    """
    resolved = _resolve(request.scope)
    return BriefingLookupResponse(
        scope=resolved.to_resolution(),
        briefing=cached_briefing_for_scope(resolved),
    )


@router.post("/quick-chat/briefings")
def create_briefing(request: BriefingRequest) -> StreamingResponse:
    """Stream the generation of a briefing over the selected meetings."""
    resolved = _resolve(request.scope)

    def event_stream() -> Iterator[str]:
        try:
            for kind, payload in stream_briefing_for_scope(resolved, force=request.force):
                if kind == "step":
                    yield sse(StepEvent(label=str(payload)))
                else:
                    yield sse(BriefingEvent(briefing=payload))
        except Exception as exc:
            logger.exception("Quick chat briefing failed fingerprint=%s", resolved.fingerprint)
            detail = str(exc) if isinstance(exc, RuntimeError) else "Could not generate the briefing."
            yield sse(ErrorEvent(detail=detail))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/quick-chat/questions")
def ask_quick_chat_question(request: QuickChatRequest) -> StreamingResponse:
    """Stream an agent answer grounded in the selected meetings."""
    resolved = _resolve(request.scope)
    cards_by_id = resolved.cards_by_id

    graph_input = {
        "scope_fingerprint": resolved.fingerprint,
        "meeting_ids": list(resolved.meeting_ids),
        "catalog": [
            {
                "meeting_id": card.meeting_id,
                "title": card.title,
                "meeting_date": card.meeting_date,
                "keywords": card.keywords,
                "participants": card.participants,
            }
            for card in resolved.cards
        ],
        "summaries": {card.meeting_id: card.simple_summary for card in resolved.cards},
        "embeddings": {
            card.meeting_id: card.topic_embedding
            for card in resolved.cards
            if card.topic_embedding
        },
        "messages": [HumanMessage(content=request.question)],
    }
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id_for(request.session_id)},
        "recursion_limit": QUICK_CHAT_RECURSION_LIMIT,
    }

    def event_stream() -> Iterator[str]:
        if not resolved.cards:
            # No meetings to read — answer deterministically, spend nothing.
            yield sse(QuickChatAnswerEvent(
                text=EMPTY_SCOPE_ANSWER, referenced_meetings=[], meeting_count=0,
            ))
            return

        yield sse(StepEvent(label=QUICK_CHAT_INITIAL_STEP_LABEL))
        try:
            for update in quick_chat_graph.stream(graph_input, config=config, stream_mode="updates"):
                agent_update = update.get("agent")
                if agent_update:
                    for message in agent_update.get("messages", []):
                        if not isinstance(message, AIMessage):
                            continue
                        if message.tool_calls:
                            for tool_call in message.tool_calls:
                                label = QUICK_CHAT_TOOL_STEP_LABELS.get(
                                    tool_call.get("name", ""), QUICK_CHAT_FALLBACK_STEP_LABEL
                                )
                                yield sse(StepEvent(label=label))
                        else:
                            yield sse(StepEvent(label=QUICK_CHAT_SYNTHESIS_STEP_LABEL))
                synthesis_update = update.get("synthesize")
                if synthesis_update:
                    for message in synthesis_update.get("messages", []):
                        if not isinstance(message, AIMessage):
                            continue
                        text, referenced = resolve_markers(message_text(message), cards_by_id)
                        yield sse(QuickChatAnswerEvent(
                            text=text,
                            referenced_meetings=referenced,
                            meeting_count=len(resolved.cards),
                        ))
        except Exception as exc:
            logger.exception("Quick chat stream failed fingerprint=%s", resolved.fingerprint)
            detail = str(exc) if isinstance(exc, RuntimeError) else "Could not complete the response."
            yield sse(ErrorEvent(detail=detail))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
