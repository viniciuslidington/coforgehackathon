from __future__ import annotations

from typing import TypedDict

class ChatState(TypedDict, total=False):
    transcript: str
    question: str
    result: str
