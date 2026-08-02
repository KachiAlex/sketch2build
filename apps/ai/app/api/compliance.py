from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any
from app.compliance.validator import validate_layout, list_rules

router = APIRouter()


class ValidateRequest(BaseModel):
    layout: dict[str, Any] = Field(..., description="Candidate layout with site and rooms")
    jurisdiction: str = Field("Nigeria", description="Jurisdiction code")


class RulesRequest(BaseModel):
    jurisdiction: str = "Nigeria"


@router.post("/validate")
async def validate_candidate(req: ValidateRequest) -> dict[str, Any]:
    return validate_layout(req.layout, req.jurisdiction)


@router.get("/rules")
async def get_rules(jurisdiction: str = "Nigeria") -> dict[str, Any]:
    return {"jurisdiction": jurisdiction, "rules": list_rules(jurisdiction)}
