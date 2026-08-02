"""End-to-end inference pipeline for design generation."""

import structlog
from typing import Any

from src.inference import vision, layout
from src.compliance.validator import ComplianceValidator
from src.compliance.models import BuildingCode, ComplianceReport
from src.models.massing.extruder import FloorPlanExtruder

logger = structlog.get_logger()


class DesignPipeline:
    """Orchestrates sketch understanding → layout generation → compliance → 3D."""

    def __init__(self):
        self.vision_encoder = vision.SketchEncoder()
        self.layout_generator = layout.LayoutGenerator()
        self.compliance_validator = ComplianceValidator()
        self.extruder = FloorPlanExtruder()

    def run(
        self,
        job_id: str,
        input_type: str,
        sketch_image: str | None,
        description: str | None,
        constraints: dict | None,
        style: str,
        compliance_standard: str,
        generate_alternatives: int,
    ) -> dict[str, Any]:
        """Run the full generation pipeline."""
        logger.info("Starting design pipeline", job_id=job_id, input_type=input_type)

        # Step 1: Parse input into structured representation
        if sketch_image:
            graph = self.vision_encoder.encode(sketch_image)
            logger.info("Sketch encoded", job_id=job_id, rooms=graph.get("room_types", []))
        else:
            graph = self._text_to_graph(description, constraints)

        # Step 2: Generate layout(s)
        code_enum = BuildingCode(compliance_standard) if compliance_standard in [e.value for e in BuildingCode] else None
        alternatives = []
        for i in range(generate_alternatives):
            floor_plan = self.layout_generator.generate(
                room_graph=graph,
                style=style,
                constraints=constraints,
                seed=i,
            )

            # Step 3: Validate compliance
            rooms = floor_plan.get("rooms", [])
            adjacency = floor_plan.get("adjacency", [])
            plot_width = floor_plan.get("plot_width", constraints.get("plot_width", 0) if constraints else 0)
            plot_depth = floor_plan.get("plot_depth", constraints.get("plot_depth", 0) if constraints else 0)

            report = self.compliance_validator.check_floor_plan(
                design_id=f"{job_id}_alt_{i}",
                rooms=rooms,
                adjacency=adjacency,
                plot_width=plot_width,
                plot_depth=plot_depth,
                code_filter=code_enum,
            )
            self.compliance_validator.generate_explanations(report)

            compliance_result = {
                "passed": report.score >= 0.8 and all(v.severity != "critical" for v in report.violations),
                "standard": compliance_standard,
                "score": report.score,
                "violations": [
                    {
                        "regulation_id": v.constraint.regulation_id,
                        "parameter": v.constraint.parameter,
                        "severity": v.severity,
                        "message": v.message,
                        "suggested_fix": v.suggested_fix,
                    }
                    for v in report.violations
                ],
                "explanations": report.explanations,
            }

            # Step 4: Generate 3D massing from floor plan
            building_3d = self.extruder.extrude_floor_plan(
                rooms=rooms,
                adjacency=adjacency,
                entrance_position=floor_plan.get("entrance_position", None),
            )
            three_d_summary = {
                "room_count": len(building_3d.rooms),
                "total_floor_area": sum(r.floor_area for r in building_3d.rooms),
                "total_volume": sum(r.volume for r in building_3d.rooms),
                "floors": building_3d.floors,
            }

            # Generate 3D preview image
            preview_3d = self.extruder.generate_3d_preview_image(building_3d, size=512)

            alternatives.append({
                "index": i,
                "floor_plan": floor_plan,
                "compliance": compliance_result,
                "three_d_model": three_d_summary,
                "preview_3d": preview_3d,
                "score": report.score,  # Use compliance score for ranking
            })

        # Step 5: Rank and pick best alternative (highest compliance score)
        alternatives.sort(key=lambda x: x["score"], reverse=True)
        best = alternatives[0] if alternatives else None

        result = {
            "job_id": job_id,
            "status": "completed",
            "floor_plan": best["floor_plan"] if best else None,
            "three_d_model": best["three_d_model"] if best else None,
            "compliance": best["compliance"] if best else None,
            "alternatives": [
                {
                    "index": alt["index"],
                    "floor_plan": alt["floor_plan"],
                    "compliance": alt["compliance"],
                    "three_d_model": alt["three_d_model"],
                }
                for alt in alternatives
            ],
            "explainability": [],  # TODO: Phase 5
        }

        logger.info("Design pipeline completed", job_id=job_id, alternatives=len(alternatives))
        return result

    def _text_to_graph(self, description: str | None, constraints: dict | None) -> dict:
        """Convert text description + constraints into a room adjacency graph."""
        # TODO: use LLM to parse text into structured room graph
        room_types = constraints.get("room_types", ["living", "kitchen", "bedroom", "bath"]) if constraints else ["living", "kitchen", "bedroom", "bath"]
        return {
            "room_types": room_types,
            "adjacency": [],  # TODO: infer from text
            "dimensions": constraints or {},
        }
