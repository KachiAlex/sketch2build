"""Data models for building code compliance."""

from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum


class ConstraintType(str, Enum):
    HARD = "hard"      # Must be satisfied (e.g., minimum egress width)
    SOFT = "soft"      # Should be satisfied (e.g., natural light preference)


class BuildingCode(str, Enum):
    IBC = "IBC"                          # International Building Code (USA)
    ASHRAE_90_1 = "ASHRAE_90_1"        # Energy efficiency
    ADA = "ADA"                          # Accessibility
    NFPA_101 = "NFPA_101"              # Life safety (egress)
    EUROCODE = "Eurocode"                # European standards
    BS_5839 = "BS_5839"                # UK fire detection
    LOCAL_ZONING = "Local_Zoning"      # Municipality-specific


@dataclass
class Regulation:
    """A single building regulation extracted from codes."""
    id: str
    code: BuildingCode
    section: str                    # e.g., "IBC 1010.1"
    title: str                      # e.g., "Means of Egress - Door Width"
    text: str                       # Full regulation text
    constraint_type: ConstraintType
    applicable_room_types: list[str] = field(default_factory=list)   # e.g., ["bedroom", "living"]
    min_value: Optional[float] = None  # e.g., 0.8 meters (minimum door width)
    max_value: Optional[float] = None  # e.g., maximum travel distance
    unit: str = "meters"
    tags: list[str] = field(default_factory=list)


@dataclass
class Constraint:
    """A constraint extracted from a regulation applicable to a design."""
    regulation_id: str
    constraint_type: ConstraintType
    parameter: str                    # e.g., "door_width", "room_area", "travel_distance"
    target_value: float               # The required value (min or max)
    operator: Literal["min", "max", "equals", "range"] = "min"
    unit: str = "meters"
    description: str = ""


@dataclass
class Violation:
    """A detected violation during compliance checking."""
    constraint: Constraint
    actual_value: float
    room_id: Optional[str] = None
    severity: Literal["critical", "warning", "info"] = "warning"
    message: str = ""
    suggested_fix: str = ""


@dataclass
class ComplianceReport:
    """Full compliance report for a generated floor plan."""
    design_id: str
    jurisdiction: str = "default"
    violations: list[Violation] = field(default_factory=list)
    passed_constraints: list[Constraint] = field(default_factory=list)
    score: float = 0.0              # 0.0 to 1.0
    explanations: list[str] = field(default_factory=list)

    def add_violation(self, violation: Violation) -> None:
        self.violations.append(violation)
        if violation.severity == "critical":
            self.score = max(0.0, self.score - 0.2)
        elif violation.severity == "warning":
            self.score = max(0.0, self.score - 0.05)

    def finalize(self) -> None:
        if not self.violations:
            self.score = 1.0
        else:
            self.score = max(0.0, self.score)
