# Meeting Insights API

Hackathon-ready Python API that turns missed meetings into short summaries, detailed briefings, and transcript-grounded answers. It accepts **WebVTT (`.vtt`)** uploads and uses **LangGraph** to route each request to a summary or Q&A agent.

## Run it

```bash
cp .env.example .env
# set OPENROUTER_API_KEY and FINNHUB_API_KEY in .env
# OPENROUTER_MAX_TOKENS=1200 is a safe summary/Q&A output cap
uv sync
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Endpoints

```bash
# Process and persist only new sample meetings (calls OpenRouter once per new meeting)
curl -X POST http://127.0.0.1:8000/sync-meetings

# Read persisted summary rows, filtered by date range and paginated
curl 'http://127.0.0.1:8000/meeting-summaries?period=30d&page=1&page_size=15'

# Search meetings by overview and by what was said in the transcript
curl 'http://127.0.0.1:8000/meeting-summaries?q=JGB'

# Discover the built-in sample meetings and IDs
curl http://127.0.0.1:8000/meetings

# Summarise a known meeting by ID
curl -X POST 'http://127.0.0.1:8000/meetings/product-planning/summaries?mode=detailed&focus_points=risks,action%20items'

# Ask a question about a known meeting by ID. The response is an SSE stream;
# reuse session_id for follow-up questions in the same modal session.
curl -N -X POST http://127.0.0.1:8000/meeting-summaries/customer-feedback/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"What work is committed for September?","session_id":"demo-session-001"}'

# Short summary, optionally prioritising selected topics
curl -X POST http://127.0.0.1:8000/summaries -F 'vtt_file=@samples/product-planning.vtt' -F 'mode=simple' -F 'focus_points=decisions, risks, action items'

# Detailed summary accepts mode=detailed (up to four short paragraphs)

# Question answered only from the supplied transcript
curl -X POST http://127.0.0.1:8000/questions -F 'vtt_file=@samples/product-planning.vtt' -F 'question=Who owns usability testing, and when are results due?'
```

## Flow

`WebVTT upload → parser → LangGraph route → summary agent OR Q&A agent → JSON response`

The parser preserves timestamps in the model context, and the Q&A agent is prompted to cite them whenever possible.

## Transcript retrieval (RAG)

The chats no longer send whole transcripts to the model. Each transcript is cut
into short windows of consecutive captions (~90 words, real cue timestamps),
embedded with the same local multilingual model used for priority, and stored
in SQLite (`transcript_chunks` + a trigram FTS5 table). Queries fuse bm25 and
cosine rankings with Reciprocal Rank Fusion (`app/services/retrieval.py`).

- **Meeting chat** sends a short meeting whole; a longer one (over ~8k chars)
  is sent as its opening plus the passages relevant to the question, and the
  agent can call `search_meeting` / `read_transcript_around` for more.
- **Quick Chat** gets `search_transcripts` and `read_transcript_around`, and
  `search_scope` now also matches what was said, not only summaries.
- **Table search** (`GET /meeting-summaries?q=`) filters by literal mentions in
  the overview or transcript, or by meaning (`SEARCH_MIN_SIMILARITY`).

Meetings are indexed at sync. To index meetings stored before this existed,
either press "Get more meetings" (sync now indexes skipped meetings without
calling the LLM) or run the backfill once:

```bash
uv run python -m scripts.backfill_transcript_chunks   # --force to rebuild all
```

Any meeting still unindexed is indexed on demand the first time a chat needs
it. Bump `CHUNKER_VERSION` in `app/services/transcript_index.py` after
changing chunking; the next sync re-indexes everything.

## Stored meeting overview

`POST /sync-meetings` processes built-in meetings that are new or predate keyword support, so repeated calls do not spend model credits regenerating complete rows. Its response includes `processed`, `skipped`, and `total_stored` counts. Each stored row contains a generated title, simple summary, important transcript-grounded keywords, speaker-derived participants, catalog date, and refresh timestamp. Use `GET /meeting-summaries` to power a meeting table in a client. It accepts `period=day`, `week`, `30d`, or `all` and defaults to 15 rows per page.
