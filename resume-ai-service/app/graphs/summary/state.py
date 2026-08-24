from __future__ import annotations

from typing import Literal, TypedDict

Mode = Literal["simple", "detailed"]

class SummaryState(TypedDict, total=False):
    transcript: str
    mode: Mode
    focus_points: list[str]
    result: str

class OverviewState(TypedDict, total=False):
    transcript: str
    title: str
    simple_summary: str
    keywords: list[str]
