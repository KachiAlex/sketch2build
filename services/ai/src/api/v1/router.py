from fastapi import APIRouter

from src.api.v1 import generate, jobs, health, compliance

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(generate.router, prefix="/design", tags=["design"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
