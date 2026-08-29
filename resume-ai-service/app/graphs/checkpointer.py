"""The single LangGraph checkpointer shared by every persistent graph.

Both the meeting chat and quick chat graphs persist their conversation
history here, keyed by `thread_id`. They deliberately share one long-lived
`SqliteSaver` rather than each opening their own: it points at the same
SQLite file that `app.services.database` writes to through short-lived
connections, and a second long-lived writer materially raises the risk of
`database is locked` under concurrent requests.

Thread ids are namespaced by the caller (`quick-chat:{session_id}`) so the
two graphs never read each other's history out of the shared tables.
"""
from __future__ import annotations

import atexit
from contextlib import AbstractContextManager

from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.config import DATABASE_PATH

_checkpoint_context: AbstractContextManager[SqliteSaver] = SqliteSaver.from_conn_string(str(DATABASE_PATH))
_checkpointer = _checkpoint_context.__enter__()
atexit.register(_checkpoint_context.__exit__, None, None, None)


def get_checkpointer() -> SqliteSaver:
    """Return the process-wide checkpointer backing every persistent graph."""
    return _checkpointer
