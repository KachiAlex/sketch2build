"""Compliance API endpoints for building code queries and validation."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from src.compliance.rag_engine import ComplianceRAGEngine
from src.compliance.validator import ComplianceValidator
from src.compliance.models import BuildingCode, ComplianceReport

router = APIRouter()

rag_engine = ComplianceRAGEngine()
validator = ComplianceValidator()


class ComplianceQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about building codes")
    code: Literal["IBC", "ASHRAE_90_1", "NFPA_101", "ADA", "Eurocode", "Local_Zoning"] | None = None
    n_results: int = Field(default=5, ge=1, le=20)


class ComplianceQueryResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    source_regulations: list[dict]


class ValidateRequest(BaseModel):
    design_id: str
    rooms: list[dict] = Field(..., description="List of rooms with type, width, depth, area, height, id")
    adjacency: list[tuple[int, int]] = Field(default=[], description="Room adjacency pairs")
    plot_width: float = Field(default=0.0, description="Plot width in meters")
    plot_depth: float = Field(default=0.0, description="Plot depth in meters")
    code: Literal["IBC", "ASHRAE_90_1", "NFPA_101", "ADA", "Eurocode", "Local_Zoning"] | None = None


class ValidateResponse(BaseModel):
    design_id: str
    score: float
    passed: bool
    violations: list[dict]
    hard_violations: int
    soft_violations: int
    explanations: list[str]


class CheckRequirementRequest(BaseModel):
    room_type: str
    parameter: str
    value: float
    unit: str = "meters"
    code: Literal["IBC", "ASHRAE_90_1", "NFPA_101", "ADA", "Eurocode", "Local_Zoning"] | None = None


class CheckRequirementResponse(BaseModel):
    passes: bool | None
    required_value: float | None
    unit: str
    regulation: dict | None
    explanation: str


class DesignGuidanceRequest(BaseModel):
    room_types: list[str]
    jurisdiction: str = "default"
    code: Literal["IBC", "ASHRAE_90_1", "NFPA_101", "ADA", "Eurocode", "Local_Zoning"] | None = None


@router.post("/query", response_model=ComplianceQueryResponse)
async def compliance_query(request: ComplianceQueryRequest):
    """Query the compliance RAG engine with a natural language question."""
    code_enum = BuildingCode(request.code) if request.code else None
    result = rag_engine.query(
        question=request.question,
        code_filter=code_enum,
        n_regulations=request.n_results,
    )
    return ComplianceQueryResponse(
        question=result["question"],
        answer=result["answer"],
        confidence=result["confidence"],
        source_regulations=result["source_regulations"],
    )


@router.post("/validate", response_model=ValidateResponse)
async def validate_floor_plan(request: ValidateRequest):
    """Validate a floor plan against building codes."""
    code_enum = BuildingCode(request.code) if request.code else None

    report = validator.check_floor_plan(
        design_id=request.design_id,
        rooms=request.rooms,
        adjacency=request.adjacency,
        plot_width=request.plot_width,
        plot_depth=request.plot_depth,
        code_filter=code_enum,
    )

    validator.generate_explanations(report)

    hard_count = sum(1 for v in report.violations if v.severity == "critical")
    soft_count = sum(1 for v in report.violations if v.severity == "warning")

    violations_json = []
    for v in report.violations:
        violations_json.append({
            "regulation_id": v.constraint.regulation_id,
            "parameter": v.constraint.parameter,
            "severity": v.severity,
            "message": v.message,
            "suggested_fix": v.suggested_fix,
            "actual_value": v.actual_value,
            "required_value": v.constraint.target_value,
            "unit": v.constraint.unit,
        })

    return ValidateResponse(
        design_id=report.design_id,
        score=report.score,
        passed=report.score >= 0.8 and hard_count == 0,
        violations=violations_json,
        hard_violations=hard_count,
        soft_violations=soft_count,
        explanations=report.explanations,
    )


@router.post("/check-requirement", response_model=CheckRequirementResponse)
async def check_requirement(request: CheckRequirementRequest):
    """Check if a specific design value meets a code requirement."""
    code_enum = BuildingCode(request.code) if request.code else None

    result = rag_engine.check_requirement(
        room_type=request.room_type,
        parameter=request.parameter,
        value=request.value,
        unit=request.unit,
        code_filter=code_enum,
    )

    return CheckRequirementResponse(
        passes=result["passes"],
        required_value=result["required_value"],
        unit=result["unit"],
        regulation=result["regulation"],
        explanation=result["explanation"],
    )


@router.post("/design-guidance")
async def design_guidance(request: DesignGuidanceRequest):
    """Get design guidance for a list of room types."""
    code_enum = BuildingCode(request.code) if request.code else None

    guidance = rag_engine.get_design_guidance(
        room_types=request.room_types,
        jurisdiction=request.jurisdiction,
        code_filter=code_enum,
    )

    return {
        "jurisdiction": request.jurisdiction,
        "room_guidance": guidance,
    }


@router.get("/regulations")
async def list_regulations(
    code: Literal["IBC", "ASHRAE_90_1", "NFPA_101", "ADA", "Eurocode", "Local_Zoning"] | None = None,
    limit: int = 50,
):
    """List available regulations in the vector store."""
    from src.compliance.regulations_seed import get_all_seed_regulations, get_regulations_by_code

    if code:
        regs = get_regulations_by_code(BuildingCode(code))
    else:
        regs = get_all_seed_regulations()

    return {
        "count": len(regs),
        "regulations": [
            {
                "id": r.id,
                "code": r.code.value,
                "section": r.section,
                "title": r.title,
                "constraint_type": r.constraint_type.value,
                "applicable_room_types": r.applicable_room_types,
                "min_value": r.min_value,
                "max_value": r.max_value,
                "unit": r.unit,
                "tags": r.tags,
            }
            for r in regs[:limit]
        ],
    }
