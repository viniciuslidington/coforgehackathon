# Meeting Insights API

Hackathon-ready Python API that turns missed meetings into short summaries, detailed briefings, and transcript-grounded answers. It accepts **WebVTT (`.vtt`)** uploads and uses **LangGraph** to route each request to a summary or Q&A agent.

## Run it

```bash
cp .env.example .env
# set OPENROUTER_API_KEY in .env
# OPENROUTER_MAX_TOKENS=1200 is a safe summary/Q&A output cap
uv sync
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Endpoints

```bash
# Process and persist only new sample meetings (calls OpenRouter once per new meeting)
curl -X POST http://127.0.0.1:8000/sync-meetings

# Read persisted summary rows, with pagination
curl 'http://127.0.0.1:8000/meeting-summaries?page=1&page_size=20'

# Discover the built-in sample meetings and IDs
curl http://127.0.0.1:8000/meetings

# Summarise a known meeting by ID
curl -X POST 'http://127.0.0.1:8000/meetings/product-planning/summaries?mode=detailed&focus_points=risks,action%20items'

# Ask a question about a known meeting by ID
curl -X POST http://127.0.0.1:8000/meetings/customer-feedback/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"What work is committed for September?"}'

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

`POST /sync-meetings` processes only built-in meetings without a SQLite row, so repeated calls do not spend model credits regenerating existing summaries. Its response includes `processed`, `skipped`, and `total_stored` counts. Each stored row contains a generated title, simple summary, speaker-derived participants, catalog date, and refresh timestamp. Use `GET /meeting-summaries` to power a meeting table in a client.
