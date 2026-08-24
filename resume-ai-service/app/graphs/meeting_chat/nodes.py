from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.graphs.meeting_chat.prompts import ANSWER_QUESTION_SYSTEM_PROMPT
from app.graphs.meeting_chat.state import ChatState
from app.graphs.model import get_model

def answer_question(state: ChatState) -> ChatState:
    response = get_model().invoke([
        SystemMessage(content=ANSWER_QUESTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Meeting context:\n{state['transcript']}\n\nQuestion: {state['question']}"),
    ])
    return {"result": str(response.content)}
