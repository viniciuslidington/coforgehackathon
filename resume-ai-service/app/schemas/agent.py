from __future__ import annotations

from pydantic import BaseModel, Field

class MeetingResponse(BaseModel):
    result: str
    caption_count: int

class QuestionRequest(BaseModel):
    question: str = Field(min_length=2)
