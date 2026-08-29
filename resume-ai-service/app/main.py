from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.routers import agent, meeting_summaries, quick_chat
from app.services.database import initialize_database

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield

app = FastAPI(title="Meeting Insights API", description="LangGraph-powered summaries and Q&A for WebVTT meeting transcripts.", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

app.include_router(meeting_summaries.router)
app.include_router(quick_chat.router)
app.include_router(agent.router)
