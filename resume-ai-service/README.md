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

## Stored meeting overview

`POST /sync-meetings` processes built-in meetings that are new or predate keyword support, so repeated calls do not spend model credits regenerating complete rows. Its response includes `processed`, `skipped`, and `total_stored` counts. Each stored row contains a generated title, simple summary, important transcript-grounded keywords, speaker-derived participants, catalog date, and refresh timestamp. Use `GET /meeting-summaries` to power a meeting table in a client. It accepts `period=day`, `week`, `30d`, or `all` and defaults to 15 rows per page.
