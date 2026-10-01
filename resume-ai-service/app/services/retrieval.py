"""Hybrid lexical + semantic retrieval over the transcript chunk index.

Two rankers run over the chunks of the allowed meetings: SQLite FTS5 (bm25,
trigram tokens) for literal mentions, and cosine similarity against the local
embedding model for paraphrases. They are merged with Reciprocal Rank Fusion,
which needs no calibration between a bm25 score and a cosine.

Every entry point takes an explicit allow-list of meeting ids. Nothing here
can return a chunk from a meeting the caller did not pass in.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Hashable, Sequence, TypeVar

import numpy as np

from app.services import database, priority

logger = logging.getLogger("meeting-insights")

# Standard RRF damping constant: high enough that rank 1 vs rank 2 in one list
# does not outweigh agreement between both lists.
RRF_K = 60
CANDIDATES_PER_RANKER = 50
MAX_CHUNKS_PER_MEETING = 3
# Shorter query terms match far too much as trigram substrings ("the" is in
# "other"), so on their own they only count as part of the full phrase.
MIN_TERM_LENGTH = 4
# The trigram tokenizer cannot match anything shorter than three characters.
MIN_FTS_LENGTH = 3
SNIPPET_CHARS = 160

TRANSCRIPT_LINE = re.compile(r"^\[(?P<start>[^–\]]+)–(?P<end>[^\]]+)\]\s?(?P<text>.*)$")


@dataclass(frozen=True)
class ChunkHit:
    meeting_id: str
    chunk_index: int
    start: str
    end: str
    transcript: str
    # The full query appears literally in the chunk.
    lexical: bool
    semantic: float
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "meeting_id": self.meeting_id,
            "start": self.start,
            "end": self.end,
            "excerpt": self.transcript,
            "match": "literal" if self.lexical else "semantic",
        }


@dataclass(frozen=True)
class Moment:
    """One cue inside a meeting, cut down to a readable snippet."""
    start: str
    snippet: str


@dataclass(frozen=True)
class MeetingText:
    meeting_id: str
    title: str = ""
    summary: str = ""
    keywords: Sequence[str] = ()
    participants: Sequence[str] = ()
    topic_embedding: bytes | None = None


@dataclass
class MeetingMatch:
    meeting_id: str
    score: float = 0.0
    # Where the query appears literally: title, keywords, participants,
    # summary or transcript. None when the meeting only matched semantically.
    lexical_source: str | None = None
    semantic: float = 0.0
    moment: Moment | None = None
    best_chunk: ChunkHit | None = field(default=None, repr=False)


@dataclass(frozen=True)
class _Corpus:
    keys: list[tuple[str, int]]
    rows: list[dict[str, object]]
    # Row-normalized, so a dot product with a normalized query is a cosine.
    matrix: np.ndarray
    positions: dict[str, np.ndarray]
    by_key: dict[tuple[str, int], int]


K = TypeVar("K", bound=Hashable)

_cache: tuple[tuple[int, int], _Corpus] | None = None


def _corpus() -> _Corpus:
    """Every chunk vector, loaded once and reloaded only after an index change."""
    global _cache
    stamp = database.chunk_index_stamp()
    if _cache is not None and _cache[0] == stamp:
        return _cache[1]

    rows = database.list_all_chunks()
    keys = [(str(row["meeting_id"]), int(row["chunk_index"])) for row in rows]  # type: ignore[arg-type]
    vectors = [priority.blob_to_vector(row.pop("embedding")) for row in rows]  # type: ignore[arg-type]
    if vectors:
        matrix = np.vstack(vectors).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / np.where(norms == 0.0, 1.0, norms)
    else:
        matrix = np.zeros((0, 0), dtype=np.float32)

    grouped: dict[str, list[int]] = {}
    for position, (meeting_id, _) in enumerate(keys):
        grouped.setdefault(meeting_id, []).append(position)
    corpus = _Corpus(
        keys=keys,
        rows=rows,
        matrix=matrix,
        positions={mid: np.array(found) for mid, found in grouped.items()},
        by_key={key: position for position, key in enumerate(keys)},
    )
    _cache = (stamp, corpus)
    return corpus


def _quote(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def _match_expression(query: str) -> str:
    """The whole query as a phrase, OR each distinctive term on its own."""
    terms: list[str] = []
    for word in re.findall(r"\w[\w/.-]*", query):
        folded = word.casefold()
        if len(folded) >= MIN_TERM_LENGTH and folded != query.casefold() and folded not in terms:
            terms.append(folded)
    return " OR ".join(_quote(part) for part in [query, *terms])


def _lexical_ranking(query: str, meeting_ids: Sequence[str]) -> list[tuple[str, int]]:
    if len(query) < MIN_FTS_LENGTH:
        return database.like_search(query, meeting_ids, CANDIDATES_PER_RANKER)
    try:
        return database.fts_search(_match_expression(query), meeting_ids, CANDIDATES_PER_RANKER)
    except sqlite3.OperationalError:
        logger.warning("FTS query failed for %r; falling back to substring search", query)
        return database.like_search(query, meeting_ids, CANDIDATES_PER_RANKER)


def _query_vector(query: str) -> np.ndarray | None:
    try:
        vector = priority.embed_topic(query)
    except Exception:  # pragma: no cover - embedding model unavailable
        logger.warning("Semantic search unavailable; using literal matches only")
        return None
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else None


def _semantic_scores(
    corpus: _Corpus, query_vector: np.ndarray | None, meeting_ids: Sequence[str],
) -> dict[int, float]:
    """Cosine for every chunk of the allowed meetings, keyed by corpus position."""
    if query_vector is None or corpus.matrix.size == 0:
        return {}
    present = [corpus.positions[mid] for mid in meeting_ids if mid in corpus.positions]
    if not present:
        return {}
    positions = np.concatenate(present)
    if corpus.matrix.shape[1] != query_vector.shape[0]:
        # Chunks embedded by a different model; a re-index will fix it.
        return {}
    similarities = corpus.matrix[positions] @ query_vector
    return {int(p): float(s) for p, s in zip(positions, similarities)}


def _top(scores: dict[int, float], limit: int) -> list[int]:
    return sorted(scores, key=scores.__getitem__, reverse=True)[:limit]


def _rrf(rankings: Sequence[Sequence[K]]) -> dict[K, float]:
    fused: dict[K, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
    return fused


def _hit(corpus: _Corpus, position: int, *, lexical: bool, semantic: float, score: float) -> ChunkHit:
    row = corpus.rows[position]
    meeting_id, chunk_index = corpus.keys[position]
    return ChunkHit(
        meeting_id=meeting_id,
        chunk_index=chunk_index,
        start=str(row["start"]),
        end=str(row["end"]),
        transcript=str(row["transcript"]),
        lexical=lexical,
        semantic=round(semantic, 4),
        score=round(score, 6),
    )


def _ranked_chunks(
    query: str, meeting_ids: Sequence[str],
) -> tuple[_Corpus, list[int], list[int], dict[int, float]]:
    corpus = _corpus()
    lexical = [
        corpus.by_key[key] for key in _lexical_ranking(query, meeting_ids)
        if key in corpus.by_key
    ]
    semantic_scores = _semantic_scores(corpus, _query_vector(query), meeting_ids)
    return corpus, lexical, _top(semantic_scores, CANDIDATES_PER_RANKER), semantic_scores


def _contains(corpus: _Corpus, position: int, folded_query: str) -> bool:
    return folded_query in str(corpus.rows[position]["text"]).casefold()


def search_chunks(
    query: str,
    meeting_ids: Sequence[str],
    *,
    k: int = 8,
    per_meeting: int = MAX_CHUNKS_PER_MEETING,
) -> list[ChunkHit]:
    """The k most relevant transcript chunks among the allowed meetings.

    At most `per_meeting` chunks come from any one meeting, so one long
    meeting cannot crowd every other meeting out of the results.
    """
    needle = query.strip()
    if not needle or not meeting_ids:
        return []
    corpus, lexical, semantic, semantic_scores = _ranked_chunks(needle, meeting_ids)
    fused = _rrf([lexical, semantic])
    folded = needle.casefold()

    hits: list[ChunkHit] = []
    taken: dict[str, int] = {}
    for position in sorted(fused, key=fused.__getitem__, reverse=True):
        meeting_id = corpus.keys[position][0]
        if taken.get(meeting_id, 0) >= per_meeting:
            continue
        taken[meeting_id] = taken.get(meeting_id, 0) + 1
        hits.append(_hit(
            corpus, position,
            lexical=_contains(corpus, position, folded),
            semantic=semantic_scores.get(position, 0.0),
            score=fused[position],
        ))
        if len(hits) >= k:
            break
    return hits


def chunk_at(meeting_id: str, start: str, radius: int = 1) -> list[ChunkHit]:
    """The chunk that contains a cited moment, with `radius` neighbours each side."""
    corpus = _corpus()
    positions = corpus.positions.get(meeting_id)
    if positions is None:
        return []
    target = _seconds(start)
    if target is None:
        return []
    anchor = None
    for position in positions:
        row = corpus.rows[int(position)]
        begin, end = _seconds(str(row["start"])), _seconds(str(row["end"]))
        if begin is not None and begin <= target + 1.0 and (end is None or target <= end + 1.0):
            anchor = corpus.keys[int(position)][1]
            break
    if anchor is None:
        return []
    return [
        ChunkHit(
            meeting_id=meeting_id,
            chunk_index=int(row["chunk_index"]),  # type: ignore[arg-type]
            start=str(row["start"]),
            end=str(row["end"]),
            transcript=str(row["transcript"]),
            lexical=False,
            semantic=0.0,
            score=0.0,
        )
        for row in database.chunks_between(meeting_id, anchor - radius, anchor + radius)
    ]


GAP_MARKER = "…"


def merge_chunks(hits: Sequence[ChunkHit]) -> str:
    """Passages in meeting order, the overlap between neighbours removed and
    a gap marker wherever passages are not contiguous."""
    lines: list[str] = []
    seen: set[str] = set()
    previous: int | None = None
    for hit in sorted(hits, key=lambda hit: hit.chunk_index):
        if previous is not None and hit.chunk_index > previous + 1:
            lines.append(GAP_MARKER)
        for line in hit.transcript.splitlines():
            if line not in seen:
                seen.add(line)
                lines.append(line)
        previous = hit.chunk_index
    return "\n".join(lines)


def _seconds(raw: str) -> float | None:
    parts = raw.strip().replace(",", ".").split(":")
    if not 2 <= len(parts) <= 3:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    hours, minutes, seconds = ([0.0, *numbers] if len(parts) == 2 else numbers)
    return hours * 3600 + minutes * 60 + seconds


def moment_in(hit: ChunkHit, query: str) -> Moment:
    """The cue inside a chunk that best shows why it matched.

    The cue containing the query when there is one, otherwise the chunk's
    first cue — a semantic match has no single word to point at.
    """
    folded = query.strip().casefold()
    lines = [TRANSCRIPT_LINE.match(line) for line in hit.transcript.splitlines()]
    cues = [line for line in lines if line]
    if not cues:
        return Moment(start=hit.start, snippet=_clip(hit.transcript, folded))
    chosen = next((cue for cue in cues if folded and folded in cue.group("text").casefold()), cues[0])
    return Moment(start=chosen.group("start"), snippet=_clip(chosen.group("text"), folded))


def _clip(text: str, folded_query: str) -> str:
    text = " ".join(text.split())
    if len(text) <= SNIPPET_CHARS:
        return text
    at = text.casefold().find(folded_query) if folded_query else -1
    if at < 0:
        return text[:SNIPPET_CHARS].rstrip() + "…"
    begin = max(0, at - SNIPPET_CHARS // 3)
    end = min(len(text), begin + SNIPPET_CHARS)
    return ("…" if begin else "") + text[begin:end].strip() + ("…" if end < len(text) else "")


def _summary_source(meeting: MeetingText, folded: str) -> str | None:
    if folded in meeting.title.casefold():
        return "title"
    if any(folded in keyword.casefold() for keyword in meeting.keywords):
        return "keywords"
    if any(folded in name.casefold() for name in meeting.participants):
        return "participants"
    if folded in meeting.summary.casefold():
        return "summary"
    return None


def rank_meetings(query: str, meetings: Sequence[MeetingText]) -> list[MeetingMatch]:
    """Rank whole meetings for a query, best first.

    Fuses four signals: a literal mention in the stored overview, overview
    similarity, and each meeting's best chunk from both transcript rankers.
    A meeting that literally mentions the query always outranks one that is
    only semantically close. The caller decides what counts as a match from
    `lexical_source` and `semantic`.
    """
    needle = query.strip()
    if not needle or not meetings:
        return []
    folded = needle.casefold()
    by_id = {meeting.meeting_id: meeting for meeting in meetings}
    meeting_ids = list(by_id)
    query_vector = _query_vector(needle)

    matches = {mid: MeetingMatch(meeting_id=mid) for mid in meeting_ids}
    summary_literal: list[str] = []
    summary_semantic: dict[str, float] = {}
    for meeting in meetings:
        source = _summary_source(meeting, folded)
        if source:
            matches[meeting.meeting_id].lexical_source = source
            summary_literal.append(meeting.meeting_id)
        if query_vector is not None and meeting.topic_embedding:
            vector = priority.blob_to_vector(meeting.topic_embedding)
            if vector.shape == query_vector.shape:
                summary_semantic[meeting.meeting_id] = priority.cosine_similarity(vector, query_vector)

    corpus, lexical, _, semantic_scores = _ranked_chunks(needle, meeting_ids)
    chunk_literal: list[str] = []
    best_literal: dict[str, int] = {}
    for position in lexical:
        meeting_id = corpus.keys[position][0]
        if meeting_id not in best_literal:
            best_literal[meeting_id] = position
            chunk_literal.append(meeting_id)
    # Over every chunk, not just the top candidates: callers filter on each
    # meeting's best similarity, so every meeting needs one.
    best_semantic: dict[str, int] = {}
    for position, similarity in semantic_scores.items():
        meeting_id = corpus.keys[position][0]
        current = best_semantic.get(meeting_id)
        if current is None or similarity > semantic_scores[current]:
            best_semantic[meeting_id] = position
    chunk_semantic = sorted(
        best_semantic, key=lambda mid: semantic_scores[best_semantic[mid]], reverse=True,
    )

    fused = _rrf([
        summary_literal,
        sorted(summary_semantic, key=summary_semantic.__getitem__, reverse=True),
        chunk_literal,
        chunk_semantic,
    ])

    for meeting_id, match in matches.items():
        match.score = round(fused.get(meeting_id, 0.0), 6)
        literal_position = best_literal.get(meeting_id)
        # A chunk only counts as a literal mention when it holds the whole
        # query, not just one of its terms.
        if literal_position is not None and not _contains(corpus, literal_position, folded):
            literal_position = None
        position = literal_position if literal_position is not None else best_semantic.get(meeting_id)
        chunk_similarity = semantic_scores.get(best_semantic[meeting_id], 0.0) if meeting_id in best_semantic else 0.0
        match.semantic = round(max(summary_semantic.get(meeting_id, 0.0), chunk_similarity), 4)
        if literal_position is not None and match.lexical_source is None:
            match.lexical_source = "transcript"
        if position is not None:
            hit = _hit(
                corpus, position,
                lexical=literal_position is not None,
                semantic=semantic_scores.get(position, 0.0),
                score=match.score,
            )
            match.best_chunk = hit
            match.moment = moment_in(hit, needle)

    return sorted(
        (match for match in matches.values() if match.score > 0.0),
        key=lambda match: (match.lexical_source is not None, match.score),
        reverse=True,
    )
