from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ai-engine", "version": "0.1.0"}
