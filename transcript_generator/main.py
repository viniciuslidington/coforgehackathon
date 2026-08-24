from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Transcript Generator API", 
    description="Service to generate synthetic trader VTT transcripts and push to R2."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    # Roda na porta 8001 para não conflitar com o summary_agent que deve estar na 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)