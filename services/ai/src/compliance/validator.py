"""Building code compliance validator for floor plans.

Checks floor plans against regulations from the vector store and generates
compliance reports with violations, explanations, and suggested fixes.
"""

import structlog
from typing import Any

from src.compliance.models import (
    Regulation, Constraint, Violation, ComplianceReport, ConstraintType, BuildingCode
)
from src.compliance.vector_store import RegulationVectorStore
from src.compliance.regulations_seed import get_all_seed_regulations

logger = structlog.get_logger()


class ComplianceValidator:
    """Validates floor plans against building code regulations."""

    # Room type mapping from our model to regulation terminology
    ROOM_TYPE_ALIASES = {
        "living": ["living room", "living", "lounge", "family room"],
        "bedroom": ["bedroom", "sleeping room", "sleeping"],
        "kitchen": ["kitchen", "cooking area"],
        "bathroom": ["bathroom", "toilet", "washroom", "restroom"],
        "dining": ["dining room", "dining", "breakfast room"],
        "hallway": ["hallway", "corridor", "passage", "hall"],
        "entrance": ["entrance", "entry", "foyer", "vestibule"],
        "storage": ["storage", "closet", "pantry", "wardrobe"],
        "garage": ["garage", "carport", "parking"],
        "balcony": ["balcony", "terrace", "patio", "deck"],
        "office": ["office", "study", "work room"],
        "utility": ["utility", "laundry", "mechanical room"],
    }

    def __init__(self, vector_store: RegulationVectorStore | None = None, jurisdiction: str = "default"):
        self.vector_store = vector_store or RegulationVectorStore()
        self.jurisdiction = jurisdiction

        # Seed regulations if vector store is empty
        if self.vector_store.count() == 0:
            logger.info("Vector store empty, seeding regulations")
            regulations = get_all_seed_regulations()
            self.vector_store.add_regulations(regulations)
            self.vector_store.save()

    def _get_room_type_aliases(self, room_type: str) -> list[str]:
        """Get all aliases for a room type."""
        return self.ROOM_TYPE_ALIASES.get(room_type, [room_type])

    def _query_relevant_regulations(
        self,
        room_type: str,
        code_filter: BuildingCode | None = None,
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Query vector store for regulations relevant to a room type."""
        aliases = self._get_room_type_aliases(room_type)
        query = f"Building code requirements for {', '.join(aliases)} in residential floor plan"
        return self.vector_store.query(query, code_filter=code_filter, n_results=n_results)

    def _check_room_constraints(
        self,
        room: dict[str, Any],
        regulations: list[dict[str, Any]],
    ) -> list[Violation]:
        """Check a single room against applicable regulations."""
        violations = []
        room_type = room.get("type", "")
        room_id = room.get("id", "")
        room_area = room.get("area", room.get("width", 0) * room.get("depth", 0))
        room_width = room.get("width", 0)
        room_depth = room.get("depth", 0)
        min_dimension = min(room_width, room_depth)

        for reg in regulations:
            metadata = reg.get("metadata", {})
            constraint_type = metadata.get("constraint_type", "hard")
            min_value = metadata.get("min_value")
            max_value = metadata.get("max_value")
            unit = metadata.get("unit", "meters")
            title = metadata.get("title", "Unknown")
            section = metadata.get("section", "")
            code = metadata.get("code", "IBC")

            # Check applicable room types
            applicable = metadata.get("applicable_room_types", [])
            if applicable and room_type not in applicable:
                continue

            # Check minimum constraints
            if min_value is not None and unit == "square_meters":
                if room_area < min_value:
                    violations.append(Violation(
                        constraint=Constraint(
                            regulation_id=reg["id"],
                            constraint_type=ConstraintType(constraint_type),
                            parameter="room_area",
                            target_value=min_value,
                            operator="min",
                            unit=unit,
                            description=f"{code} {section}: {title}",
                        ),
                        actual_value=room_area,
                        room_id=room_id,
                        severity="critical" if constraint_type == "hard" else "warning",
                        message=f"{room_type} area ({room_area:.2f} m²) is below minimum ({min_value} m²) per {code} {section}",
                        suggested_fix=f"Increase {room_type} dimensions to at least {min_value / max(room_width, room_depth, 1):.1f} m on the shorter side or expand both dimensions",
                    ))

            elif min_value is not None and unit == "meters" and "width" in title.lower():
                if min_dimension < min_value:
                    violations.append(Violation(
                        constraint=Constraint(
                            regulation_id=reg["id"],
                            constraint_type=ConstraintType(constraint_type),
                            parameter="min_dimension",
                            target_value=min_value,
                            operator="min",
                            unit=unit,
                            description=f"{code} {section}: {title}",
                        ),
                        actual_value=min_dimension,
                        room_id=room_id,
                        severity="critical" if constraint_type == "hard" else "warning",
                        message=f"{room_type} minimum dimension ({min_dimension:.2f} m) is below requirement ({min_value} m) per {code} {section}",
                        suggested_fix=f"Increase {room_type} minimum dimension to at least {min_value} m",
                    ))

            elif min_value is not None and unit == "meters" and "height" in title.lower():
                room_height = room.get("height", 2.5)  # default assumption
                if room_height < min_value:
                    violations.append(Violation(
                        constraint=Constraint(
                            regulation_id=reg["id"],
                            constraint_type=ConstraintType(constraint_type),
                            parameter="ceiling_height",
                            target_value=min_value,
                            operator="min",
                            unit=unit,
                            description=f"{code} {section}: {title}",
                        ),
                        actual_value=room_height,
                        room_id=room_id,
                        severity="critical" if constraint_type == "hard" else "warning",
                        message=f"{room_type} ceiling height ({room_height:.2f} m) is below requirement ({min_value} m) per {code} {section}",
                        suggested_fix=f"Raise ceiling height to at least {min_value} m",
                    ))

            # Check maximum constraints
            if max_value is not None and unit == "ratio" and "FAR" in title:
                # FAR is checked at the building level, not per room
                pass
            elif max_value is not None and unit == "meters" and "distance" in title.lower():
                # Travel distance is checked at the plan level
                pass

        return violations

    def check_floor_plan(
        self,
        design_id: str,
        rooms: list[dict[str, Any]],
        adjacency: list[tuple[int, int]],
        plot_width: float = 0.0,
        plot_depth: float = 0.0,
        code_filter: BuildingCode | None = None,
    ) -> ComplianceReport:
        """
        Validate a floor plan against all applicable regulations.

        Args:
            design_id: Unique identifier for the design
            rooms: List of room dicts with keys: type, width, depth, area, height, id
            adjacency: Room adjacency list (room indices)
            plot_width: Total plot width (for FAR/zoning checks)
            plot_depth: Total plot depth
            code_filter: Optional building code to filter by

        Returns:
            ComplianceReport with violations, score, and explanations
        """
        report = ComplianceReport(design_id=design_id, jurisdiction=self.jurisdiction)

        # Check each room against regulations
        for room in rooms:
            room_type = room.get("type", "")
            regulations = self._query_relevant_regulations(room_type, code_filter=code_filter)
            violations = self._check_room_constraints(room, regulations)
            for v in violations:
                report.add_violation(v)

        # Check building-level constraints
        # FAR (Floor Area Ratio)
        if plot_width > 0 and plot_depth > 0:
            total_floor_area = sum(r.get("area", r.get("width", 0) * r.get("depth", 0)) for r in rooms)
            plot_area = plot_width * plot_depth
            far = total_floor_area / plot_area if plot_area > 0 else 0

            # Query FAR regulations
            far_regs = self._query_relevant_regulations("floor area ratio", code_filter=code_filter, n_results=3)
            for reg in far_regs:
                metadata = reg.get("metadata", {})
                max_far = metadata.get("max_value")
                if max_far is not None and far > max_far:
                    report.add_violation(Violation(
                        constraint=Constraint(
                            regulation_id=reg["id"],
                            constraint_type=ConstraintType(metadata.get("constraint_type", "hard")),
                            parameter="FAR",
                            target_value=max_far,
                            operator="max",
                            unit="ratio",
                            description=metadata.get("title", "FAR Limit"),
                        ),
                        actual_value=far,
                        severity="critical",
                        message=f"Floor Area Ratio ({far:.2f}) exceeds maximum ({max_far}) per {metadata.get('code', 'Zoning')}",
                        suggested_fix=f"Reduce total floor area or increase plot size to achieve FAR <= {max_far}",
                    ))

        # Check bathroom-kitchen separation (IBC 1204.2)
        bathroom_indices = [i for i, r in enumerate(rooms) if r.get("type") == "bathroom"]
        kitchen_indices = [i for i, r in enumerate(rooms) if r.get("type") == "kitchen"]
        bedroom_indices = [i for i, r in enumerate(rooms) if r.get("type") == "bedroom"]

        for b_idx in bathroom_indices:
            for k_idx in kitchen_indices:
                if (b_idx, k_idx) in adjacency or (k_idx, b_idx) in adjacency:
                    # Direct adjacency is a violation
                    report.add_violation(Violation(
                        constraint=Constraint(
                            regulation_id="IBC-1204-2",
                            constraint_type=ConstraintType.HARD,
                            parameter="bathroom_kitchen_separation",
                            target_value=1.0,
                            operator="min",
                            description="IBC 1204.2: Separation of Kitchen and Bathroom",
                        ),
                        actual_value=0.0,
                        room_id=rooms[b_idx].get("id", str(b_idx)),
                        severity="critical",
                        message="Bathroom is directly adjacent to kitchen (IBC 1204.2 violation)",
                        suggested_fix="Insert a hallway or wall between bathroom and kitchen",
                    ))

        # Check bedroom-egress (IBC 1015.1)
        for b_idx in bedroom_indices:
            has_exit = False
            for i, j in adjacency:
                if i == b_idx and j in [k for k, r in enumerate(rooms) if r.get("type") in ["hallway", "entrance"]]:
                    has_exit = True
                if j == b_idx and i in [k for k, r in enumerate(rooms) if r.get("type") in ["hallway", "entrance"]]:
                    has_exit = True

            if not has_exit:
                report.add_violation(Violation(
                    constraint=Constraint(
                        regulation_id="IBC-1015-1",
                        constraint_type=ConstraintType.HARD,
                        parameter="bedroom_egress",
                        target_value=1.0,
                        operator="min",
                        description="IBC 1015.1: Exits from Bedrooms",
                    ),
                    actual_value=0.0,
                    room_id=rooms[b_idx].get("id", str(b_idx)),
                    severity="critical",
                    message="Bedroom has no direct access to hallway or entrance (IBC 1015.1 violation)",
                    suggested_fix="Connect bedroom to hallway or entrance via an adjacency edge",
                ))

        # Check for bathroom presence
        if len(rooms) > 3 and not bathroom_indices:
            report.add_violation(Violation(
                constraint=Constraint(
                    regulation_id="IBC-GENERAL-BATH",
                    constraint_type=ConstraintType.HARD,
                    parameter="bathroom_present",
                    target_value=1.0,
                    operator="min",
                    description="General: Bathroom Required",
                ),
                actual_value=0.0,
                severity="critical",
                message="Floor plan has no bathroom (required for residential with >3 rooms)",
                suggested_fix="Add a bathroom with minimum area 3.7 m²",
            ))

        # Check for entrance presence
        if not any(r.get("type") == "entrance" for r in rooms):
            report.add_violation(Violation(
                constraint=Constraint(
                    regulation_id="IBC-GENERAL-ENTRANCE",
                    constraint_type=ConstraintType.HARD,
                    parameter="entrance_present",
                    target_value=1.0,
                    operator="min",
                    description="General: Entrance Required",
                ),
                actual_value=0.0,
                severity="critical",
                message="Floor plan has no entrance/foyer",
                suggested_fix="Add an entrance room connected to the exterior",
            ))

        report.finalize()
        logger.info(
            "Compliance check complete",
            design_id=design_id,
            violations=len(report.violations),
            score=report.score,
            hard_violations=len([v for v in report.violations if v.constraint.constraint_type == ConstraintType.HARD]),
        )
        return report

    def explain_violation(self, violation: Violation) -> str:
        """Generate a human-readable explanation for a violation."""
        constraint = violation.constraint
        return (
            f"[{violation.severity.upper()}] {violation.message}\n"
            f"  Regulation: {constraint.description}\n"
            f"  Required: {constraint.target_value} {constraint.unit} ({constraint.operator})\n"
            f"  Actual: {violation.actual_value} {constraint.unit}\n"
            f"  Suggested fix: {violation.suggested_fix}"
        )

    def generate_explanations(self, report: ComplianceReport) -> list[str]:
        """Generate full explanation list for all violations."""
        explanations = []
        for v in report.violations:
            explanations.append(self.explain_violation(v))
        report.explanations = explanations
        return explanations
