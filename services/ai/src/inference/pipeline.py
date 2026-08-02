"""End-to-end inference pipeline for design generation."""

import structlog
from typing import Any

from src.inference import vision, layout

logger = structlog.get_logger()


class DesignPipeline:
    """Orchestrates sketch understanding → layout generation → compliance → 3D."""

    def __init__(self):
        self.vision_encoder = vision.SketchEncoder()
        self.layout_generator = layout.LayoutGenerator()
        # self.compliance_engine = ComplianceEngine()  # TODO: Phase 3
        # self.massing_pipeline = MassingPipeline()     # TODO: Phase 4

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
        alternatives = []
        for i in range(generate_alternatives):
            floor_plan = self.layout_generator.generate(
                room_graph=graph,
                style=style,
                constraints=constraints,
                seed=i,
            )
            alternatives.append({
                "index": i,
                "floor_plan": floor_plan,
                "compliance": {"passed": True, "standard": compliance_standard, "violations": [], "warnings": []},
                "score": 0.0,  # TODO: ranking model
            })

        # Step 3: Pick best alternative (or return all)
        best = alternatives[0] if alternatives else None

        result = {
            "job_id": job_id,
            "status": "completed",
            "floor_plan": best["floor_plan"] if best else None,
            "three_d_model": None,  # TODO: Phase 4
            "compliance": best["compliance"] if best else None,
            "alternatives": alternatives,
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
