from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
from app.core.storage import fetch_file_bytes
from app.geometry.snapping import snap_segments_to_grid, filter_duplicate_segments

router = APIRouter()


@router.post("/digitize")
async def digitize_sketch(
    file: UploadFile = File(...),
    reference_length: Optional[float] = Form(None),
    unit: str = Form("m"),
) -> dict:
    return {
        "status": "queued",
        "message": "Sketch digitization endpoint placeholder. Full CV pipeline in Phase 2.",
        "filename": file.filename,
        "reference_length": reference_length,
        "unit": unit,
    }


class DigitizeFromStorageRequest(BaseModel):
    storageKey: str = Field(..., description="Object storage key for the uploaded sketch")
    referenceLength: float = Field(..., description="Real-world length of the reference line")
    unit: str = Field("m", description="Unit of the reference length")
    projectId: str
    jobId: str


@router.post("/digitize-from-storage")
async def digitize_from_storage(req: DigitizeFromStorageRequest) -> dict:
    """Internal endpoint invoked by the orchestration worker."""
    try:
        # Fetch the image from storage to verify it exists and prepare for processing.
        image_bytes = fetch_file_bytes(req.storageKey)
    except RuntimeError as exc:
        return {"status": "failed", "error": str(exc), "jobId": req.jobId}

    # Placeholder: once the CV model is integrated, it will return raw wall segments.
    # For now, generate a small synthetic rectangular outline as a mock vector graph.
    raw_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = [
        ((0.0, 0.0), (10.0, 0.0)),
        ((10.0, 0.0), (10.0, 8.0)),
        ((10.0, 8.0), (0.0, 8.0)),
        ((0.0, 8.0), (0.0, 0.0)),
    ]
    snapped = snap_segments_to_grid(raw_segments, grid_size=0.05)
    deduped = filter_duplicate_segments(snapped)

    return {
        "status": "completed",
        "jobId": req.jobId,
        "projectId": req.projectId,
        "referenceLength": req.referenceLength,
        "unit": req.unit,
        "imageSize": len(image_bytes),
        "walls": [{"start": s[0], "end": s[1]} for s in deduped],
        "doors": [],
        "windows": [],
        "rooms": [],
    }
