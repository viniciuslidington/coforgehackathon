from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

class MeetingResponse(BaseModel):
    result: str
    caption_count: int

class QuestionRequest(BaseModel):
    question: str = Field(min_length=2)
    session_id: str = Field(min_length=8, max_length=128)

class StepEvent(BaseModel):
    type: Literal["step"] = "step"
    label: str

class AnswerEvent(BaseModel):
    type: Literal["answer"] = "answer"
    text: str
    caption_count: int

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    detail: str
