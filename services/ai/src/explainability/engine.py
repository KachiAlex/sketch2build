"""Explainability layer for AI-generated architectural designs.

Provides design rationale for each room placement, dimension, and compliance
decision. Generates human-readable explanations linking design choices to
building codes, natural light, ventilation, and spatial quality metrics.
"""

import structlog
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from src.compliance.validator import ComplianceValidator
from src.compliance.models import BuildingCode, ComplianceReport, Violation
from src.compliance.rag_engine import ComplianceRAGEngine

logger = structlog.get_logger()


class ExplanationCategory(str, Enum):
    COMPLIANCE = "compliance"
    SPATIAL_QUALITY = "spatial_quality"
    NATURAL_LIGHT = "natural_light"
    VENTILATION = "ventilation"
    ERGONOMICS = "ergonomics"
    CIRCULATION = "circulation"
    PRIVACY = "privacy"
    ENERGY_EFFICIENCY = "energy_efficiency"
    AESTHETIC = "aesthetic"
    SAFETY = "safety"


@dataclass
class DesignExplanation:
    """A single explanation for a design decision."""
    category: ExplanationCategory
    title: str
    description: str
    room_id: str | None = None
    room_type: str | None = None
    regulation_ref: str | None = None
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ExplainabilityReport:
    """Full explainability report for a generated design."""
    design_id: str
    explanations: list[DesignExplanation] = field(default_factory=list)
    room_explanations: dict[str, list[DesignExplanation]] = field(default_factory=dict)
    overall_summary: str = ""
    design_strengths: list[str] = field(default_factory=list)
    design_weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_id": self.design_id,
            "overall_summary": self.overall_summary,
            "design_strengths": self.design_strengths,
            "design_weaknesses": self.design_weaknesses,
            "recommendations": self.recommendations,
            "explanations": [
                {
                    "category": e.category.value,
                    "title": e.title,
                    "description": e.description,
                    "room_id": e.room_id,
                    "room_type": e.room_type,
                    "regulation_ref": e.regulation_ref,
                    "confidence": e.confidence,
                }
                for e in self.explanations
            ],
            "room_explanations": {
                rid: [
                    {
                        "category": e.category.value,
                        "title": e.title,
                        "description": e.description,
                        "regulation_ref": e.regulation_ref,
                        "confidence": e.confidence,
                    }
                    for e in exps
                ]
                for rid, exps in self.room_explanations.items()
            },
        }


