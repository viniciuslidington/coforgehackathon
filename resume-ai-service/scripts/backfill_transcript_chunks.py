"""One-off backfill: build the transcript chunk index for stored meetings.

Indexes every meeting in `meeting_summaries` that has no chunks yet, or whose
chunks were built by an older CHUNKER_VERSION. Summaries are not touched and
no LLM is called — only an R2 fetch and the local embedding model per meeting.

The sync endpoint does the same for each meeting it visits, so this is only
needed to index everything up front without pressing "Get more meetings":

    cd resume-ai-service && .venv/bin/python -m scripts.backfill_transcript_chunks

Pass --force to re-index every meeting regardless of version.
"""
from __future__ import annotations

import sys
import time

from app.services.database import list_meeting_ids
from app.services.transcript_index import index_meeting, is_indexed
from app.services.transcripts import transcript_repository


def main(force: bool = False) -> None:
    meeting_ids = [mid for mid in list_meeting_ids() if force or not is_indexed(mid)]
    print(f"Found {len(meeting_ids)} meeting(s) to index.")

    indexed = 0
    chunks = 0
    started = time.perf_counter()
    for position, meeting_id in enumerate(meeting_ids, start=1):
        captions = transcript_repository.get_captions(meeting_id)
        if captions is None:
            print(f"[{position}/{len(meeting_ids)}] no transcript for {meeting_id!r}, skipped")
            continue
        count = index_meeting(meeting_id, captions)
        indexed += 1
        chunks += count
        print(f"[{position}/{len(meeting_ids)}] indexed {meeting_id!r}: {count} chunk(s)")

    elapsed = time.perf_counter() - started
    print(f"Done. Indexed {indexed} of {len(meeting_ids)} meeting(s), {chunks} chunk(s) in {elapsed:.1f}s.")


if __name__ == "__main__":
    main(force="--force" in sys.argv[1:])
