from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.vtt import Caption
from app.graphs.meeting_chat import context as context_module
from app.graphs.meeting_chat.context import build_meeting_context
from app.graphs.meeting_chat.graph import build_chat_graph
from app.graphs.meeting_chat.nodes import run_agent, synthesize_answer
from app.graphs.meeting_chat.prompts import EXCERPTS_CONTEXT_RULE, FINAL_ANSWER_REQUEST
from app.graphs.meeting_chat.state import ChatState
from app.graphs.meeting_chat.tools import (
    get_geopolitical_analysis,
    get_market_quote,
    read_transcript_around,
    search_meeting,
    search_transcript_keyword,
)
from app.main import app
from app.services import finnhub_service, transcript_index
from app.services.transcript_index import index_meeting


class HistoryAwareModel:
    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        questions = [
            message for message in messages
            if isinstance(message, HumanMessage)
            and message.content != FINAL_ANSWER_REQUEST
        ]
        return AIMessage(content=f"questions={len(questions)}")


class ToolCallingModel:
    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        if not any(isinstance(message, ToolMessage) for message in messages):
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "search_transcript_keyword",
                    "args": {"term": "receita"},
                    "id": "call-1",
                    "type": "tool_call",
                }],
            )
        tool_result = next(message for message in messages if isinstance(message, ToolMessage))
        payload = json.loads(tool_result.content)
        return AIMessage(content=f"matches={payload['total']}")


class ExternalFailureAwareModel:
    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        if not tool_messages:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "get_market_quote",
                    "args": {"ticker": "AAPL"},
                    "id": "call-quote",
                    "type": "tool_call",
                }],
            )
        payload = json.loads(tool_messages[-1].content)
        assert payload["ok"] is False
        return AIMessage(content="A reunião menciona a Apple, mas o dado externo não pôde ser obtido.")


class ReasoningDraftModel:
    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return AIMessage(content="Preciso analisar os dados e então elaborar a resposta.")


class FinalAnswerModel:
    def invoke(self, messages):
        assert any(
            isinstance(message, AIMessage) and "Preciso analisar os dados" in message.content
            for message in messages
        )
        return AIMessage(content="Ana informou que a receita cresceu 12% [00:00:01].")


def _graph_input(question: str) -> dict[str, object]:
    return {
        "meeting_id": "meeting-1",
        "transcript": "[00:00:01.000–00:00:04.000] Ana: A receita cresceu 12%.",
        "captions": [{
            "start": "00:00:01.000",
            "end": "00:00:04.000",
            "text": "Ana: A receita cresceu 12%.",
        }],
        "metadata": {"participants": ["Ana"]},
        "messages": [HumanMessage(content=question)],
    }


def test_deterministic_tool_reads_injected_meeting_state():
    workflow = StateGraph(ChatState)
    workflow.add_node("tools", ToolNode([search_transcript_keyword]))
    workflow.add_edge(START, "tools")
    graph = workflow.compile()
    result = graph.invoke({
        **_graph_input("Qual foi a receita?"),
        "messages": [AIMessage(
            content="",
            tool_calls=[{
                "name": "search_transcript_keyword",
                "args": {"term": "RECEITA"},
                "id": "call-1",
                "type": "tool_call",
            }],
        )],
    })

    payload = json.loads(result["messages"][-1].content)
    assert payload["total"] == 1
    assert payload["matches"][0]["start"] == "00:00:01.000"


def test_graph_cycles_through_tool_before_final_answer(monkeypatch):
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: ToolCallingModel())
    graph = build_chat_graph()

    updates = list(graph.stream(_graph_input("Qual foi a receita?"), stream_mode="updates"))

    assert [next(iter(update)) for update in updates] == [
        "agent",
        "tools",
        "agent",
        "synthesize",
    ]
    assert updates[-1]["synthesize"]["messages"][0].content == "matches=1"


def test_graph_synthesizes_reasoning_draft_into_a_final_answer(monkeypatch):
    models = iter([ReasoningDraftModel(), FinalAnswerModel()])
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: next(models))
    graph = build_chat_graph()

    updates = list(graph.stream(_graph_input("Qual foi a receita?"), stream_mode="updates"))

    assert [next(iter(update)) for update in updates] == ["agent", "synthesize"]
    assert updates[-1]["synthesize"]["messages"][0].content == (
        "Ana informou que a receita cresceu 12% [00:00:01]."
    )


def test_sqlite_checkpointer_restores_history_after_graph_is_recreated(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: HistoryAwareModel())
    checkpoint_path = tmp_path / "chat.db"
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        first_graph = build_chat_graph(saver)
        first = first_graph.invoke(_graph_input("Primeira pergunta"), config=config)
        assert first["messages"][-1].content == "questions=1"
        assert len([message for message in first["messages"] if isinstance(message, AIMessage)]) == 1

    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        restarted_graph = build_chat_graph(saver)
        second = restarted_graph.invoke(_graph_input("E sobre isso?"), config=config)
        assert second["messages"][-1].content == "questions=2"
        assert len([message for message in second["messages"] if isinstance(message, AIMessage)]) == 2


