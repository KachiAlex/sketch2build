from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sketch, prompt, compliance, export

app = FastAPI(
    title="Sketch2Build AI Service",
    version="0.1.0",
    description="Computer vision, intent parsing, layout generation, and compliance helpers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sketch.router, prefix="/sketch", tags=["sketch"])
app.include_router(prompt.router, prefix="/prompt", tags=["prompt"])
app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
app.include_router(export.router, prefix="/export", tags=["export"])
