from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, list

from src.services.queue import get_task_result

router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None


class FloorPlanResult(BaseModel):
    svg: str
    rooms: list[dict]
    dimensions: list[dict]
    area_m2: float


class ThreeDModelResult(BaseModel):
    glb_url: str | None
    ifc_url: str | None


class ComplianceReport(BaseModel):
    passed: bool
    standard: str
    violations: list[dict]
    warnings: list[dict]


class DesignAlternative(BaseModel):
    index: int
    floor_plan: FloorPlanResult
    compliance: ComplianceReport
    score: float


class JobResultResponse(BaseModel):
    job_id: str
    status: Literal["completed", "failed"]
    floor_plan: FloorPlanResult | None
    three_d_model: ThreeDModelResult | None
    compliance: ComplianceReport | None
    alternatives: list[DesignAlternative] | None
    explainability: list[dict] | None  # design rationale per decision


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll for job status and progress."""
    result = get_task_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job_id,
        status=result.get("status", "queued"),
        progress=result.get("progress", 0.0),
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        error=result.get("error"),
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(job_id: str):
    """Retrieve completed job results."""
    result = get_task_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if result.get("status") != "completed":
        raise HTTPException(
            status_code=400, detail="Job not yet completed. Check /jobs/{job_id} for status."
        )
    return JobResultResponse(**result.get("output", {}))