def test_finnhub_search_uses_normalized_ttl_cache(monkeypatch):
    finnhub_service.clear_cache()
    monkeypatch.setattr(finnhub_service, "FINNHUB_API_KEY", "test-key")
    calls = 0

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": [{"symbol": "AAPL", "description": "Apple Inc"}]}

    def fake_get(_path, **_kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr(finnhub_service._client, "get", fake_get)

    assert finnhub_service.search_symbol(" Apple Inc ") == "AAPL"
    assert finnhub_service.search_symbol("apple   inc") == "AAPL"
    assert calls == 1


def test_finnhub_quote_cache_prevents_repeated_market_requests(monkeypatch):
    finnhub_service.clear_cache()
    monkeypatch.setattr(finnhub_service, "FINNHUB_API_KEY", "test-key")
    calls = 0

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"c": 200.0, "d": 1.0, "dp": 0.5, "t": 1_787_600_000}

    def fake_get(_path, **_kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr(finnhub_service._client, "get", fake_get)

    assert finnhub_service.get_quote("AAPL")["current_price"] == 200.0
    assert finnhub_service.get_quote(" aapl ")["current_price"] == 200.0
    assert calls == 1


def test_external_tool_returns_structured_failure_on_timeout(monkeypatch):
    monkeypatch.setattr(
        finnhub_service,
        "get_quote",
        lambda _ticker: (_ for _ in ()).throw(
            finnhub_service.FinnhubTimeoutError("late")
        ),
    )

    result = get_market_quote.invoke({"ticker": "AAPL"})

    assert result["ok"] is False
    assert result["source"] == "Finnhub"
    assert "timed out" in result["reason"]


def test_finnhub_failure_does_not_break_the_agent_answer(monkeypatch):
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: ExternalFailureAwareModel())
    monkeypatch.setattr(
        finnhub_service,
        "get_quote",
        lambda _ticker: (_ for _ in ()).throw(
            finnhub_service.FinnhubTimeoutError("late")
        ),
    )
    graph = build_chat_graph()

    result = graph.invoke(_graph_input("E a cotação atual da Apple?"))

    assert "dado externo não pôde ser obtido" in result["messages"][-1].content


def test_geopolitical_tool_uses_a_dedicated_news_only_model_call(monkeypatch):
    article = {
        "headline": "Shipping disruption",
        "summary": "A route was temporarily disrupted.",
        "source": "Reuters",
        "url": "https://example.test/article",
        "published_at": "2026-08-24T10:00:00+00:00",
    }
    monkeypatch.setattr(finnhub_service, "get_news", lambda _topic: [article])

    class DedicatedModel:
        def invoke(self, messages):
            assert len(messages) == 2
            assert "Shipping disruption" in messages[1].content
            return AIMessage(content="Análise ancorada na notícia.")

    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: DedicatedModel())

    result = get_geopolitical_analysis.invoke({"asset_or_topic": "shipping"})

    assert result["ok"] is True
    assert result["analysis"] == "Análise ancorada na notícia."
    assert result["articles"] == [article]


def test_meeting_question_endpoint_streams_step_tool_and_answer(monkeypatch):
    captions = [Caption(
        start="00:00:01.000",
        end="00:00:04.000",
        text="Ana: A receita cresceu 12%.",
    )]
    monkeypatch.setattr(
        "app.routers.meeting_summaries.transcript_repository.get_captions",
        lambda _meeting_id: captions,
    )
    monkeypatch.setattr(
        "app.routers.meeting_summaries.get_summary",
        lambda _meeting_id: {
            "title": "Resultados",
            "meeting_date": "2026-08-24",
            "participants": "Ana",
            "keywords": "receita",
            "duration_seconds": 3,
        },
    )

    class FakeGraph:
        def stream(self, _input, config, stream_mode):
            assert config["configurable"]["thread_id"] == "session-123"
            assert stream_mode == "updates"
            yield {"agent": {"messages": [AIMessage(
                content="",
                tool_calls=[{
                    "name": "search_transcript_keyword",
                    "args": {"term": "receita"},
                    "id": "call-1",
                    "type": "tool_call",
                }],
            )]}}
            yield {"tools": {"messages": []}}
            yield {"agent": {"messages": [AIMessage(content="Preciso formular a resposta.")]}}
            yield {"synthesize": {"messages": [AIMessage(
                content="Ana disse que cresceu 12% [00:00:01].",
            )]}}

    monkeypatch.setattr("app.routers.meeting_summaries.chat_graph", FakeGraph())
    response = TestClient(app).post(
        "/meeting-summaries/meeting-1/questions",
        json={"question": "Qual foi a receita?", "session_id": "session-123"},
    )

    assert response.status_code == 200
    events = [
        json.loads(frame.removeprefix("data: "))
        for frame in response.text.strip().split("\n\n")
    ]
    assert [event["type"] for event in events] == ["step", "step", "step", "answer"]
    assert "quote" in events[1]["label"]
    assert events[-1]["caption_count"] == 1


