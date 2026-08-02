"""RAG (Retrieval-Augmented Generation) engine for compliance queries.

Retrieves relevant building code regulations based on user queries and
provides natural language explanations using an LLM (Llama 3 or similar).
"""

import structlog
from typing import Any

from src.compliance.vector_store import RegulationVectorStore
from src.compliance.models import BuildingCode, ConstraintType

logger = structlog.get_logger()


class ComplianceRAGEngine:
    """
    RAG engine for answering compliance-related questions.
    
    Uses semantic search over the regulation vector store, then
    formats the retrieved context into a coherent response.
    
    In production, this would be backed by a fine-tuned Llama 3 8B model
    or use an LLM API (OpenAI, Anthropic, etc.) for the generation step.
    """

    def __init__(self, vector_store: RegulationVectorStore | None = None):
        self.vector_store = vector_store or RegulationVectorStore()

    def query(
        self,
        question: str,
        code_filter: BuildingCode | None = None,
        n_regulations: int = 5,
    ) -> dict[str, Any]:
        """
        Answer a compliance question using RAG.
        
        Args:
            question: Natural language question about building codes
            code_filter: Optional building code to filter by
            n_regulations: Number of regulations to retrieve
            
        Returns:
            Dict with answer, source_regulations, and confidence
        """
        # Retrieve relevant regulations
        regulations = self.vector_store.query(
            question,
            code_filter=code_filter,
            n_results=n_regulations,
        )

        # Build context from retrieved regulations
        context_parts = []
        for i, reg in enumerate(regulations):
            metadata = reg.get("metadata", {})
            context_parts.append(
                f"[{i+1}] {metadata.get('code', 'Unknown')} {metadata.get('section', '')}: "
                f"{metadata.get('title', 'Unknown')}\n"
                f"Text: {reg.get('text', '')}\n"
                f"Constraint Type: {metadata.get('constraint_type', 'unknown')}\n"
            )

        context = "\n".join(context_parts)

        # Generate answer (placeholder - replace with LLM call in production)
        answer = self._generate_answer(question, context, regulations)

        # Calculate confidence based on retrieval distance
        avg_distance = sum(r.get("distance", 0.5) for r in regulations) / max(len(regulations), 1)
        confidence = max(0.0, 1.0 - avg_distance)

        logger.info(
            "RAG query answered",
            question=question[:100],
            regulations_found=len(regulations),
            confidence=confidence,
        )

        return {
            "question": question,
            "answer": answer,
            "confidence": confidence,
            "source_regulations": [
                {
                    "id": r["id"],
                    "code": r.get("metadata", {}).get("code", "Unknown"),
                    "section": r.get("metadata", {}).get("section", ""),
                    "title": r.get("metadata", {}).get("title", ""),
                    "text": r["text"][:200] + "..." if len(r.get("text", "")) > 200 else r.get("text", ""),
                    "distance": r.get("distance", 0),
                }
                for r in regulations
            ],
        }

    def _generate_answer(self, question: str, context: str, regulations: list[dict]) -> str:
        """
        Generate a natural language answer from retrieved context.
        
        In production, this calls a fine-tuned Llama 3 8B or an LLM API.
        For now, we return a structured summary based on the top regulation.
        """
        if not regulations:
            return (
                "No specific regulations were found for this query. "
                "Please consult a licensed architect or building code official for authoritative guidance."
            )

        top_reg = regulations[0]
        metadata = top_reg.get("metadata", {})
        code = metadata.get("code", "Unknown")
        section = metadata.get("section", "")
        title = metadata.get("title", "")
        text = top_reg.get("text", "")
        constraint_type = metadata.get("constraint_type", "unknown")

        # Build a structured answer
        answer_parts = [
            f"Based on {code} {section} ({title}):",
            "",
            f"{text}",
            "",
            f"This is a {constraint_type} constraint, meaning it {'must' if constraint_type == 'hard' else 'should'} be satisfied in your design.",
        ]

        # Add references to other retrieved regulations
        if len(regulations) > 1:
            answer_parts.append("")
            answer_parts.append("Related regulations:")
            for r in regulations[1:]:
                r_meta = r.get("metadata", {})
                answer_parts.append(
                    f"- {r_meta.get('code', 'Unknown')} {r_meta.get('section', '')}: {r_meta.get('title', '')}"
                )

        answer_parts.append("")
        answer_parts.append(
            "Note: This is an AI-generated summary for design assistance. "
            "Always verify with a licensed professional and the official code document before construction."
        )

        return "\n".join(answer_parts)

    def check_requirement(
        self,
        room_type: str,
        parameter: str,
        value: float,
        unit: str = "meters",
        code_filter: BuildingCode | None = None,
    ) -> dict[str, Any]:
        """
        Check if a specific design value meets code requirements.
        
        Args:
            room_type: e.g., "bedroom", "kitchen", "bathroom"
            parameter: e.g., "area", "width", "height", "door_width"
            value: The design value to check
            unit: Unit of measurement
            code_filter: Optional building code filter
            
        Returns:
            Dict with passes, required_value, regulation reference, and explanation
        """
        query = f"{room_type} {parameter} requirement minimum maximum residential building code"
        regulations = self.vector_store.query(query, code_filter=code_filter, n_results=3)

        if not regulations:
            return {
                "passes": None,
                "required_value": None,
                "unit": unit,
                "regulation": None,
                "explanation": f"No specific regulation found for {room_type} {parameter}.",
            }

        # Find the most relevant regulation
        best_reg = regulations[0]
        metadata = best_reg.get("metadata", {})
        min_val = metadata.get("min_value")
        max_val = metadata.get("max_value")
        reg_unit = metadata.get("unit", unit)

        passes = True
        required_value = None
        explanation = ""

        # Simple unit conversion (placeholder - real implementation would use pint or similar)
        conversion = self._unit_conversion(reg_unit, unit)
        converted_value = value * conversion

        if min_val is not None and parameter in ["area", "width", "height", "door_width", "min_dimension"]:
            required_value = min_val / conversion
            if converted_value < min_val:
                passes = False
                explanation = (
                    f"{room_type} {parameter} ({value} {unit}) is below the minimum requirement of "
                    f"{min_val} {reg_unit} per {metadata.get('code', 'Unknown')} {metadata.get('section', '')}."
                )
            else:
                explanation = (
                    f"{room_type} {parameter} ({value} {unit}) meets the minimum requirement of "
                    f"{min_val} {reg_unit} per {metadata.get('code', 'Unknown')} {metadata.get('section', '')}."
                )
        elif max_val is not None and parameter in ["FAR", "travel_distance", "height"]:
            required_value = max_val / conversion
            if converted_value > max_val:
                passes = False
                explanation = (
                    f"{room_type} {parameter} ({value} {unit}) exceeds the maximum allowed "
                    f"{max_val} {reg_unit} per {metadata.get('code', 'Unknown')} {metadata.get('section', '')}."
                )
            else:
                explanation = (
                    f"{room_type} {parameter} ({value} {unit}) is within the maximum allowed "
                    f"{max_val} {reg_unit} per {metadata.get('code', 'Unknown')} {metadata.get('section', '')}."
                )
        else:
            explanation = f"Regulation found but no quantitative constraint for {parameter}."

        return {
            "passes": passes,
            "required_value": required_value,
            "unit": unit,
            "regulation": {
                "id": best_reg["id"],
                "code": metadata.get("code", "Unknown"),
                "section": metadata.get("section", ""),
                "title": metadata.get("title", ""),
                "text": best_reg["text"][:200] + "..." if len(best_reg.get("text", "")) > 200 else best_reg.get("text", ""),
            },
            "explanation": explanation,
        }

    def _unit_conversion(self, from_unit: str, to_unit: str) -> float:
        """Convert between common units. Returns multiplier to convert from from_unit to to_unit."""
        # Simple conversion factors
        conversions = {
            ("meters", "meters"): 1.0,
            ("meters", "feet"): 3.28084,
            ("feet", "meters"): 0.3048,
            ("square_meters", "square_meters"): 1.0,
            ("square_meters", "square_feet"): 10.7639,
            ("square_feet", "square_meters"): 0.092903,
            ("meters", "inches"): 39.3701,
            ("inches", "meters"): 0.0254,
            ("ratio", "ratio"): 1.0,
            ("count", "count"): 1.0,
            ("dB", "dB"): 1.0,
            ("lux", "lux"): 1.0,
            ("minutes", "minutes"): 1.0,
            ("kN_per_sqm", "kN_per_sqm"): 1.0,
            ("watts_per_sqm", "watts_per_sqm"): 1.0,
        }

        key = (from_unit, to_unit)
        if key in conversions:
            return conversions[key]

        # Try reverse
        reverse_key = (to_unit, from_unit)
        if reverse_key in conversions:
            return 1.0 / conversions[reverse_key]

        # Default: assume same unit
        return 1.0

    def get_design_guidance(
        self,
        room_types: list[str],
        jurisdiction: str = "default",
        code_filter: BuildingCode | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get design guidance for a list of room types.
        
        Returns a list of relevant regulations for each room type
        with design recommendations.
        """
        guidance = []
        for room_type in room_types:
            query = f"{room_type} design requirements minimum dimensions residential building code"
            regulations = self.vector_store.query(query, code_filter=code_filter, n_results=5)

            room_guidance = {
                "room_type": room_type,
                "relevant_regulations": [
                    {
                        "id": r["id"],
                        "code": r.get("metadata", {}).get("code", "Unknown"),
                        "section": r.get("metadata", {}).get("section", ""),
                        "title": r.get("metadata", {}).get("title", ""),
                        "constraint_type": r.get("metadata", {}).get("constraint_type", "unknown"),
                        "text": r["text"][:150] + "..." if len(r.get("text", "")) > 150 else r.get("text", ""),
                    }
                    for r in regulations
                ],
            }
            guidance.append(room_guidance)

        return guidance
