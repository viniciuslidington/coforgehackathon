from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import initialize_database, list_summaries, summary_exists, summary_has_keywords, upsert_summary, delete_summary
from app.graph import Mode, generate_meeting_overview, run_meeting_agent
# 1. CORREÇÃO: Importando o duration_seconds do vtt
from app.vtt import parse_vtt, transcript_from_captions, duration_seconds 
from app.r2_storage import list_r2_vtt_files, get_r2_vtt_content
import re

logger = logging.getLogger("meeting-insights")

def openrouter_failure(exc: APIStatusError) -> str:
    provider_body = getattr(exc, "body", None)
    suffix = f" Provider response: {provider_body}" if provider_body else ""
    return f"OpenRouter request failed ({exc.status_code}): {exc.message}.{suffix}"

def raise_openrouter_failure(exc: APIStatusError) -> None:
    status_code = 429 if exc.status_code == 429 else 502
    raise HTTPException(status_code=status_code, detail=openrouter_failure(exc)) from exc

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield

app = FastAPI(
    title="Meeting Insights API", 
    description="LangGraph-powered summaries and Q&A for WebVTT meeting transcripts.", 
    version="0.1.0", 
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MeetingResponse(BaseModel):
    result: str
    caption_count: int

class QuestionRequest(BaseModel):
    question: str = Field(min_length=2)

class StoredMeetingSummary(BaseModel):
    meeting_id: str
    title: str
    meeting_date: str
    participants: list[str]
    simple_summary: str
    keywords: list[str]
    duration_seconds: int
    refreshed_at: str

class SummaryPage(BaseModel):
    items: list[StoredMeetingSummary]
    total: int
    page: int
    page_size: int

class RefreshResponse(BaseModel):
    processed: int
    skipped: int
    total_stored: int
    items: list[StoredMeetingSummary]

async def read_transcript(vtt_file: UploadFile) -> tuple[str, int]:
    if not (vtt_file.filename or "").lower().endswith(".vtt"):
        raise HTTPException(status_code=400, detail="Upload a .vtt WebVTT transcript file.")
    try:
        captions = parse_vtt((await vtt_file.read()).decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="The VTT file must be UTF-8 encoded.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return transcript_from_captions(captions), len(captions)

def execute_agent(transcript: str, mode: Mode, focus_points: str | None, question: str | None) -> str:
    points = [item.strip() for item in (focus_points or "").split(",") if item.strip()]
    try:
        return run_meeting_agent(transcript=transcript, mode=mode, focus_points=points, question=question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        logger.error(
            "OpenRouter agent request failed status=%s message=%s body=%r",
            exc.status_code, exc.message, getattr(exc, "body", None)
        )
        raise_openrouter_failure(exc)

def execute_overview(transcript: str) -> tuple[str, str, list[str]]:
    try:
        result = generate_meeting_overview(transcript)
        logger.info("AI overview returned title=%r summary=%r keywords=%s", result[0], result[1], result[2])
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIStatusError as exc:
        logger.error(
            "OpenRouter overview request failed status=%s message=%s body=%r",
            exc.status_code, exc.message, getattr(exc, "body", None)
        )
        raise_openrouter_failure(exc)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

# 2. CORREÇÃO: A rota /meetings listava os mocks, ela foi removida pois agora tudo é dinâmico.

@app.post("/sync-meetings", response_model=RefreshResponse)
def refresh_meetings() -> RefreshResponse:
    """Fetch VTTs from R2 and process only the new ones."""
    processed = 0
    skipped = 0
    
    r2_files = list_r2_vtt_files()
    total = len(r2_files)
    logger.info("Starting meeting sync from R2: total_available=%d", total)
    
    for file_key in r2_files:
        meeting_id = file_key.replace(".vtt", "") 
        
        if summary_exists(meeting_id) and summary_has_keywords(meeting_id):
            skipped += 1
            logger.info("Skipping meeting %s (%d/%d): already processed", meeting_id, processed + skipped, total)
            continue
            
        logger.info("Processing meeting %s (%d/%d)", meeting_id, processed + skipped + 1, total)
        
        raw_vtt = get_r2_vtt_content(file_key)
        captions = parse_vtt(raw_vtt)
        transcript = transcript_from_captions(captions)
        duration = duration_seconds(captions)
        
        # 4. Extrai os participantes dinamicamente das falas
        participants = []
        for caption in captions:
            possible_name, separator, _ = caption.text.partition(":")
            name = possible_name.strip()
            if separator and name and name not in participants:
                participants.append(name)
                
        title, simple_summary, keywords = execute_overview(transcript)
        
        upsert_summary(
            meeting_id=meeting_id, 
            title=title, 
            meeting_date=date.today().isoformat(),
            participants=participants, 
            simple_summary=simple_summary, 
            keywords=keywords, 
            duration_seconds=duration
        )
        processed += 1
        
    page = get_stored_summaries(page=1, page_size=20)
    logger.info("Meeting sync complete: processed=%d skipped=%d total_stored=%d", processed, skipped, page.total)
    
    return RefreshResponse(processed=processed, skipped=skipped, total_stored=page.total, items=page.items)

@app.post("/sync-meetings/batch", response_model=RefreshResponse)
def sync_specific_quantity(limit: int = Query(..., gt=0, description="Quantidade exata de novos arquivos para processar")) -> RefreshResponse:
    """Fetch VTTs from R2 and process exactly 'limit' new meetings."""
    processed = 0
    skipped = 0
    
    r2_files = list_r2_vtt_files()
    total = len(r2_files)
    logger.info(f"Starting batch meeting sync from R2: targeting {limit} new files out of {total} total")
    
    for file_key in r2_files:
        # A MÁGICA AQUI: O loop para assim que atingir o limite de processados
        if processed >= limit:
            break 
            
        meeting_id = file_key.replace(".vtt", "") 
        
        if summary_exists(meeting_id) and summary_has_keywords(meeting_id):
            skipped += 1
            # Evitamos colocar log aqui para não poluir o terminal caso você já tenha muitos arquivos
            continue
            
        logger.info("Processing meeting %s (Processing %d of %d requested)", meeting_id, processed + 1, limit)
        
        raw_vtt = get_r2_vtt_content(file_key)
        captions = parse_vtt(raw_vtt)
        transcript = transcript_from_captions(captions)
        duration = duration_seconds(captions)
        
        # 4. Extrai os participantes dinamicamente das falas
        participants = []
        for caption in captions:
            possible_name, separator, _ = caption.text.partition(":")
            name = possible_name.strip()
            if separator and name and name not in participants:
                participants.append(name)
                
        title, simple_summary, keywords = execute_overview(transcript)
        
        upsert_summary(
            meeting_id=meeting_id, 
            title=title, 
            meeting_date=date.today().isoformat(),
            participants=participants, 
            simple_summary=simple_summary, 
            keywords=keywords, 
            duration_seconds=duration
        )
        processed += 1
        
    page = get_stored_summaries(page=1, page_size=20)
    logger.info("Batch sync complete: processed=%d skipped=%d total_stored=%d", processed, skipped, page.total)
    
    return RefreshResponse(processed=processed, skipped=skipped, total_stored=page.total, items=page.items)

def get_stored_summaries(page: int, page_size: int, period: Literal["day", "week", "30d", "all"] = "all") -> SummaryPage:
    date_from = {
        "day": date.today().isoformat(),
        "week": (date.today() - timedelta(days=6)).isoformat(),
        "30d": (date.today() - timedelta(days=29)).isoformat(),
        "all": None,
    }[period]
    rows, total = list_summaries(offset=(page - 1) * page_size, limit=page_size, date_from=date_from)
    items = []
    for row in rows:
        data = dict(row)
        data["participants"] = [name.strip() for name in data["participants"].split(",") if name.strip()]
        data["keywords"] = [keyword.strip() for keyword in data["keywords"].split(",") if keyword.strip()]
        items.append(StoredMeetingSummary(**data))
    return SummaryPage(items=items, total=total, page=page, page_size=page_size)

@app.get("/meeting-summaries", response_model=SummaryPage)
def get_meeting_summaries(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100), period: Literal["day", "week", "30d", "all"] = "all") -> SummaryPage:
    """Return persisted meeting overviews, filtered by meeting date and paginated."""
    return get_stored_summaries(page, page_size, period)

def load_r2_transcript(meeting_id: str) -> tuple[str, int]:
    """Helper function to load a specific transcript from R2."""
    file_key = f"{meeting_id}.vtt"
    try:
        raw_vtt = get_r2_vtt_content(file_key)
        captions = parse_vtt(raw_vtt)
        return transcript_from_captions(captions), len(captions)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found in R2.") from exc

@app.post("/meetings/{meeting_id}/summaries", response_model=MeetingResponse)
def create_sample_summary(meeting_id: str, mode: Mode = "simple", focus_points: str | None = None) -> MeetingResponse:
    """Create a summary for a specific R2 meeting selected by ID."""
    transcript, caption_count = load_r2_transcript(meeting_id)
    return MeetingResponse(result=execute_agent(transcript, mode, focus_points, None), caption_count=caption_count)

@app.post("/meetings/{meeting_id}/questions", response_model=MeetingResponse)
def ask_sample_question(meeting_id: str, request: QuestionRequest) -> MeetingResponse:
    """Ask a question about a specific R2 meeting selected by ID."""
    transcript, caption_count = load_r2_transcript(meeting_id)
    return MeetingResponse(result=execute_agent(transcript, "simple", None, request.question), caption_count=caption_count)

@app.post("/summaries", response_model=MeetingResponse)
async def create_summary(vtt_file: UploadFile = File(...), mode: Mode = Form("simple"), focus_points: str | None = Form(None)) -> MeetingResponse:
    """Create a simple or detailed meeting summary from a .vtt upload."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_agent(transcript, mode, focus_points, None), caption_count=caption_count)

@app.post("/questions", response_model=MeetingResponse)
async def ask_question(vtt_file: UploadFile = File(...), question: str = Form(..., min_length=2)) -> MeetingResponse:
    """Answer one question strictly from the uploaded VTT transcript."""
    transcript, caption_count = await read_transcript(vtt_file)
    return MeetingResponse(result=execute_agent(transcript, "simple", None, question), caption_count=caption_count)

@app.delete("/meetings/{meeting_id}")
def remove_meeting_summary(meeting_id: str):
    """Deletes a processed meeting summary to allow reprocessing."""
    deleted = delete_summary(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found in database.")
    return {"status": "success", "message": f"Meeting '{meeting_id}' deleted successfully."}
