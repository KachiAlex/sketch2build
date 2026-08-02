"""Export API endpoints for generating downloadable design files.

Supports IFC (BIM), DXF (AutoCAD), and GLB (WebGL) formats.
"""

import base64
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from src.models.massing.extruder import FloorPlanExtruder, MultiStoryExtruder, Building3D
from src.models.massing.ifc_export import IFCExporter
from src.models.massing.dxf_export import DXFExporter
from src.models.massing.glb_export import GLBExporter

router = APIRouter()

extruder = FloorPlanExtruder()
ifc_exporter = IFCExporter()
dxf_exporter = DXFExporter()
glb_exporter = GLBExporter()


class ExportFloorPlanRequest(BaseModel):
    design_id: str
    rooms: list[dict] = Field(..., description="List of rooms with type, x, y, width/depth, height, id")
    adjacency: list[tuple[int, int]] = Field(default=[], description="Room adjacency pairs")
    entrance_position: tuple[float, float] | None = None
    format: Literal["ifc", "dxf-2d", "dxf-3d", "glb"] = "glb"
    multi_story: bool = False
    floor_heights: list[float] | None = None


class ExportResponse(BaseModel):
    design_id: str
    format: str
    file_url: str | None = None
    file_base64: str | None = None
    file_size_bytes: int
    content_type: str
    metadata: dict


class Export3DPreviewRequest(BaseModel):
    rooms: list[dict] = Field(..., description="List of rooms with type, x, y, width/depth, id")
    adjacency: list[tuple[int, int]] = Field(default=[])
    entrance_position: tuple[float, float] | None = None
    size: int = Field(default=512, ge=128, le=2048)


class Export3DPreviewResponse(BaseModel):
    preview_image_base64: str
    width: int
    height: int


def _build_building_3d(request: ExportFloorPlanRequest) -> Building3D:
    """Build a 3D building from the floor plan request."""
    if request.multi_story:
        multi = MultiStoryExtruder(base_extruder=extruder)
        # Single floor for now, but extensible
        building = multi.extrude_building(
            floors=[request.rooms],
            floor_heights=request.floor_heights or [3.0],
            adjacency_per_floor=[request.adjacency],
        )
    else:
        building = extruder.extrude_floor_plan(
            rooms=request.rooms,
            adjacency=request.adjacency,
            entrance_position=request.entrance_position,
        )
    return building


@router.post("/export", response_model=ExportResponse)
async def export_floor_plan(request: ExportFloorPlanRequest):
    """Export a floor plan to IFC, DXF, or GLB format."""
    import tempfile
    from pathlib import Path

    building = _build_building_3d(request)

    tmp_dir = Path(tempfile.gettempdir()) / "sketch2build"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    content_type = "application/octet-stream"
    metadata = {
        "rooms": len(building.rooms),
        "total_floor_area": sum(r.floor_area for r in building.rooms),
        "total_volume": sum(r.volume for r in building.rooms),
    }

    if request.format == "ifc":
        output_path = tmp_dir / f"{request.design_id}.ifc"
        ifc_exporter.export(building, str(output_path))
        content_type = "application/x-step"
        metadata["format_version"] = "IFC4"

    elif request.format == "dxf-2d":
        output_path = tmp_dir / f"{request.design_id}_2d.dxf"
        dxf_exporter.export_2d(building, str(output_path))
        content_type = "image/vnd.dxf"
        metadata["format_version"] = "AC1015"

    elif request.format == "dxf-3d":
        output_path = tmp_dir / f"{request.design_id}_3d.dxf"
        dxf_exporter.export_3d(building, str(output_path))
        content_type = "image/vnd.dxf"
        metadata["format_version"] = "AC1015"

    elif request.format == "glb":
        output_path = tmp_dir / f"{request.design_id}.glb"
        glb_exporter.export(building, str(output_path))
        content_type = "model/gltf-binary"
        metadata["format_version"] = "glTF 2.0"

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")

    file_size = output_path.stat().st_size

    with open(output_path, "rb") as f:
        file_base64 = base64.b64encode(f.read()).decode("utf-8")

    return ExportResponse(
        design_id=request.design_id,
        format=request.format,
        file_base64=file_base64,
        file_size_bytes=file_size,
        content_type=content_type,
        metadata=metadata,
    )


@router.post("/3d-preview", response_model=Export3DPreviewResponse)
async def generate_3d_preview(request: Export3DPreviewRequest):
    """Generate a 2D preview image from the 3D axonometric projection."""
    import io

    building = extruder.extrude_floor_plan(
        rooms=request.rooms,
        adjacency=request.adjacency,
        entrance_position=request.entrance_position,
    )

    preview_image = extruder.generate_3d_preview_image(building, size=request.size)

    buffer = io.BytesIO()
    preview_image.save(buffer, format="PNG")
    preview_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return Export3DPreviewResponse(
        preview_image_base64=preview_base64,
        width=preview_image.width,
        height=preview_image.height,
    )
