from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any
from app.services.intent_parser import parse_brief
from app.services.layout_generator import generate_candidates

router = APIRouter()


class DesignBrief(BaseModel):
    plot_width: float
    plot_depth: float
    unit: str = "m"
    orientation: Optional[float] = None
    prompt: Optional[str] = None
    room_count: Optional[int] = None


class GenerateFromProgramRequest(BaseModel):
    program: dict[str, Any] = Field(..., description="Structured design program from the intent parser")
    projectId: str
    jobId: str


def _validate_dimensions(brief: DesignBrief) -> tuple[dict[str, Any], Optional[str]]:
    warnings = []
    width = brief.plot_width
    depth = brief.plot_depth
    unit = brief.unit.lower()

    if unit not in ("m", "ft", "cm", "mm"):
        raise HTTPException(status_code=400, detail=f"Unrecognized unit: {brief.unit}")

    # Detect ambiguous/implausible values
    if unit == "m" and (width > 500 or depth > 500):
        warnings.append(f"Plot dimensions ({width}, {depth}) m are unusually large; did you mean {brief.unit}?")
    if unit in ("ft", "cm", "mm") and (width < 1 or depth < 1):
        warnings.append(f"Plot dimensions ({width}, {depth}) {brief.unit} are unusually small; did you mean metres?")

    return {"unit_ambiguity_flags": warnings or None}, warnings[0] if warnings else None


@router.post("/parse-and-generate")
async def parse_and_generate(brief: DesignBrief) -> dict:
    validation, _ = _validate_dimensions(brief)
    program = parse_brief(brief.model_dump())
    candidates = generate_candidates(program)
    return {
        "status": "completed",
        "validation": validation,
        "program": program,
        "candidates": candidates,
    }


@router.post("/generate-from-program")
async def generate_from_program(req: GenerateFromProgramRequest) -> dict:
    """Internal endpoint invoked by the orchestration worker."""
    candidates = generate_candidates(req.program)
    return {
        "status": "completed",
        "jobId": req.jobId,
        "projectId": req.projectId,
        "candidates": candidates,
    }