class ExplainabilityEngine:
    """Generates design explanations for AI-generated floor plans."""

    # Cardinal directions for natural light analysis
    NORTH = 0
    EAST = 90
    SOUTH = 180
    WEST = 270

    # Room type light preferences (direction in degrees, 0=N)
    ROOM_LIGHT_PREFERENCES = {
        "living": [SOUTH, EAST, WEST],
        "kitchen": [EAST, SOUTH, WEST],
        "bedroom": [EAST, SOUTH, NORTH],
        "bathroom": [NORTH, WEST],
        "dining": [SOUTH, EAST, WEST],
        "hallway": [],
        "entrance": [NORTH, EAST, WEST],
        "storage": [],
        "garage": [NORTH, EAST],
        "office": [NORTH, EAST, SOUTH],
        "utility": [NORTH, WEST],
        "balcony": [SOUTH, EAST, WEST],
    }

    # Minimum area recommendations (sqm) for spatial quality
    ROOM_AREA_RECOMMENDATIONS = {
        "living": (20.0, "Spacious living area for family gathering"),
        "kitchen": (8.0, "Functional kitchen with adequate counter space"),
        "bedroom": (12.0, "Comfortable bedroom with wardrobe space"),
        "bathroom": (4.5, "Functional bathroom with dry/wet separation"),
        "dining": (10.0, "Dining area accommodating 6+ people"),
        "hallway": (3.0, "Circulation space allowing comfortable passage"),
        "entrance": (3.0, "Entry area with shoe storage and coat rack"),
        "storage": (2.0, "Storage room for household items"),
        "garage": (20.0, "Single car garage with storage"),
        "office": (10.0, "Home office with desk and shelving"),
        "utility": (4.0, "Utility room for laundry and equipment"),
        "balcony": (4.0, "Usable balcony for outdoor relaxation"),
    }

    # Privacy hierarchy (lower = more private)
    PRIVACY_LEVELS = {
        "entrance": 0,
        "garage": 1,
        "hallway": 2,
        "living": 3,
        "dining": 3,
        "kitchen": 4,
        "utility": 4,
        "storage": 4,
        "office": 5,
        "bathroom": 6,
        "bedroom": 7,
        "balcony": 5,
    }

    def __init__(
        self,
        validator: ComplianceValidator | None = None,
        rag_engine: ComplianceRAGEngine | None = None,
    ):
        self.validator = validator or ComplianceValidator()
        self.rag_engine = rag_engine or ComplianceRAGEngine()

    def explain_design(
        self,
        design_id: str,
        rooms: list[dict[str, Any]],
        adjacency: list[tuple[int, int]] | None = None,
        plot_width: float = 0.0,
        plot_depth: float = 0.0,
        compliance_report: ComplianceReport | None = None,
        building_orientation: float = 0.0,
    ) -> ExplainabilityReport:
        """
        Generate a full explainability report for a floor plan design.

        Args:
            design_id: Unique design identifier
            rooms: List of room dicts with type, x, y, width, depth, area, height, id
            adjacency: Room adjacency pairs
            plot_width: Plot width in meters
            plot_depth: Plot depth in meters
            compliance_report: Pre-computed compliance report (optional)
            building_orientation: Building facing direction in degrees (0=North)
        """
        report = ExplainabilityReport(design_id=design_id)
        adjacency = adjacency or []

        # Generate per-room explanations
        for i, room in enumerate(rooms):
            room_id = room.get("id", f"room_{i}")
            room_type = room.get("type", "unknown")
            room_exps = self._explain_room(
                room, i, rooms, adjacency,
                plot_width, plot_depth,
                building_orientation,
            )
            report.room_explanations[room_id] = room_exps
            report.explanations.extend(room_exps)

        # Generate building-level explanations
        building_exps = self._explain_building_level(
            rooms, adjacency, plot_width, plot_depth, building_orientation,
        )
        report.explanations.extend(building_exps)

        # Link compliance violations
        if compliance_report:
            self._link_compliance_violations(report, compliance_report)
        else:
            code_filter = None
            compliance_report = self.validator.check_floor_plan(
                design_id=design_id,
                rooms=rooms,
                adjacency=adjacency,
                plot_width=plot_width,
                plot_depth=plot_depth,
                code_filter=code_filter,
            )
            self._link_compliance_violations(report, compliance_report)

        # Generate summary, strengths, weaknesses, recommendations
        self._generate_summary(report, rooms, compliance_report)

        logger.info(
            "Explainability report generated",
            design_id=design_id,
            explanations=len(report.explanations),
            rooms=len(rooms),
        )
        return report

    def _explain_room(
        self,
        room: dict,
        room_idx: int,
        all_rooms: list[dict],
        adjacency: list[tuple[int, int]],
        plot_width: float,
        plot_depth: float,
        orientation: float,
    ) -> list[DesignExplanation]:
        """Generate explanations for a single room."""
        explanations = []
        room_id = room.get("id", f"room_{room_idx}")
        room_type = room.get("type", "unknown")
        area = room.get("area", room.get("w", 0) * room.get("d", 0))
        width = room.get("w", room.get("width", 0))
        depth = room.get("d", room.get("depth", 0))
        x = room.get("x", 0)
        y = room.get("y", 0)

        # 1. Spatial quality — area assessment
        rec_area, rec_desc = self.ROOM_AREA_RECOMMENDATIONS.get(
            room_type, (0, "Adequate space"),
        )
        if rec_area > 0:
            if area >= rec_area * 1.2:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title=f"Spacious {room_type}",
                    description=f"The {room_type} ({area:.1f} sqm) exceeds the recommended minimum of {rec_area:.1f} sqm, providing excellent spatial quality. {rec_desc}.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.9,
                ))
            elif area >= rec_area:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title=f"Adequate {room_type} size",
                    description=f"The {room_type} ({area:.1f} sqm) meets the recommended minimum of {rec_area:.1f} sqm. {rec_desc}.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.8,
                ))
            else:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title=f"Below recommended {room_type} size",
                    description=f"The {room_type} ({area:.1f} sqm) is below the recommended minimum of {rec_area:.1f} sqm. Consider expanding for better functionality. {rec_desc}.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.85,
                ))

        # 2. Natural light analysis
        light_exps = self._analyze_natural_light(
            room, room_idx, plot_width, plot_depth, orientation,
        )
        explanations.extend(light_exps)

        # 3. Ventilation analysis
        vent_exp = self._analyze_ventilation(room, room_idx, all_rooms, adjacency)
        if vent_exp:
            explanations.append(vent_exp)

        # 4. Privacy analysis
        privacy_exp = self._analyze_privacy(room, room_idx, all_rooms, adjacency)
        if privacy_exp:
            explanations.append(privacy_exp)

        # 5. Circulation analysis
        circ_exp = self._analyze_circulation(room, room_idx, all_rooms, adjacency)
        if circ_exp:
            explanations.append(circ_exp)

        # 6. Ergonomics — aspect ratio check
        if width > 0 and depth > 0:
            ratio = max(width, depth) / min(width, depth)
            if ratio > 2.5:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.ERGONOMICS,
                    title=f"Elongated {room_type} shape",
                    description=f"The {room_type} has an aspect ratio of {ratio:.1f}:1 ({width:.1f}m × {depth:.1f}m). Ratios above 2.5:1 may create awkward furniture layouts. Consider a more proportional shape.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.7,
                ))
            elif ratio < 1.8:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.ERGONOMICS,
                    title=f"Well-proportioned {room_type}",
                    description=f"The {room_type} has a balanced aspect ratio of {ratio:.1f}:1, allowing flexible furniture arrangement.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.8,
                ))

        return explanations

    def _analyze_natural_light(
        self,
        room: dict,
        room_idx: int,
        plot_width: float,
        plot_depth: float,
        orientation: float,
    ) -> list[DesignExplanation]:
        """Analyze natural light potential for a room based on position."""
        explanations = []
        room_type = room.get("type", "unknown")
        room_id = room.get("id", f"room_{room_idx}")
        x = room.get("x", 0)
        y = room.get("y", 0)
        w = room.get("w", room.get("width", 0))
        d = room.get("d", room.get("depth", 0))

        if plot_width == 0 or plot_depth == 0:
            return explanations

        # Determine which walls are exterior (on plot boundary)
        tolerance = 0.5
        is_north_wall = y < tolerance
        is_south_wall = (y + d) > (plot_depth - tolerance)
        is_east_wall = (x + w) > (plot_width - tolerance)
        is_west_wall = x < tolerance

        exterior_walls = []
        if is_north_wall:
            exterior_walls.append("north")
        if is_south_wall:
            exterior_walls.append("south")
        if is_east_wall:
            exterior_walls.append("east")
        if is_west_wall:
            exterior_walls.append("west")

        preferred = self.ROOM_LIGHT_PREFERENCES.get(room_type, [])
        preferred_dirs = []
        for deg in preferred:
            if deg == self.NORTH:
                preferred_dirs.append("north")
            elif deg == self.EAST:
                preferred_dirs.append("east")
            elif deg == self.SOUTH:
                preferred_dirs.append("south")
            elif deg == self.WEST:
                preferred_dirs.append("west")

        if not exterior_walls:
            explanations.append(DesignExplanation(
                category=ExplanationCategory.NATURAL_LIGHT,
                title=f"Interior {room_type} — limited natural light",
                description=f"The {room_type} is positioned in the interior with no exterior walls. Consider adding skylights, light wells, or repositioning to a perimeter location for better daylight access.",
                room_id=room_id,
                room_type=room_type,
                confidence=0.85,
            ))
        elif preferred_dirs:
            matching = [d for d in exterior_walls if d in preferred_dirs]
            if matching:
                directions_str = "/".join(matching)
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.NATURAL_LIGHT,
                    title=f"Optimal daylight orientation for {room_type}",
                    description=f"The {room_type} has exterior walls facing {directions_str}, which is optimal for this room type. This provides favorable natural light conditions throughout the day.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.9,
                ))
            else:
                actual_str = "/".join(exterior_walls)
                preferred_str = "/".join(preferred_dirs)
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.NATURAL_LIGHT,
                    title=f"Suboptimal daylight for {room_type}",
                    description=f"The {room_type} faces {actual_str} but prefers {preferred_str} exposure. Natural light quality may be reduced. Consider window sizing adjustments or room repositioning.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.7,
                ))

        return explanations

    def _analyze_ventilation(
        self,
        room: dict,
        room_idx: int,
        all_rooms: list[dict],
        adjacency: list[tuple[int, int]],
    ) -> DesignExplanation | None:
        """Analyze cross-ventilation potential."""
        room_type = room.get("type", "unknown")
        room_id = room.get("id", f"room_{room_idx}")

        # Check if room has multiple exterior walls (cross-ventilation)
        # Simplified: rooms with 2+ adjacent rooms have better air flow
        adjacent_count = sum(1 for a, b in adjacency if a == room_idx or b == room_idx)

        if room_type in ["kitchen", "bathroom", "utility"]:
            if adjacent_count >= 2:
                return DesignExplanation(
                    category=ExplanationCategory.VENTILATION,
                    title=f"Good ventilation potential for {room_type}",
                    description=f"The {room_type} has connections to {adjacent_count} adjacent spaces, allowing for effective cross-ventilation. Wet rooms benefit from multiple air flow paths.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.75,
                )
            else:
                return DesignExplanation(
                    category=ExplanationCategory.VENTILATION,
                    title=f"Limited ventilation for {room_type}",
                    description=f"The {room_type} has only {adjacent_count} connection(s). As a wet room, consider adding an exhaust fan or direct exterior ventilation to prevent moisture buildup.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.8,
                )

        return None

    def _analyze_privacy(
        self,
        room: dict,
        room_idx: int,
        all_rooms: list[dict],
        adjacency: list[tuple[int, int]],
    ) -> DesignExplanation | None:
        """Analyze privacy based on room adjacency."""
        room_type = room.get("type", "unknown")
        room_id = room.get("id", f"room_{room_idx}")
        room_privacy = self.PRIVACY_LEVELS.get(room_type, 3)

        # Check adjacency to rooms with very different privacy levels
        adjacent_types = []
        for a, b in adjacency:
            if a == room_idx and b < len(all_rooms):
                adjacent_types.append(all_rooms[b].get("type", "unknown"))
            elif b == room_idx and a < len(all_rooms):
                adjacent_types.append(all_rooms[a].get("type", "unknown"))

        issues = []
        for adj_type in adjacent_types:
            adj_privacy = self.PRIVACY_LEVELS.get(adj_type, 3)
            if room_privacy >= 6 and adj_privacy <= 2:
                issues.append(f"{adj_type} (low privacy)")
            elif room_privacy <= 2 and adj_privacy >= 6:
                issues.append(f"{adj_type} (high privacy)")

        if issues and room_type in ["bedroom", "bathroom"]:
            return DesignExplanation(
                category=ExplanationCategory.PRIVACY,
                title=f"Privacy concern for {room_type}",
                description=f"The {room_type} is adjacent to {', '.join(issues)}. Consider adding a buffer space (hallway/closet) for privacy transition.",
                room_id=room_id,
                room_type=room_type,
                confidence=0.7,
            )
        elif room_type in ["bedroom", "bathroom"] and not issues:
            return DesignExplanation(
                category=ExplanationCategory.PRIVACY,
                title=f"Good privacy for {room_type}",
                description=f"The {room_type} is well-separated from public spaces, maintaining appropriate privacy hierarchy.",
                room_id=room_id,
                room_type=room_type,
                confidence=0.8,
            )

        return None

    def _analyze_circulation(
        self,
        room: dict,
        room_idx: int,
        all_rooms: list[dict],
        adjacency: list[tuple[int, int]],
    ) -> DesignExplanation | None:
        """Analyze circulation patterns."""
        room_type = room.get("type", "unknown")
        room_id = room.get("id", f"room_{room_idx}")

        if room_type == "hallway":
            adjacent_count = sum(1 for a, b in adjacency if a == room_idx or b == room_idx)
            if adjacent_count >= 3:
                return DesignExplanation(
                    category=ExplanationCategory.CIRCULATION,
                    title="Well-connected hallway",
                    description=f"The hallway connects to {adjacent_count} rooms, serving as an effective circulation hub. This minimizes dead-end corridors and improves traffic flow.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.85,
                )
            elif adjacent_count <= 1:
                return DesignExplanation(
                    category=ExplanationCategory.CIRCULATION,
                    title="Underutilized hallway",
                    description=f"The hallway only connects to {adjacent_count} room(s). Consider repositioning to serve as a central circulation node connecting multiple rooms.",
                    room_id=room_id,
                    room_type=room_type,
                    confidence=0.75,
                )

        return None

    def _explain_building_level(
        self,
        rooms: list[dict],
        adjacency: list[tuple[int, int]],
        plot_width: float,
        plot_depth: float,
        orientation: float,
    ) -> list[DesignExplanation]:
        """Generate building-level explanations."""
        explanations = []
        total_area = sum(r.get("area", r.get("w", 0) * r.get("d", 0)) for r in rooms)
        plot_area = plot_width * plot_depth

        # FAR / coverage analysis
        if plot_area > 0:
            coverage = total_area / plot_area
            if coverage > 0.8:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title="High site coverage",
                    description=f"Building coverage is {coverage*100:.0f}% of the plot. This leaves limited outdoor space. Consider reducing room sizes or adding a second floor.",
                    confidence=0.85,
                ))
            elif coverage < 0.4:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title="Low site coverage",
                    description=f"Building coverage is {coverage*100:.0f}% of the plot. There is ample outdoor space for garden, parking, or future expansion.",
                    confidence=0.8,
                ))
            else:
                explanations.append(DesignExplanation(
                    category=ExplanationCategory.SPATIAL_QUALITY,
                    title="Balanced site coverage",
                    description=f"Building coverage is {coverage*100:.0f}% of the plot, providing a good balance between indoor and outdoor space.",
                    confidence=0.85,
                ))

        # Room count analysis
        room_types = [r.get("type", "unknown") for r in rooms]
        has_bedroom = "bedroom" in room_types
        has_bathroom = "bathroom" in room_types
        has_kitchen = "kitchen" in room_types
        has_living = "living" in room_types

        essential_count = sum([has_bedroom, has_bathroom, has_kitchen, has_living])
        if essential_count == 4:
            explanations.append(DesignExplanation(
                category=ExplanationCategory.SPATIAL_QUALITY,
                title="Complete essential room set",
                description="The design includes all essential rooms (living, kitchen, bedroom, bathroom), providing a functional residential layout.",
                confidence=0.95,
            ))
        elif essential_count < 3:
            explanations.append(DesignExplanation(
                category=ExplanationCategory.SPATIAL_QUALITY,
                title="Missing essential rooms",
                description=f"Only {essential_count}/4 essential rooms present. A functional residence typically requires living, kitchen, bedroom, and bathroom spaces.",
                confidence=0.9,
            ))

        # Adjacency connectivity
        if rooms and len(adjacency) == 0:
            explanations.append(DesignExplanation(
                category=ExplanationCategory.CIRCULATION,
                title="No room connections defined",
                description="Rooms are not connected via adjacency. In practice, rooms should be linked through doors and hallways for functional circulation.",
                confidence=0.9,
            ))
        elif rooms and len(adjacency) < len(rooms) - 1:
            explanations.append(DesignExplanation(
                category=ExplanationCategory.CIRCULATION,
                title="Limited room connectivity",
                description=f"Only {len(adjacency)} connections for {len(rooms)} rooms. Some rooms may be isolated. Consider adding hallway connections.",
                confidence=0.75,
            ))

        return explanations

    def _link_compliance_violations(
        self,
        report: ExplainabilityReport,
        compliance: ComplianceReport,
    ) -> None:
        """Link compliance violations into the explainability report."""
        for violation in compliance.violations:
            exp = DesignExplanation(
                category=ExplanationCategory.COMPLIANCE,
                title=f"Compliance: {violation.constraint.parameter}",
                description=violation.message,
                regulation_ref=violation.constraint.regulation_id,
                confidence=0.95,
                metadata={
                    "severity": violation.severity,
                    "suggested_fix": violation.suggested_fix,
                    "actual_value": violation.actual_value,
                    "required_value": violation.constraint.target_value,
                },
            )
            report.explanations.append(exp)

    def _generate_summary(
        self,
        report: ExplainabilityReport,
        rooms: list[dict],
        compliance: ComplianceReport,
    ) -> None:
        """Generate overall summary, strengths, weaknesses, and recommendations."""
        room_count = len(rooms)
        total_area = sum(r.get("area", r.get("w", 0) * r.get("d", 0)) for r in rooms)
        hard_violations = [v for v in compliance.violations if v.severity == "critical"]
        soft_violations = [v for v in compliance.violations if v.severity == "warning"]

        # Overall summary
        report.overall_summary = (
            f"This design comprises {room_count} rooms totaling {total_area:.1f} sqm. "
            f"Compliance score: {compliance.score*100:.0f}%. "
            f"{len(hard_violations)} hard violation(s) and {len(soft_violations)} soft violation(s) detected. "
            f"The design was generated with AI-assisted layout optimization and compliance checking."
        )

        # Strengths
        categories = [e.category for e in report.explanations]
        if ExplanationCategory.NATURAL_LIGHT in categories:
            light_exps = [e for e in report.explanations if e.category == ExplanationCategory.NATURAL_LIGHT and "optimal" in e.title.lower()]
            if light_exps:
                report.design_strengths.append("Optimal natural light orientation for key rooms")

        if ExplanationCategory.SPATIAL_QUALITY in categories:
            spacious = [e for e in report.explanations if e.category == ExplanationCategory.SPATIAL_QUALITY and "spacious" in e.title.lower()]
            if spacious:
                report.design_strengths.append("Spacious room dimensions exceeding recommendations")

        if compliance.score >= 0.8:
            report.design_strengths.append(f"High compliance score ({compliance.score*100:.0f}%)")
        if len(hard_violations) == 0:
            report.design_strengths.append("No critical building code violations")

        # Weaknesses
        if hard_violations:
            report.design_weaknesses.append(f"{len(hard_violations)} critical code violation(s) require attention")
        if soft_violations:
            report.design_weaknesses.append(f"{len(soft_violations)} soft violation(s) for improvement")

        weak_light = [e for e in report.explanations if e.category == ExplanationCategory.NATURAL_LIGHT and "limited" in e.title.lower()]
        if weak_light:
            report.design_weaknesses.append("Some rooms have limited natural light access")

        small_rooms = [e for e in report.explanations if e.category == ExplanationCategory.SPATIAL_QUALITY and "below" in e.title.lower()]
        if small_rooms:
            report.design_weaknesses.append(f"{len(small_rooms)} room(s) below recommended size")

        # Recommendations
        for v in hard_violations[:3]:
            if v.suggested_fix:
                report.recommendations.append(v.suggested_fix)

        if weak_light:
            report.recommendations.append("Consider repositioning interior rooms to perimeter locations or adding skylights")

        if not report.recommendations:
            report.recommendations.append("Design meets key requirements. Consider user preferences for style refinements.")
