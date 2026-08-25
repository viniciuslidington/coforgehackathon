from __future__ import annotations

from pathlib import Path

import pytest

from app.services import database


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point database.py at a fresh, empty SQLite file for this test only."""
    path = tmp_path / "test_meeting_insights.db"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    return path
