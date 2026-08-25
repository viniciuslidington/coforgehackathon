"""Minimal SQLite persistence for generated meeting overview rows."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

from app.core.config import DATABASE_PATH

SCHEMA = """
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
"""

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # A running development server can encounter a newly created SQLite
        # file. Ensure every operation has the table it depends on.
        conn.execute(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(meeting_summaries)")}
        if "keywords" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN keywords TEXT NOT NULL DEFAULT ''")
        if "duration_seconds" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN duration_seconds INTEGER NOT NULL DEFAULT 0")
        if "topic_embedding" not in columns:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN topic_embedding BLOB")
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
                topic_embedding=excluded.topic_embedding
        """, (meeting_id, title, meeting_date, ", ".join(participants), simple_summary, ", ".join(keywords), duration_seconds, datetime.now(UTC).isoformat(), topic_embedding))

def summary_exists(meeting_id: str) -> bool:
    with connection() as conn:
        return conn.execute("SELECT 1 FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,)).fetchone() is not None

def summary_has_keywords(meeting_id: str) -> bool:
    with connection() as conn:
        row = conn.execute("SELECT keywords, duration_seconds FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,)).fetchone()
    return bool(row and row["keywords"].strip() and row["duration_seconds"] > 0)

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
        return cursor.rowcount > 0