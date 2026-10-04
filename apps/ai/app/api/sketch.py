import logging

from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional
from app.core.storage import fetch_file_bytes
from app.services.vlm_sketch import VLMSketchEncoder
from app.services.layout_generator import _openings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/digitize")
async def digitize_sketch(
    file: UploadFile = File(...),
    reference_length: Optional[float] = Form(None),
    reference_pixels: Optional[float] = Form(None),
    unit: str = Form("m"),
) -> dict:
    image_bytes = await file.read()
    return _digitize(image_bytes, reference_length, reference_pixels, unit)


class DigitizeFromStorageRequest(BaseModel):
    storageKey: str = Field(..., description="Object storage key for the uploaded sketch")
    referenceLength: float = Field(..., description="Real-world length of the reference line")
    referencePixels: Optional[float] = Field(None, description="Pixel length of the reference line")
    unit: str = Field("m", description="Unit of the reference length")
    projectId: str
    jobId: str


@router.post("/digitize-from-storage")
async def digitize_from_storage(req: DigitizeFromStorageRequest) -> dict:
    """Internal endpoint invoked by the orchestration worker."""
    try:
        image_bytes = fetch_file_bytes(req.storageKey)
    except RuntimeError as exc:
        return {"status": "failed", "error": str(exc), "jobId": req.jobId}

    result = _digitize(image_bytes, req.referenceLength, req.referencePixels, req.unit)
    result.update({"jobId": req.jobId, "projectId": req.projectId})
    return result


def _digitize(
    image_bytes: bytes,
    reference_length: Optional[float],
    reference_pixels: Optional[float],
    unit: str,
) -> dict:
    """VLM room-graph extraction scaled to real-world coordinates.

    Scale is derived from the user's reference line (referenceLength over
    referencePixels, in `unit` per pixel). Without pixel calibration we fall
    back to assuming the detected building extent equals referenceLength —
    crude but deterministic, and the renderer shows dimensions so a bad
    scale is obvious.
    """
    encoder = VLMSketchEncoder()
    if not encoder.has_providers():
        return {
            "status": "failed",
            "error": "No VLM provider configured (set GROQ_API_KEY or GEMINI_API_KEY)",
        }

    try:
        graph = encoder.encode(image_bytes)
    except Exception as exc:  # noqa: BLE001 — PIL errors, provider failures
        return {"status": "failed", "error": f"Sketch extraction failed: {exc}"}

    img_w = graph["imageSize"]["width"]
    img_h = graph["imageSize"]["height"]
    rooms_n = graph["rooms"]

    # Building extent in pixels (union of room bboxes).
    bx0 = min(r["bbox"][0] for r in rooms_n) * img_w
    by0 = min(r["bbox"][1] for r in rooms_n) * img_h
    bx1 = max(r["bbox"][0] + r["bbox"][2] for r in rooms_n) * img_w
    by1 = max(r["bbox"][1] + r["bbox"][3] for r in rooms_n) * img_h
    extent_px = max(bx1 - bx0, 1.0)

    if reference_pixels and reference_length:
        unit_per_px = reference_length / reference_pixels
    elif reference_length:
        unit_per_px = reference_length / extent_px
    else:
        unit_per_px = 0.05  # ~20 px per metre fallback
    scale_note = (
        "calibrated"
        if reference_pixels and reference_length
        else "approximate (no pixel calibration — verify dimensions)"
    )

    rooms = []
    for i, r in enumerate(rooms_n):
        x, y, w, h = r["bbox"]
        rx, ry = (x * img_w - bx0) * unit_per_px, (y * img_h - by0) * unit_per_px
        rw, rh = w * img_w * unit_per_px, h * img_h * unit_per_px
        rooms.append(
            {
                "type": r["type"],
                "label": r["type"].capitalize(),
                "area": round(rw * rh, 2),
                "confidence": r["confidence"],
                "boundaryGeometry": [
                    [round(rx, 2), round(ry, 2)],
                    [round(rx + rw, 2), round(ry, 2)],
                    [round(rx + rw, 2), round(ry + rh, 2)],
                    [round(rx, 2), round(ry + rh, 2)],
                ],
                "_rect": (rx, ry, rx + rw, ry + rh),
            }
        )

    placed = [dict(r) for r in rooms]
    plot = {
        "width": round((bx1 - bx0) * unit_per_px, 2),
        "depth": round((by1 - by0) * unit_per_px, 2),
    }
    doors, windows = _openings(placed, plot)
    for r in rooms:
        r.pop("_rect", None)

    return {
        "status": "completed",
        "source": graph["source"],
        "scale": scale_note,
        "unit": unit,
        "plot": plot,
        "doors": doors,
        "windows": windows,
        "adjacency": graph["adjacency"],
        "rooms": rooms,
        "walls": [],
    }
