import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, list

from src.services.queue import generate_design_task

router = APIRouter()


class GenerateRequest(BaseModel):
    input_type: Literal["sketch", "text", "hybrid"] = "hybrid"
    sketch_image: str | None = Field(
        None, description="Base64-encoded sketch image (JPEG/PNG)"
    )
    description: str | None = Field(
        None, description="Text description of desired design"
    )
    constraints: dict | None = Field(
        None, description="Layout constraints: max_area, room_types, plot dimensions"
    )
    style: Literal[
        "modern_minimalist",
        "traditional",
        "contemporary",
        "industrial",
        "scandinavian",
        "mediterranean",
    ] = "modern_minimalist"
    compliance_standard: Literal[
        "IBC_2021", "EUROCODE", "NBC_2020", "LOCAL"
    ] = "IBC_2021"
    generate_alternatives: int = Field(1, ge=1, le=5)


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    estimated_seconds: int


@router.post("/generate", response_model=GenerateResponse)
async def generate_design(request: GenerateRequest):
    """Submit a design generation job. Returns immediately with a job ID."""
    job_id = str(uuid.uuid4())

    # TODO: validate sketch image base64 if provided
    # TODO: enqueue Celery task for generation

    task = generate_design_task.delay(
        job_id=job_id,
        input_type=request.input_type,
        sketch_image=request.sketch_image,
        description=request.description,
        constraints=request.constraints,
        style=request.style,
        compliance_standard=request.compliance_standard,
        generate_alternatives=request.generate_alternatives,
    )

    return GenerateResponse(
        job_id=job_id,
        status="queued",
        estimated_seconds=60,  # TODO: dynamic estimate based on queue depth
    )


class AlternativeRequest(BaseModel):
    job_id: str
    alternative_index: int = Field(0, ge=0, le=4)


class RegenerateRequest(BaseModel):
    job_id: str
    feedback: str | None = None
    constraint_adjustments: dict | None = None


@router.post("/regenerate")
async def regenerate_design(request: RegenerateRequest):
    """Regenerate a design based on feedback from a previous job."""
    new_job_id = str(uuid.uuid4())
    # TODO: enqueue regeneration task with context from previous job
    return {"job_id": new_job_id, "status": "queued", "parent_job_id": request.job_id}
