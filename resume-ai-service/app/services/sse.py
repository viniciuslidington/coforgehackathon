"""Server-sent event framing shared by every streaming router.

The wire format is deliberately minimal: bare `data: {json}\\n\\n` frames with
no `event:`, `id:`, or heartbeat lines. The frontend parser in
`src/shared/api/sse.ts` depends on exactly this shape, so both the meeting
chat and quick chat routers frame through here rather than each rolling their
own — otherwise the two can silently drift apart.
"""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from pydantic import BaseModel


def sse(event: BaseModel) -> str:
    """Frame one pydantic event as a single SSE `data:` message."""
    return f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"


def message_text(message: AIMessage) -> str:
    """Flatten an AI message's content to plain text.

    Providers may return either a bare string or a list of content parts;
    only the `text` parts carry the answer.
    """
    if isinstance(message.content, str):
        return message.content
    pieces = [
        str(part.get("text", ""))
        for part in message.content
        if isinstance(part, dict) and part.get("type") == "text"
    ]
    return "".join(pieces)
