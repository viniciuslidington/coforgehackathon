from fastapi import APIRouter, BackgroundTasks
from app.generator import run_batch_generation

router = APIRouter()

@router.post("/generate-batch")
async def trigger_generation(background_tasks: BackgroundTasks, convos: int = 56, hoots: int = 34):
    """
    Endpoint para iniciar a geração em lote.
    Usa BackgroundTasks para não prender a requisição enquanto gera os arquivos.
    """
    background_tasks.add_task(run_batch_generation, convos, hoots)
    return {
        "status": "accepted",
        "message": f"Started background task to generate {convos} conversations and {hoots} hoot calls."
    }

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "transcript-generator"}