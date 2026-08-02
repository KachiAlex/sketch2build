import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(
    title="Sketch2Build AI Engine",
    description="Multi-modal AI for architectural sketch-to-plan generation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ai-engine", "version": "0.1.0"}


@app.on_event("startup")
async def startup():
    logger.info("AI engine starting up", env=settings.app_env)


@app.on_event("shutdown")
async def shutdown():
    logger.info("AI engine shutting down")
