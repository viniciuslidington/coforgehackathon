"""The bound that keeps an agent's tool loop from running to the step limit.

Both chat graphs loop agent -> tools -> agent for as long as the model asks for
tools. Without a bound a model that never stops asking exhausts LangGraph's
recursion limit, and the user gets a GraphRecursionError where an answer
belonged. These tests pin the bound and the message repair that follows it.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graphs.meeting_chat.graph import (
    MEETING_CHAT_RECURSION_LIMIT,
    _route_after_agent as route_meeting_chat,
)
from app.graphs.quick_chat.graph import (
    QUICK_CHAT_RECURSION_LIMIT,
    _route_after_agent as route_quick_chat,
)
from app.graphs.tool_budget import (
    MAX_TOOL_ROUNDS,
    route_after_agent,
    tool_rounds_this_turn,
    without_pending_tool_calls,
)


def _round(index: int) -> list:
    """One agent tool request and its result."""
    call_id = f"call-{index}"
    return [
        AIMessage(content="", tool_calls=[{"name": "search_scope", "args": {}, "id": call_id}]),
        ToolMessage(content="[]", tool_call_id=call_id),
    ]


def _turn(rounds: int) -> list:
    """A question the agent has answered with `rounds` tool requests.

    The earlier requests have their results; the latest is still pending, which
    is the state the router sees when it decides whether to run tools again.
    """
    messages = [HumanMessage(content="What happened?")]
    for index in range(rounds - 1):
        messages.extend(_round(index))
    messages.append(
        AIMessage(content="", tool_calls=[{"name": "search_scope", "args": {}, "id": "pending"}])
    )
    return messages


def test_an_answer_without_tool_calls_goes_straight_to_synthesis() -> None:
    messages = [HumanMessage(content="What happened?"), AIMessage(content="Nothing did.")]

    assert route_after_agent(messages) == "synthesize"


def test_the_agent_keeps_its_tools_while_inside_the_budget() -> None:
    messages = _turn(MAX_TOOL_ROUNDS - 1)

    assert route_after_agent(messages) == "tools"


def test_a_runaway_loop_is_sent_to_synthesis_rather_than_raising() -> None:
    """The whole point: the turn ends in an answer, not GraphRecursionError."""
    messages = _turn(MAX_TOOL_ROUNDS)

    assert route_after_agent(messages) == "synthesize"


def test_both_graphs_apply_the_same_bound() -> None:
    messages = _turn(MAX_TOOL_ROUNDS)

    assert route_quick_chat({"messages": messages}) == "synthesize"
    assert route_meeting_chat({"messages": messages}) == "synthesize"


def test_the_budget_is_per_question_not_per_session() -> None:
    """`messages` is checkpointed, so a running total would starve later turns."""
    spent = [*_turn(MAX_TOOL_ROUNDS), AIMessage(content="Here is the answer.")]
    next_turn = [*spent, *_turn(1)]

    assert tool_rounds_this_turn(next_turn) == 1
    assert route_after_agent(next_turn) == "tools"


def test_the_recursion_limit_leaves_room_for_a_full_budget() -> None:
    """LangGraph's limit is the backstop, never the thing that ends a turn.

    A round is two super-steps, plus the entry agent step and synthesize.
    """
    steps_needed = 2 * MAX_TOOL_ROUNDS + 2

    assert QUICK_CHAT_RECURSION_LIMIT > steps_needed
    assert MEETING_CHAT_RECURSION_LIMIT > steps_needed


def test_a_cut_off_draft_loses_its_unanswered_tool_calls() -> None:
    """Providers reject a tool call with no matching result."""
    messages = [
        HumanMessage(content="What happened?"),
        *_round(0),
        AIMessage(
            content="Still looking",
            id="draft-1",
            tool_calls=[{"name": "search_scope", "args": {}, "id": "call-orphan"}],
        ),
    ]

    repaired = without_pending_tool_calls(messages)

    assert repaired[-1].tool_calls == []
    assert repaired[-1].content == "Still looking"
    # The id carries over so add_messages still replaces the draft in state.
    assert repaired[-1].id == "draft-1"
    # Everything gathered before the cut survives, so the answer stays grounded.
    assert [type(message) for message in repaired[:-1]] == [type(m) for m in messages[:-1]]


def test_an_ordinary_history_passes_through_untouched() -> None:
    messages = [HumanMessage(content="What happened?"), AIMessage(content="This did.")]

    assert without_pending_tool_calls(messages) == messages


class NeverStopsCallingTools:
    """The failure mode this bound exists for: a model that always asks again."""

    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(
            content="",
            tool_calls=[{
                "name": "search_transcript_keyword",
                "args": {"term": "receita"},
                "id": f"call-{self.calls}",
                "type": "tool_call",
            }],
        )


def test_a_model_that_never_stops_still_produces_an_answer(monkeypatch) -> None:
    """End to end: the graph terminates instead of raising GraphRecursionError."""
    from app.graphs.meeting_chat.graph import build_chat_graph

    model = NeverStopsCallingTools()
    monkeypatch.setattr("app.graphs.meeting_chat.nodes.get_model", lambda **_kwargs: model)
    graph = build_chat_graph()

    updates = list(graph.stream(
        {
            "meeting_id": "meeting-1",
            "transcript": "[00:00:01.000–00:00:04.000] Ana: A receita cresceu 12%.",
            "captions": [{
                "start": "00:00:01.000",
                "end": "00:00:04.000",
                "text": "Ana: A receita cresceu 12%.",
            }],
            "metadata": {"participants": ["Ana"]},
            "messages": [HumanMessage(content="Qual foi a receita?")],
        },
        config={"recursion_limit": MEETING_CHAT_RECURSION_LIMIT},
        stream_mode="updates",
    ))

    nodes = [next(iter(update)) for update in updates]
    assert nodes[-1] == "synthesize"
    assert nodes.count("tools") == MAX_TOOL_ROUNDS - 1
    # The synthesis call is the last one, and it sees no unanswered tool call.
    assert isinstance(updates[-1]["synthesize"]["messages"][0], AIMessage)