def test_meeting_question_endpoint_only_emits_synthesized_answer(monkeypatch):
    captions = [Caption(
        start="00:00:01.000",
        end="00:00:04.000",
        text="Ana: A receita cresceu 12%.",
    )]
    monkeypatch.setattr(
        "app.routers.meeting_summaries.transcript_repository.get_captions",
        lambda _meeting_id: captions,
    )
    monkeypatch.setattr("app.routers.meeting_summaries.get_summary", lambda _meeting_id: {})

    class FakeGraph:
        def stream(self, _input, config, stream_mode):
            yield {"agent": {"messages": [AIMessage(
                content="Preciso analisar os dados e formular a resposta.",
            )]}}
            yield {"synthesize": {"messages": [AIMessage(
                content="Ana informou crescimento de 12% [00:00:01].",
            )]}}

    monkeypatch.setattr("app.routers.meeting_summaries.chat_graph", FakeGraph())
    response = TestClient(app).post(
        "/meeting-summaries/meeting-1/questions",
        json={"question": "Qual foi a receita?", "session_id": "session-456"},
    )
    events = [
        json.loads(frame.removeprefix("data: "))
        for frame in response.text.strip().split("\n\n")
    ]
    answers = [event for event in events if event["type"] == "answer"]

    assert len(answers) == 1
    assert answers[0]["text"] == "Ana informou crescimento de 12% [00:00:01]."


LONG_MEETING = [
    Caption(start=f"00:{minute:02d}:00.000", end=f"00:{minute:02d}:30.000", text=text)
    for minute, text in enumerate(
        ["Ana: Good morning, this is the rates huddle."]
        + [f"Bo: Filler update number {n} about desk logistics and seating." for n in range(40)]
        + ["Cy: Treasuries sold off and yields are up ten basis points."]
        + [f"Bo: More filler {n} on the coffee machine schedule." for n in range(15)]
    )
]


class PromptRecordingModel:
    def __init__(self):
        self.system_prompts: list[str] = []

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        self.system_prompts.append(str(messages[0].content))
        return AIMessage(content="ok")


def test_a_short_meeting_is_sent_whole():
    context = build_meeting_context("m1", LONG_MEETING[:3], "anything")

    assert "rates huddle" in context.transcript
    assert context.excerpts == ""


def test_a_long_meeting_is_sent_as_its_opening_and_relevant_passages(db_path, fake_embedder, monkeypatch):
    monkeypatch.setattr(context_module, "INLINE_TRANSCRIPT_CHARS", 500)
    monkeypatch.setattr(transcript_index.transcript_repository, "get_captions", lambda _id: LONG_MEETING)

    context = build_meeting_context("m1", LONG_MEETING, "What happened to bond yields?")

    assert context.transcript == ""
    assert "rates huddle" in context.opening
    assert "Treasuries sold off" in context.excerpts
    assert "coffee machine" not in context.opening


def test_a_long_meeting_without_an_index_falls_back_to_the_whole_meeting(db_path, monkeypatch):
    monkeypatch.setattr(context_module, "INLINE_TRANSCRIPT_CHARS", 500)
    monkeypatch.setattr(transcript_index.transcript_repository, "get_captions", lambda _id: None)

    context = build_meeting_context("m1", LONG_MEETING, "yields?")

    assert "Treasuries sold off" in context.transcript


def test_agent_and_synthesis_read_excerpts_instead_of_the_full_meeting(monkeypatch):
    model = PromptRecordingModel()
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: model)
    state = {
        "meeting_id": "m1",
        "transcript": "",
        "opening": "[00:00:00.000–00:00:30.000] Ana: Good morning.",
        "excerpts": "[00:41:00.000–00:41:30.000] Cy: Treasuries sold off.",
        "messages": [HumanMessage(content="What happened to yields?")],
    }

    run_agent(state)
    synthesize_answer({**state, "messages": [*state["messages"], AIMessage(content="draft", id="d1")]})

    agent_prompt, synthesis_prompt = model.system_prompts
    assert EXCERPTS_CONTEXT_RULE in agent_prompt
    assert "Treasuries sold off" in agent_prompt
    assert "Full meeting content" not in agent_prompt
    assert "Treasuries sold off" in synthesis_prompt
    assert EXCERPTS_CONTEXT_RULE not in synthesis_prompt


def test_search_meeting_finds_a_paraphrase_inside_the_current_meeting(db_path, fake_embedder):
    index_meeting("m1", LONG_MEETING)
    index_meeting("other", [Caption(start="00:00:01.000", end="00:00:02.000", text="Di: yields yields yields")])

    result = search_meeting.invoke({"query": "duration", "state": {"meeting_id": "m1"}})

    assert result["ok"] is True
    assert any("Treasuries sold off" in passage["excerpt"] for passage in result["passages"])
    assert all("Di:" not in passage["excerpt"] for passage in result["passages"])


def test_read_transcript_around_returns_the_neighbourhood_of_a_moment(db_path, fake_embedder):
    index_meeting("m1", LONG_MEETING)

    result = read_transcript_around.invoke({"start": "00:41:00.000", "state": {"meeting_id": "m1"}})

    assert result["ok"] is True
    assert "Treasuries sold off" in result["excerpt"]
