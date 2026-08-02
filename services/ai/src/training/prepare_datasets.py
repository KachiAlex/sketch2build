"""Dataset preparation script.

Generates synthetic data and converts real datasets (RPlan, CubiCasa5K)
to our unified format for mixed training.

Usage:
    python -m src.training.prepare_datasets \
        --output_dir data/mixed \
        --synthetic_samples 100000 \
        --rplan_dir /path/to/rplan \
        --cubicasa_dir /path/to/cubicasa5k
"""

import argparse
import structlog
from pathlib import Path

from src.training.data.graph_generator import GraphBasedLayoutGenerator
from src.training.data.rplan_loader import RPlanLoader
from src.training.data.cubicasa_loader import CubiCasa5KLoader

logger = structlog.get_logger()


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare mixed training datasets")
    parser.add_argument("--output_dir", type=str, required=True, help="Output directory for all prepared datasets")
    parser.add_argument("--synthetic_samples", type=int, default=100_000, help="Number of synthetic samples to generate")
    parser.add_argument("--synthetic_valid_ratio", type=float, default=0.7, help="Ratio of valid synthetic samples")
    parser.add_argument("--rplan_dir", type=str, default=None, help="Path to RPlan dataset directory")
    parser.add_argument("--cubicasa_dir", type=str, default=None, help="Path to CubiCasa5K dataset directory")
    parser.add_argument("--rplan_max_samples", type=int, default=None, help="Max RPlan samples to convert")
    parser.add_argument("--cubicasa_max_samples", type=int, default=None, help="Max CubiCasa5K samples to convert")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return parser.parse_args()


def prepare_synthetic(output_dir: Path, num_samples: int, valid_ratio: float, seed: int) -> Path:
    """Generate synthetic dataset using graph-based layout generator."""
    logger.info("Preparing synthetic dataset", num_samples=num_samples, valid_ratio=valid_ratio)

    synth_dir = output_dir / "synthetic"
    synth_dir.mkdir(parents=True, exist_ok=True)

    generator = GraphBasedLayoutGenerator(seed=seed)

    from src.training.data.synthetic_generator import SyntheticDatasetBuilder
    # Use the graph-based generator instead of the old grid-based one
    builder = SyntheticDatasetBuilder(str(synth_dir), image_size=256)
    builder.generator = generator
    builder.build(num_samples=num_samples, valid_ratio=valid_ratio)

    logger.info("Synthetic dataset ready", path=str(synth_dir))
    return synth_dir


def prepare_rplan(output_dir: Path, rplan_dir: str, max_samples: int | None) -> Path | None:
    """Convert RPlan dataset to unified format."""
    rplan_path = Path(rplan_dir)
    if not rplan_path.exists():
        logger.warning("RPlan directory not found, skipping", path=rplan_dir)
        return None

    logger.info("Preparing RPlan dataset", path=rplan_dir, max_samples=max_samples)

    out_dir = output_dir / "rplan"
    loader = RPlanLoader(rplan_dir)
    loader.save_to_disk(str(out_dir), max_samples=max_samples)

    logger.info("RPlan dataset ready", path=str(out_dir))
    return out_dir


def prepare_cubicasa(output_dir: Path, cubicasa_dir: str, max_samples: int | None) -> Path | None:
    """Convert CubiCasa5K dataset to unified format."""
    cubicasa_path = Path(cubicasa_dir)
    if not cubicasa_path.exists():
        logger.warning("CubiCasa5K directory not found, skipping", path=cubicasa_dir)
        return None

    logger.info("Preparing CubiCasa5K dataset", path=cubicasa_dir, max_samples=max_samples)

    out_dir = output_dir / "cubicasa"
    loader = CubiCasa5KLoader(cubicasa_dir)
    loader.save_to_disk(str(out_dir), max_samples=max_samples)

    logger.info("CubiCasa5K dataset ready", path=str(out_dir))
    return out_dir


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting dataset preparation", output_dir=str(output_dir))

    # 1. Synthetic data
    prepare_synthetic(output_dir, args.synthetic_samples, args.synthetic_valid_ratio, args.seed)

    # 2. RPlan
    if args.rplan_dir:
        prepare_rplan(output_dir, args.rplan_dir, args.rplan_max_samples)

    # 3. CubiCasa5K
    if args.cubicasa_dir:
        prepare_cubicasa(output_dir, args.cubicasa_dir, args.cubicasa_max_samples)

    logger.info("Dataset preparation complete", output_dir=str(output_dir))
    print(f"\nDatasets prepared in: {output_dir}")
    print(f"  - Synthetic: {output_dir / 'synthetic'}")
    if args.rplan_dir:
        print(f"  - RPlan: {output_dir / 'rplan'}")
    if args.cubicasa_dir:
        print(f"  - CubiCasa5K: {output_dir / 'cubicasa'}")


if __name__ == "__main__":
    main()
