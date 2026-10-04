from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Optional
from app.compliance.validator import validate_layout, list_rules, build_ruleset
from app.compliance.repair import repair_layout
from app.compliance.geometry import Rect
from app.services.layout_generator import _openings

router = APIRouter()


class ValidateRequest(BaseModel):
    layout: dict[str, Any] = Field(..., description="Candidate layout with site and rooms")
    jurisdiction: str = Field("Nigeria", description="Jurisdiction code")
    rules: Optional[list[dict[str, Any]]] = Field(
        None, description="DB compliance rules merged over the base ruleset"
    )
    repair: bool = Field(False, description="Attempt to repair violations and re-validate")


@router.post("/validate")
async def validate_candidate(req: ValidateRequest) -> dict[str, Any]:
    result = validate_layout(req.layout, req.jurisdiction, req.rules)

    if req.repair and result.get("status") == "completed" and not result["passed"]:
        ruleset = build_ruleset(req.jurisdiction, req.rules)
        if ruleset:
            repaired_layout, repair_log = repair_layout(req.layout, ruleset)
            if repair_log:
                # Recompute openings/plot from the repaired geometry.
                placed = []
                for r in repaired_layout.get("rooms", []):
                    rr = Rect.from_polygon(r.get("boundaryGeometry", []))
                    placed.append({**r, "_rect": (rr.x_min, rr.y_min, rr.x_max, rr.y_max)})
                if placed:
                    bx0 = min(p["_rect"][0] for p in placed)
                    by0 = min(p["_rect"][1] for p in placed)
                    bx1 = max(p["_rect"][2] for p in placed)
                    by1 = max(p["_rect"][3] for p in placed)
                    plot = {"width": round(bx1 - bx0, 2), "depth": round(by1 - by0, 2)}
                    doors, windows = _openings(placed, plot)
                    repaired_layout["plot"] = plot
                    repaired_layout["doors"] = doors
                    repaired_layout["windows"] = windows
                recheck = validate_layout(repaired_layout, req.jurisdiction, req.rules)
                result = {
                    **recheck,
                    "repaired": recheck["passed"],
                    "repairLog": repair_log,
                    "layout": repaired_layout,
                }

    return result


@router.get("/rules")
async def get_rules(jurisdiction: str = "Nigeria") -> dict[str, Any]:
    return {"jurisdiction": jurisdiction, "rules": list_rules(jurisdiction)}
