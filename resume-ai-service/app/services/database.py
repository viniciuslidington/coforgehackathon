"""Minimal SQLite persistence for generated meeting overview rows.

Note the one deviation from this module's conventions: `meeting_summaries`
stores list columns as comma-joined text, but `quick_chat_briefings` stores
them as JSON. Key points and referenced meetings are objects, not flat
strings, so CSV cannot carry them.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator, Sequence

from app.core.config import DATABASE_PATH

BRIEFING_CACHE_LIMIT = 10

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS meeting_summaries (
        meeting_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        meeting_date TEXT NOT NULL,
        participants TEXT NOT NULL,
        simple_summary TEXT NOT NULL,
        keywords TEXT NOT NULL DEFAULT '',
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        refreshed_at TEXT NOT NULL,
        topic_embedding BLOB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quick_chat_briefings (
        fingerprint TEXT PRIMARY KEY,
        selection_json TEXT NOT NULL,
        meeting_ids TEXT NOT NULL,
        meeting_count INTEGER NOT NULL,
        range_start TEXT,
        range_end TEXT,
        summary TEXT NOT NULL,
        key_points TEXT NOT NULL,
        referenced_meetings TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used_at TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_quick_chat_briefings_last_used
        ON quick_chat_briefings(last_used_at DESC)
    """,
    # Retrieval index over transcripts. `text` is the plain spoken text that
    # is searched and embedded; `transcript` is the same span with per-cue
    # timestamps, which is what the agents read and cite from.
    """
    CREATE TABLE IF NOT EXISTS transcript_chunks (
        meeting_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        speakers TEXT NOT NULL,
        text TEXT NOT NULL,
        transcript TEXT NOT NULL,
        embedding BLOB NOT NULL,
        chunker_version TEXT NOT NULL,
        PRIMARY KEY (meeting_id, chunk_index)
    )
    """,
    # Trigram rather than unicode61: the corpus includes Mandarin and
    # Japanese, which unicode61 cannot segment, and trigram also matches
    # inside tokens ("2s10s", "JGB").
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
        text, meeting_id UNINDEXED, chunk_index UNINDEXED, tokenize='trigram'
    )
    """,
)

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # A running development server can encounter a newly created SQLite
        # file. Ensure every operation has the tables it depends on.
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(meeting_summaries)")}
        if "keywords" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN keywords TEXT NOT NULL DEFAULT ''")
        if "duration_seconds" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN duration_seconds INTEGER NOT NULL DEFAULT 0")
        if "topic_embedding" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN topic_embedding BLOB")
        briefing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(quick_chat_briefings)")}
        if "truncated" not in briefing_columns:
            conn.execute("ALTER TABLE quick_chat_briefings ADD COLUMN truncated INTEGER NOT NULL DEFAULT 0")
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialize_database() -> None:
    with connection() as conn:
        pass

def upsert_summary(*, meeting_id: str, title: str, meeting_date: str, participants: list[str], simple_summary: str, keywords: list[str], duration_seconds: int, topic_embedding: bytes | None = None) -> None:
    with connection() as conn:
        conn.execute("""
            INSERT INTO meeting_summaries (meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                title=excluded.title,
                meeting_date=excluded.meeting_date,
                participants=excluded.participants,
                simple_summary=excluded.simple_summary,
                keywords=excluded.keywords,
                duration_seconds=excluded.duration_seconds,
                refreshed_at=excluded.refreshed_at,
                topic_embedding=COALESCE(excluded.topic_embedding, meeting_summaries.topic_embedding)
        """, (meeting_id, title, meeting_date, ", ".join(participants), simple_summary, ", ".join(keywords), duration_seconds, datetime.now(UTC).isoformat(), topic_embedding))

def summary_exists(meeting_id: str) -> bool:
    with connection() as conn:
        return conn.execute("SELECT 1 FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,)).fetchone() is not None

def summary_has_keywords(meeting_id: str) -> bool:
    with connection() as conn:
        row = conn.execute("SELECT keywords, duration_seconds FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,)).fetchone()
    return bool(row and row["keywords"].strip() and row["duration_seconds"] > 0)

def get_summary(meeting_id: str) -> dict[str, object] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT meeting_id, title, meeting_date, participants, simple_summary,
                   keywords, duration_seconds, refreshed_at
            FROM meeting_summaries WHERE meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()
    return dict(row) if row else None

def list_summaries(*, offset: int, limit: int, date_from: str | None = None) -> tuple[list[dict[str, str]], int]:
    with connection() as conn:
        where = "WHERE meeting_date >= ?" if date_from else ""
        parameters: tuple[object, ...] = (date_from,) if date_from else ()
        total = conn.execute(f"SELECT COUNT(*) FROM meeting_summaries {where}", parameters).fetchone()[0]
        rows = conn.execute("""
            SELECT meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding
            FROM meeting_summaries {where} ORDER BY meeting_date DESC, refreshed_at DESC LIMIT ? OFFSET ?
        """.format(where=where), (*parameters, limit, offset)).fetchall()
    return [dict(row) for row in rows], total

def list_summaries_for_priority(*, date_from: str | None = None) -> list[dict[str, object]]:
    """Every summary matching the date filter, unpaginated, with its raw
    topic_embedding blob — used to score+sort the full dataset before the
    caller paginates in Python."""
    with connection() as conn:
        where = "WHERE meeting_date >= ?" if date_from else ""
        parameters: tuple[object, ...] = (date_from,) if date_from else ()
        rows = conn.execute(f"""
            SELECT meeting_id, title, meeting_date, participants, simple_summary, keywords, duration_seconds, refreshed_at, topic_embedding
            FROM meeting_summaries {where} ORDER BY meeting_date DESC, refreshed_at DESC
        """, parameters).fetchall()
    return [dict(row) for row in rows]

def delete_summary(meeting_id: str) -> bool:
    with connection() as conn:
        cursor = conn.execute("DELETE FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,))
        _delete_chunks(conn, meeting_id)
        return cursor.rowcount > 0

def _delete_chunks(conn: sqlite3.Connection, meeting_id: str) -> None:
    conn.execute("DELETE FROM transcript_chunks WHERE meeting_id = ?", (meeting_id,))
    conn.execute("DELETE FROM transcript_chunks_fts WHERE meeting_id = ?", (meeting_id,))

def replace_chunks(meeting_id: str, rows: Sequence[dict[str, object]]) -> None:
    """Swap a meeting's whole chunk set in one transaction, so a reader never
    sees half of an old index and half of a new one."""
    with connection() as conn:
        _delete_chunks(conn, meeting_id)
        conn.executemany("""
            INSERT INTO transcript_chunks (
                meeting_id, chunk_index, start, end, speakers, text, transcript,
                embedding, chunker_version)
            VALUES (:meeting_id, :chunk_index, :start, :end, :speakers, :text,
                    :transcript, :embedding, :chunker_version)
        """, [{**row, "meeting_id": meeting_id} for row in rows])
        conn.executemany(
            "INSERT INTO transcript_chunks_fts (text, meeting_id, chunk_index) VALUES (?, ?, ?)",
            [(row["text"], meeting_id, row["chunk_index"]) for row in rows],
        )

def chunk_index_version(meeting_id: str) -> str | None:
    """The chunker version a meeting was indexed with, or None if it never was."""
    with connection() as conn:
        row = conn.execute(
            "SELECT MIN(chunker_version) FROM transcript_chunks WHERE meeting_id = ?",
            (meeting_id,),
        ).fetchone()
    return row[0] if row else None

def indexed_meeting_ids(chunker_version: str) -> set[str]:
    """Meetings whose every chunk was built by `chunker_version`."""
    with connection() as conn:
        rows = conn.execute("""
            SELECT meeting_id FROM transcript_chunks
            GROUP BY meeting_id HAVING MIN(chunker_version) = ? AND MAX(chunker_version) = ?
        """, (chunker_version, chunker_version)).fetchall()
    return {row[0] for row in rows}

def chunk_index_stamp() -> tuple[int, int]:
    """Changes whenever any meeting is (re)indexed or deleted.

    A re-index deletes and re-inserts, so the max rowid always grows; a delete
    always changes the count. Callers cache the corpus keyed by this.
    """
    with connection() as conn:
        count, max_rowid = conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(rowid), 0) FROM transcript_chunks"
        ).fetchone()
    return int(count), int(max_rowid)

def list_all_chunks() -> list[dict[str, object]]:
    with connection() as conn:
        rows = conn.execute("""
            SELECT meeting_id, chunk_index, start, end, text, transcript, embedding
            FROM transcript_chunks ORDER BY meeting_id, chunk_index
        """).fetchall()
    return [dict(row) for row in rows]

def fts_search(match: str, meeting_ids: Sequence[str], limit: int) -> list[tuple[str, int]]:
    """(meeting_id, chunk_index) for an FTS5 MATCH expression, best bm25 first."""
    if not meeting_ids:
        return []
    placeholders = ",".join("?" * len(meeting_ids))
    with connection() as conn:
        rows = conn.execute(f"""
            SELECT meeting_id, chunk_index FROM transcript_chunks_fts
            WHERE transcript_chunks_fts MATCH ? AND meeting_id IN ({placeholders})
            ORDER BY bm25(transcript_chunks_fts) LIMIT ?
        """, (match, *meeting_ids, limit)).fetchall()
    return [(row[0], int(row[1])) for row in rows]

def like_search(needle: str, meeting_ids: Sequence[str], limit: int) -> list[tuple[str, int]]:
    """Substring fallback for terms too short for the trigram index."""
    if not meeting_ids:
        return []
    placeholders = ",".join("?" * len(meeting_ids))
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with connection() as conn:
        rows = conn.execute(f"""
            SELECT meeting_id, chunk_index FROM transcript_chunks
            WHERE text LIKE ? ESCAPE '\\' AND meeting_id IN ({placeholders})
            ORDER BY meeting_id, chunk_index LIMIT ?
        """, (f"%{escaped}%", *meeting_ids, limit)).fetchall()
    return [(row[0], int(row[1])) for row in rows]

def chunks_between(meeting_id: str, first: int, last: int) -> list[dict[str, object]]:
    with connection() as conn:
        rows = conn.execute("""
            SELECT chunk_index, start, end, transcript FROM transcript_chunks
            WHERE meeting_id = ? AND chunk_index BETWEEN ? AND ?
            ORDER BY chunk_index
        """, (meeting_id, first, last)).fetchall()
    return [dict(row) for row in rows]

def list_meeting_ids() -> list[str]:
    with connection() as conn:
        return [row[0] for row in conn.execute("SELECT meeting_id FROM meeting_summaries")]

SUMMARY_COLUMNS = """
    meeting_id, title, meeting_date, participants, simple_summary,
    keywords, duration_seconds, refreshed_at, topic_embedding
"""

def max_meeting_date() -> str | None:
    """The newest meeting_date on record, or None when there are no meetings."""
    with connection() as conn:
        return conn.execute("SELECT MAX(meeting_date) FROM meeting_summaries").fetchone()[0]

def list_summaries_between(*, date_from: str, date_to: str) -> list[dict[str, object]]:
    """Every summary in an inclusive date range, newest first.

    Both bounds are inclusive because meeting_date is a date-only string;
    an exclusive upper bound would silently drop the final day.
    """
    with connection() as conn:
        rows = conn.execute(f"""
            SELECT {SUMMARY_COLUMNS} FROM meeting_summaries
            WHERE meeting_date >= ? AND meeting_date <= ?
            ORDER BY meeting_date DESC, refreshed_at DESC
        """, (date_from, date_to)).fetchall()
    return [dict(row) for row in rows]

def list_summaries_by_ids(meeting_ids: Sequence[str]) -> list[dict[str, object]]:
    """Summaries for the given ids, unordered — the caller restores its order."""
    if not meeting_ids:
        return []
    placeholders = ",".join("?" * len(meeting_ids))
    with connection() as conn:
        rows = conn.execute(f"""
            SELECT {SUMMARY_COLUMNS} FROM meeting_summaries
            WHERE meeting_id IN ({placeholders})
        """, tuple(meeting_ids)).fetchall()
    return [dict(row) for row in rows]

def get_cached_briefing(fingerprint: str) -> dict[str, object] | None:
    """Read a cached briefing, marking it as most recently used."""
    now = datetime.now(UTC).isoformat()
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM quick_chat_briefings WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE quick_chat_briefings SET last_used_at = ? WHERE fingerprint = ?",
            (now, fingerprint),
        )
    briefing = dict(row)
    briefing["meeting_ids"] = json.loads(briefing["meeting_ids"])
    briefing["key_points"] = json.loads(briefing["key_points"])
    briefing["referenced_meetings"] = json.loads(briefing["referenced_meetings"])
    briefing["last_used_at"] = now
    return briefing

def save_briefing(
    *,
    fingerprint: str,
    selection_json: str,
    meeting_ids: Sequence[str],
    meeting_count: int,
    range_start: str | None,
    range_end: str | None,
    summary: str,
    key_points: list[dict[str, object]],
    referenced_meetings: list[dict[str, object]],
    model: str,
    prompt_version: str,
    truncated: bool = False,
    limit: int = BRIEFING_CACHE_LIMIT,
) -> None:
    """Store a briefing and evict all but the `limit` most recently used."""
    now = datetime.now(UTC).isoformat()
    with connection() as conn:
        conn.execute("""
            INSERT INTO quick_chat_briefings (
                fingerprint, selection_json, meeting_ids, meeting_count,
                range_start, range_end, summary, key_points, referenced_meetings,
                model, prompt_version, created_at, last_used_at, truncated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                selection_json=excluded.selection_json,
                summary=excluded.summary,
                key_points=excluded.key_points,
                referenced_meetings=excluded.referenced_meetings,
                last_used_at=excluded.last_used_at,
                truncated=excluded.truncated
        """, (
            fingerprint, selection_json, json.dumps(list(meeting_ids)), meeting_count,
            range_start, range_end, summary, json.dumps(key_points),
            json.dumps(referenced_meetings), model, prompt_version, now, now,
            int(truncated),
        ))
        _evict_old_briefings(conn, limit)

def _evict_old_briefings(conn: sqlite3.Connection, limit: int) -> int:
    """Keep only the `limit` most recently used briefings.

    LRU rather than insertion order, so the presets a user actually cycles
    through stay cached even as one-off date ranges come and go.
    """
    cursor = conn.execute("""
        DELETE FROM quick_chat_briefings WHERE fingerprint NOT IN (
            SELECT fingerprint FROM quick_chat_briefings
            ORDER BY last_used_at DESC, created_at DESC LIMIT ?)
    """, (limit,))
    return cursor.rowcount

def evict_old_briefings(limit: int = BRIEFING_CACHE_LIMIT) -> int:
    with connection() as conn:
        return _evict_old_briefings(conn, limit)

def list_briefings(limit: int = BRIEFING_CACHE_LIMIT) -> list[dict[str, object]]:
    with connection() as conn:
        rows = conn.execute("""
            SELECT fingerprint, meeting_count, range_start, range_end,
                   created_at, last_used_at
            FROM quick_chat_briefings ORDER BY last_used_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]
