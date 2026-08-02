from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any
from app.services.exporters import (
    generate_dxf,
    generate_png,
    generate_pdf,
    generate_ifc,
    generate_3d_massing,
)

router = APIRouter()


class ExportRequest(BaseModel):
    layout: dict[str, Any] = Field(..., description="Candidate layout with rooms and optional site boundary")
    format: str = Field("dxf", pattern="^(dxf|png|pdf|ifc|3d-massing)$")


@router.post("/dxf")
async def export_dxf(req: ExportRequest) -> Response:
    try:
        data = generate_dxf(req.layout)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=layout.dxf"},
    )


@router.post("/png")
async def export_png(req: ExportRequest) -> Response:
    try:
        data = generate_png(req.layout)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=data, media_type="image/png")


@router.post("/pdf")
async def export_pdf(req: ExportRequest) -> StreamingResponse:
    try:
        data = generate_pdf(req.layout)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=layout.pdf"},
    )


@router.post("/ifc")
async def export_ifc(req: ExportRequest) -> dict[str, Any]:
    return generate_ifc(req.layout)


@router.post("/3d-massing")
async def export_3d_massing(req: ExportRequest) -> dict[str, Any]:
    return generate_3d_massing(req.layout)
