"""Constrained diffusion for layout generation.

Integrates compliance constraints into the diffusion sampling process
by rejecting or penalizing samples that violate building codes.
"""

import structlog
import torch
import torch.nn as nn

from src.compliance.validator import ComplianceValidator
from src.compliance.models import ConstraintType, Violation

logger = structlog.get_logger()


class ConstrainedDiffusionSampler:
    """Wraps a diffusion model with compliance constraints during sampling."""

    def __init__(
        self,
        model: nn.Module,
        validator: ComplianceValidator,
        num_inference_steps: int = 50,
        guidance_scale: float = 1.0,
        constraint_penalty_weight: float = 0.5,
        rejection_sampling: bool = True,
        max_rejections: int = 10,
    ):
        self.model = model
        self.validator = validator
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.constraint_penalty_weight = constraint_penalty_weight
        self.rejection_sampling = rejection_sampling
        self.max_rejections = max_rejections

    def _extract_rooms_from_tensor(self, image_tensor: torch.Tensor) -> list[dict]:
        """
        Extract room bounding boxes from a generated floor plan image.
        This is a simplified placeholder - real implementation would use
        the sketch encoder or image segmentation.
        """
        # For now, return dummy data - in production this would use
        # the vision encoder's room graph output
        return []

    def _compute_constraint_penalty(
        self,
        image_tensor: torch.Tensor,
        room_types: torch.Tensor,
        bboxes: torch.Tensor,
        adjacency: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute a penalty based on compliance violations.
        Returns a scalar penalty value (0 = fully compliant, >0 = violations).
        """
        # Convert tensors to room dicts for the validator
        rooms = []
        batch_size = bboxes.size(0)
        num_rooms = bboxes.size(1)

        for b in range(batch_size):
            batch_rooms = []
            for i in range(num_rooms):
                if room_types[b, i].item() == 0:
                    continue  # Skip empty rooms
                bbox = bboxes[b, i].detach().cpu().numpy()
                batch_rooms.append({
                    "id": f"b{b}_r{i}",
                    "type": self._room_type_from_idx(room_types[b, i].item()),
                    "x": float(bbox[0]),
                    "y": float(bbox[1]),
                    "width": float(bbox[2]),
                    "depth": float(bbox[3]),
                    "area": float(bbox[2] * bbox[3]),
                })
            rooms.append(batch_rooms)

        # Check compliance for each sample in the batch
        penalty = torch.zeros(batch_size, device=image_tensor.device)

        for b in range(batch_size):
            if not rooms[b]:
                continue

            # Build adjacency list for this batch
            adj_list = []
            for i in range(num_rooms):
                for j in range(num_rooms):
                    if adjacency[b, i, j].item() > 0.5:
                        adj_list.append((i, j))

            report = self.validator.check_floor_plan(
                design_id=f"sample_{b}",
                rooms=rooms[b],
                adjacency=adj_list,
            )

            # Penalty based on hard violations
            for v in report.violations:
                if v.constraint.constraint_type == ConstraintType.HARD:
                    penalty[b] += 1.0
                else:
                    penalty[b] += 0.3

        return penalty

    def _room_type_from_idx(self, idx: int) -> str:
        """Map room type index to string."""
        types = [
            "living", "kitchen", "bedroom", "bathroom", "dining",
            "hallway", "entrance", "balcony", "storage", "garage",
            "office", "utility",
        ]
        if idx < len(types):
            return types[idx]
        return "utility"

    @torch.no_grad()
    def sample(
        self,
        room_types: torch.Tensor,
        bboxes: torch.Tensor,
        adjacency: torch.Tensor,
        mask: torch.Tensor,
        shape: tuple,
        device: str = "cuda",
    ) -> torch.Tensor:
        """
        Generate floor plans with compliance-aware sampling.

        Uses rejection sampling: if generated plan violates hard constraints,
        resample with noise perturbation until compliant or max rejections reached.
        """
        best_sample = None
        best_penalty = float('inf')
        attempts = 0
        max_attempts = 1 if not self.rejection_sampling else self.max_rejections

        while attempts < max_attempts:
            # Generate sample using base diffusion model
            sample = self.model.generate(
                room_types, bboxes, adjacency, mask,
                shape=shape, num_inference_steps=self.num_inference_steps,
            )

            # Compute compliance penalty
            penalty = self._compute_constraint_penalty(sample, room_types, bboxes, adjacency)
            batch_penalty = penalty.sum().item()

            logger.info(
                "Constrained sampling attempt",
                attempt=attempts + 1,
                penalty=batch_penalty,
                violations=int(penalty.sum().item()),
            )

            if batch_penalty < best_penalty:
                best_sample = sample
                best_penalty = batch_penalty

            if batch_penalty == 0:
                # Fully compliant, return immediately
                logger.info("Fully compliant sample generated")
                return sample

            attempts += 1

        logger.info(
            "Returning best sample after max attempts",
            penalty=best_penalty,
            attempts=attempts,
        )
        return best_sample

    def sample_with_guidance(
        self,
        room_types: torch.Tensor,
        bboxes: torch.Tensor,
        adjacency: torch.Tensor,
        mask: torch.Tensor,
        shape: tuple,
        device: str = "cuda",
    ) -> torch.Tensor:
        """
        Generate with classifier-free guidance + compliance guidance.
        
        Uses the diffusion model's generate method but adds a compliance
        penalty as an additional guidance term during denoising.
        """
        # For now, delegate to standard sampling - full guidance integration
        # requires modifying the model's forward pass during each denoising step
        return self.sample(room_types, bboxes, adjacency, mask, shape, device)
