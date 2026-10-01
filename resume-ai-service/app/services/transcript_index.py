"""Chunking and embedding of transcripts for retrieval.

A meeting is cut into short windows of consecutive captions. Each window keeps
real cue bounds, so anything retrieved from it can be cited with a timestamp
the transcript actually has. Windows are kept short because the local
embedding model truncates its input at 128 tokens: a longer chunk would only
be embedded in part.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.vtt import Caption, transcript_from_captions
from app.services import database, priority
from app.services.transcripts import transcript_repository

logger = logging.getLogger("meeting-insights")

# Bump whenever chunking or the embedding model changes: every meeting indexed
# under another version is re-indexed on the next sync or lookup.
CHUNKER_VERSION = "chunks-v1"
MAX_CHUNK_WORDS = 90


@dataclass(frozen=True)
class Chunk:
    index: int
    start: str
    end: str
    speakers: list[str]
    text: str
    transcript: str


def _speaker(caption: Caption) -> str | None:
    name, separator, _ = caption.text.partition(":")
    return name.strip() if separator and name.strip() else None


def chunk_captions(captions: list[Caption]) -> list[Chunk]:
    """Group consecutive captions into windows of at most MAX_CHUNK_WORDS.

    A caption is never split, so one longer than the limit becomes a chunk on
    its own. Consecutive windows share one caption, so a statement that sits
    on a boundary is still retrievable with its lead-in.
    """
    windows: list[list[Caption]] = []
    current: list[Caption] = []
    words = 0
    for caption in captions:
        caption_words = len(caption.text.split())
        if current and words + caption_words > MAX_CHUNK_WORDS:
            windows.append(current)
            # Carry the last caption over as overlap, unless it alone would
            # already fill the next window.
            overlap = current[-1]
            overlap_words = len(overlap.text.split())
            if len(current) > 1 and overlap_words + caption_words <= MAX_CHUNK_WORDS:
                current, words = [overlap], overlap_words
            else:
                current, words = [], 0
        current.append(caption)
        words += caption_words
    if current:
        windows.append(current)

    chunks: list[Chunk] = []
    for index, window in enumerate(windows):
        speakers: list[str] = []
        for caption in window:
            name = _speaker(caption)
            if name and name not in speakers:
                speakers.append(name)
        chunks.append(Chunk(
            index=index,
            start=window[0].start,
            end=window[-1].end,
            speakers=speakers,
            text="\n".join(caption.text for caption in window),
            transcript=transcript_from_captions(window),
        ))
    return chunks


def index_meeting(meeting_id: str, captions: list[Caption]) -> int:
    """(Re)build a meeting's chunk index. Idempotent; returns the chunk count."""
    chunks = chunk_captions(captions)
    vectors = priority.embed_passages([chunk.text for chunk in chunks])
    database.replace_chunks(meeting_id, [
        {
            "chunk_index": chunk.index,
            "start": chunk.start,
            "end": chunk.end,
            "speakers": ", ".join(chunk.speakers),
            "text": chunk.text,
            "transcript": chunk.transcript,
            "embedding": priority.vector_to_blob(vector),
            "chunker_version": CHUNKER_VERSION,
        }
        for chunk, vector in zip(chunks, vectors)
    ])
    return len(chunks)


def is_indexed(meeting_id: str) -> bool:
    return database.chunk_index_version(meeting_id) == CHUNKER_VERSION


def ensure_scope_indexed(meeting_ids: list[str], *, budget: int = 5) -> list[str]:
    """Index up to `budget` unindexed meetings now; return those still missing.

    Bounded so a question over a large, never-indexed scope cannot stall on
    fetching and embedding dozens of transcripts. Whatever is left is
    reported back so the caller can say its search was partial.
    """
    indexed = database.indexed_meeting_ids(CHUNKER_VERSION)
    missing = [mid for mid in meeting_ids if mid not in indexed]
    for meeting_id in missing[:budget]:
        ensure_indexed(meeting_id)
    if not missing:
        return []
    indexed = database.indexed_meeting_ids(CHUNKER_VERSION)
    return [mid for mid in missing if mid not in indexed]


def ensure_indexed(meeting_id: str) -> bool:
    """Index a meeting on demand when sync never did. True when it is indexed.

    The safety net for meetings that slipped past sync and the backfill, e.g.
    because their transcript could not be fetched at the time.
    """
    if is_indexed(meeting_id):
        return True
    captions = transcript_repository.get_captions(meeting_id)
    if captions is None:
        return False
    try:
        index_meeting(meeting_id, captions)
    except Exception:
        logger.exception("Could not index transcript for meeting %s", meeting_id)
        return False
    return True
