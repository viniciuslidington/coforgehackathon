"""Quick Chat agent: scope containment in tools, and session memory."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from app.graphs.quick_chat import nodes as nodes_module
from app.graphs.quick_chat.graph import build_quick_chat_graph, thread_id_for
from app.graphs.quick_chat.tools import (
    get_meeting_summaries,
    get_meeting_transcript,
    search_meeting_transcript,
    search_scope,
)

STATE = {
    "meeting_ids": ["in-scope"],
    "catalog": [
        {
            "meeting_id": "in-scope",
            "title": "EUR/USD block",
            "meeting_date": "2026-08-27",
            "keywords": ["eurusd"],
            "participants": ["Alex"],
        }
    ],
    "summaries": {"in-scope": "Alex flagged an unanswered EUR/USD block."},
    "embeddings": {},
}


def _invoke(tool, **kwargs):
    return tool.invoke({**kwargs, "state": STATE})


def test_transcript_tool_refuses_an_out_of_scope_meeting(monkeypatch) -> None:
    """Scope is enforced in code, so a hallucinated id cannot reach storage."""
    def explode(_meeting_id):  # pragma: no cover - must never be called
        raise AssertionError("the repository was consulted for an out-of-scope meeting")

    monkeypatch.setattr(
        "app.graphs.quick_chat.tools.transcript_repository.get_captions", explode
    )

    result = _invoke(get_meeting_transcript, meeting_id="other")

    assert result["ok"] is False
    assert result["invalid_ids"] == ["other"]


def test_transcript_search_refuses_an_out_of_scope_meeting(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.graphs.quick_chat.tools.transcript_repository.get_captions",
        lambda _id: (_ for _ in ()).throw(AssertionError("should not be reached")),
    )

    result = _invoke(search_meeting_transcript, meeting_id="other", term="block")

    assert result["ok"] is False


def test_summary_tool_rejects_a_mix_of_valid_and_invalid_ids() -> None:
    result = _invoke(get_meeting_summaries, meeting_ids=["in-scope", "ghost"])

    assert result["ok"] is False
    assert result["invalid_ids"] == ["ghost"]


def test_summary_tool_returns_in_scope_meetings() -> None:
    result = _invoke(get_meeting_summaries, meeting_ids=["in-scope"])

    assert result["ok"] is True
    assert result["meetings"][0]["summary"].startswith("Alex flagged")


def test_search_never_returns_a_meeting_outside_the_scope() -> None:
    result = _invoke(search_scope, query="EUR/USD")

    assert result["ok"] is True
    assert {match["meeting_id"] for match in result["matches"]} <= {"in-scope"}


def test_search_rejects_an_empty_query() -> None:
    assert _invoke(search_scope, query="   ")["ok"] is False


class RecordingModel:
    """Records the user questions visible in history on each agent call.

    Only the `agent` node's view is recorded: the `synthesize` node appends
    its own instruction as a HumanMessage, which is not a user turn.
    """

    def __init__(self) -> None:
        self.seen: list[list[str]] = []
        self._binding = False

    def bind_tools(self, _tools):
        self._binding = True
        return self

    def invoke(self, messages):
        questions = [
            str(message.content)
            for message in messages
            if isinstance(message, HumanMessage)
            and not str(message.content).startswith("Now synthesize")
        ]
        if self._binding:
            self.seen.append(questions)
            self._binding = False
        return AIMessage(content=f"answered: {questions[-1] if questions else ''}")


def _graph_input(question: str) -> dict:
    return {
        "meeting_ids": ["in-scope"],
        "catalog": STATE["catalog"],
        "summaries": STATE["summaries"],
        "embeddings": {},
        "messages": [HumanMessage(content=question)],
    }


def test_graph_reaches_synthesis_without_tool_calls(monkeypatch, db_path: Path) -> None:
    monkeypatch.setattr(nodes_module, "get_model", lambda **_kwargs: RecordingModel())
    graph = build_quick_chat_graph()

    visited = [
        node
        for update in graph.stream(_graph_input("What happened?"), stream_mode="updates")
        for node in update
    ]

    assert visited == ["agent", "synthesize"]


def test_session_memory_persists_across_graph_recreation(monkeypatch, tmp_path: Path) -> None:
    """A reconstructed graph must still see the earlier turns of the session."""
    model = RecordingModel()
    monkeypatch.setattr(nodes_module, "get_model", lambda **_kwargs: model)
    checkpoint_path = tmp_path / "quick-chat.db"
    config = {"configurable": {"thread_id": thread_id_for(str(uuid4()))}}

    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        build_quick_chat_graph(saver).invoke(_graph_input("First"), config=config)
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        build_quick_chat_graph(saver).invoke(_graph_input("Second"), config=config)

    # Turn two's agent saw turn one's question, so the session remembered it.
    assert model.seen == [["First"], ["First", "Second"]]


def test_a_different_session_does_not_inherit_history(monkeypatch, tmp_path: Path) -> None:
    model = RecordingModel()
    monkeypatch.setattr(nodes_module, "get_model", lambda **_kwargs: model)
    checkpoint_path = tmp_path / "quick-chat.db"

    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        graph = build_quick_chat_graph(saver)
        graph.invoke(_graph_input("First"), config={
            "configurable": {"thread_id": thread_id_for("session-one")}})
        graph.invoke(_graph_input("Second"), config={
            "configurable": {"thread_id": thread_id_for("session-two")}})

    assert model.seen == [["First"], ["Second"]]


def test_thread_ids_are_namespaced_away_from_meeting_chat() -> None:
    session = "11111111-1111-1111-1111-111111111111"

    assert thread_id_for(session) == f"quick-chat:{session}"
    assert thread_id_for(session) != session
