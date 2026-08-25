"""One-off backfill: compute topic_embedding for meetings synced before the
meeting-priority-by-topic feature existed.

The normal sync pipeline (`_sync_from_r2` in app/routers/meeting_summaries.py)
skips any meeting that already has a summary + keywords, so rows synced
before this feature shipped will never retroactively get a topic_embedding
through normal sync. This script fills those in directly.

This is a manual, out-of-request-path operational script. It is NOT wired
into any API endpoint or automatic trigger — run it by hand when ready:

    cd resume-ai-service && .venv/bin/python -m scripts.backfill_topic_embeddings

(or: .venv/bin/python scripts/backfill_topic_embeddings.py)
"""
from __future__ import annotations

from app.services.database import connection
from app.services.meeting_service import compute_topic_embedding_blob


def _text_for_embedding(title: str, simple_summary: str, keywords_field: str) -> str:
    """Match the exact text-construction pattern used by _sync_from_r2 in
    app/routers/meeting_summaries.py: f"{title} {simple_summary} {' '.join(keywords)}".

    `keywords_field` is the raw comma-joined string stored in the DB column;
    split it back into a list the same way _row_to_summary does before
    rejoining with spaces to match the sync pipeline's text shape.
    """
    keywords = [keyword.strip() for keyword in keywords_field.split(",") if keyword.strip()]
    return f"{title} {simple_summary} {' '.join(keywords)}"


def main() -> None:
    with connection() as conn:
        rows = conn.execute(
            "SELECT meeting_id, title, simple_summary, keywords FROM meeting_summaries "
            "WHERE topic_embedding IS NULL"
        ).fetchall()

        print(f"Found {len(rows)} meeting(s) missing topic_embedding.")

        updated = 0
        for row in rows:
            text = _text_for_embedding(row["title"], row["simple_summary"], row["keywords"])
            blob = compute_topic_embedding_blob(text)
            conn.execute(
                "UPDATE meeting_summaries SET topic_embedding = ? WHERE meeting_id = ?",
                (blob, row["meeting_id"]),
            )
            updated += 1
            print(f"[{updated}/{len(rows)}] backfilled topic_embedding for {row['meeting_id']!r}")

        print(f"Done. Backfilled {updated} of {len(rows)} meeting(s).")


if __name__ == "__main__":
    main()
