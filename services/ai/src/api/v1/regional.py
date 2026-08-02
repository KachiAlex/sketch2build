"""Regional profiles API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any

from src.regional.profiles import RegionalProfileManager

router = APIRouter()

manager = RegionalProfileManager()


class ApplyProfileRequest(BaseModel):
    region_key: str = Field(..., description="Regional profile key (e.g., 'nordic', 'middle_east')")
    base_constraints: dict | None = None
    rooms: list[dict] | None = None


@router.get("/profiles")
async def list_profiles() -> dict[str, Any]:
    """List all available regional profiles."""
    return {
        "count": len(manager.list_profiles()),
        "profiles": manager.list_profiles(),
    }


@router.get("/profiles/{region_key}")
async def get_profile(region_key: str) -> dict[str, Any]:
    """Get a specific regional profile."""
    profile = manager.get_profile(region_key)
    if not profile:
        return {"error": f"Profile '{region_key}' not found", "available": list(manager.profiles.keys())}
    return profile.to_dict()


@router.post("/apply")
async def apply_profile(request: ApplyProfileRequest) -> dict[str, Any]:
    """Apply a regional profile to design constraints and optionally adjust room sizes."""
    profile = manager.get_profile(request.region_key)
    if not profile:
        return {"error": f"Profile '{request.region_key}' not found"}

    constraints = manager.apply_profile_to_constraints(profile, request.base_constraints)

    adjusted_rooms = None
    if request.rooms:
        adjusted_rooms = manager.apply_area_multipliers(profile, request.rooms)

    return {
        "region_key": request.region_key,
        "profile": profile.to_dict(),
        "adjusted_constraints": constraints,
        "adjusted_rooms": adjusted_rooms,
    }
