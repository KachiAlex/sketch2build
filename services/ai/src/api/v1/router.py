from fastapi import APIRouter

from src.api.v1 import generate, jobs, health, compliance, exports, explainability, regional, monitoring

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(generate.router, prefix="/design", tags=["design"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(explainability.router, prefix="/explainability", tags=["explainability"])
api_router.include_router(regional.router, prefix="/regional", tags=["regional"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
