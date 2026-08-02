"""Explainability API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any

from src.explainability.engine import ExplainabilityEngine

router = APIRouter()

engine = ExplainabilityEngine()


class ExplainRequest(BaseModel):
    design_id: str
    rooms: list[dict] = Field(..., description="List of rooms with type, x, y, width/depth, area, height, id")
    adjacency: list[tuple[int, int]] = Field(default=[])
    plot_width: float = Field(default=0.0)
    plot_depth: float = Field(default=0.0)
    building_orientation: float = Field(default=0.0, description="Building facing direction in degrees (0=North)")


@router.post("/explain")
async def explain_design(request: ExplainRequest) -> dict[str, Any]:
    """Generate an explainability report for a floor plan design."""
    report = engine.explain_design(
        design_id=request.design_id,
        rooms=request.rooms,
        adjacency=request.adjacency,
        plot_width=request.plot_width,
        plot_depth=request.plot_depth,
        building_orientation=request.building_orientation,
    )
    return report.to_dict()
