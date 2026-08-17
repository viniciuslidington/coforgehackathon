"""Minimal SQLite persistence for generated meeting overview rows."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

DATABASE_PATH = Path(os.getenv("MEETINGS_DATABASE_PATH", Path(__file__).resolve().parent.parent / "meeting_insights.db"))

SCHEMA = """
    CREATE TABLE IF NOT EXISTS meeting_summaries (
        meeting_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        meeting_date TEXT NOT NULL,
        participants TEXT NOT NULL,
        simple_summary TEXT NOT NULL,
        refreshed_at TEXT NOT NULL
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
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialize_database() -> None:
    with connection() as conn:
        pass

def upsert_summary(*, meeting_id: str, title: str, meeting_date: str, participants: list[str], simple_summary: str) -> None:
    with connection() as conn:
        conn.execute("""
            INSERT INTO meeting_summaries (meeting_id, title, meeting_date, participants, simple_summary, refreshed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                title=excluded.title,
                meeting_date=excluded.meeting_date,
                participants=excluded.participants,
                simple_summary=excluded.simple_summary,
                refreshed_at=excluded.refreshed_at
        """, (meeting_id, title, meeting_date, ", ".join(participants), simple_summary, datetime.now(UTC).isoformat()))

def summary_exists(meeting_id: str) -> bool:
    with connection() as conn:
        return conn.execute("SELECT 1 FROM meeting_summaries WHERE meeting_id = ?", (meeting_id,)).fetchone() is not None

def list_summaries(*, offset: int, limit: int) -> tuple[list[dict[str, str]], int]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()[0]
        rows = conn.execute("""
            SELECT meeting_id, title, meeting_date, participants, simple_summary, refreshed_at
            FROM meeting_summaries ORDER BY refreshed_at DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
    return [dict(row) for row in rows], total
