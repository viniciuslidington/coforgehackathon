"""Small, dependency-free WebVTT parser used before passing text to agents."""
from __future__ import annotations
import re
from dataclasses import dataclass

TIMING_LINE = re.compile(r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})")
TAG = re.compile(r"<[^>]+>")

@dataclass(frozen=True)
class Caption:
    start: str
    end: str
    text: str

def timestamp_seconds(timestamp: str) -> float:
    hours, minutes, seconds = timestamp.split(":")
    whole_seconds, milliseconds = seconds.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(whole_seconds) + int(milliseconds) / 1000

def parse_vtt(raw_vtt: str) -> list[Caption]:
    """Extract time-stamped spoken captions, rejecting malformed uploads."""
    normalized = raw_vtt.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("WEBVTT"):
        raise ValueError("The uploaded file is not a WebVTT document (missing WEBVTT header).")
    captions: list[Caption] = []
    for block in re.split(r"\n\s*\n", normalized)[1:]:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING_LINE.search(lines[timing_index])
        if not match:
            continue
        text = TAG.sub("", " ".join(lines[timing_index + 1:])).strip()
        if text:
            captions.append(Caption(start=match.group("start"), end=match.group("end"), text=text))
    if not captions:
        raise ValueError("No spoken captions were found in this WebVTT file.")
    return captions

def transcript_from_captions(captions: list[Caption]) -> str:
    return "\n".join(f"[{cue.start}–{cue.end}] {cue.text}" for cue in captions)

def duration_seconds(captions: list[Caption]) -> int:
    """Return the elapsed duration from the first cue start to the last cue end."""
    return max(0, round(timestamp_seconds(captions[-1].end) - timestamp_seconds(captions[0].start)))
