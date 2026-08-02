"""Mixed training script for the Sketch-to-Graph Vision Encoder.

Trains on a blend of synthetic, RPlan, and CubiCasa5K data with
configurable sampling weights.

Usage:
    python -m src.training.train_mixed_vision \
        --mixed_dir data/mixed \
        --output_dir output/mixed_vision \
        --synthetic_weight 0.5 \
        --rplan_weight 0.3 \
        --cubicasa_weight 0.2
"""

import argparse
import structlog
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import CLIPProcessor, get_cosine_schedule_with_warmup
import wandb

from src.config import get_settings
from src.models.vision.sketch_encoder import SketchEncoderModel
from src.training.data.mixed_dataset import create_mixed_datasets
from src.training.train_vision import collate_fn, compute_loss, validate

logger = structlog.get_logger()
settings = get_settings()


def parse_args():
    parser = argparse.ArgumentParser(description="Train Vision Encoder on mixed data")
    parser.add_argument("--mixed_dir", type=str, required=True, help="Directory containing prepared datasets")
    parser.add_argument("--output_dir", type=str, default="./output/mixed_vision")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--num_epochs", type=int, default=50)
    parser.add_argument("--warmup_steps", type=int, default=1000)
    parser.add_argument("--freeze_backbone_epochs", type=int, default=5)
    parser.add_argument("--val_every", type=int, default=1000)
    parser.add_argument("--save_every", type=int, default=5000)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--resume", type=str, default=None)

    # Dataset weights
    parser.add_argument("--synthetic_weight", type=float, default=0.5)
    parser.add_argument("--rplan_weight", type=float, default=0.3)
    parser.add_argument("--cubicasa_weight", type=float, default=0.2)
    parser.add_argument("--max_rooms", type=int, default=20)
    return parser.parse_args()


def train():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Starting mixed vision training", device=device, args=args)

    if settings.wandb_api_key:
        wandb.init(
            project=settings.wandb_project,
            entity=settings.wandb_entity,
            name="mixed_vision_encoder",
            config=vars(args),
        )

    # Processor
    processor = CLIPProcessor.from_pretrained(settings.vision_model_name)

    # Create mixed datasets
    weights = {
        "synthetic": args.synthetic_weight,
        "rplan": args.rplan_weight,
        "cubicasa": args.cubicasa_weight,
    }

    synthetic_dir = Path(args.mixed_dir) / "synthetic"
    rplan_dir = Path(args.mixed_dir) / "rplan" if (Path(args.mixed_dir) / "rplan").exists() else None
    cubicasa_dir = Path(args.mixed_dir) / "cubicasa" if (Path(args.mixed_dir) / "cubicasa").exists() else None

    train_sketch, train_layout = create_mixed_datasets(
        synthetic_dir=str(synthetic_dir) if synthetic_dir.exists() else "",
        rplan_dir=str(rplan_dir) if rplan_dir else None,
        cubicasa_dir=str(cubicasa_dir) if cubicasa_dir else None,
        processor=processor,
        split="train",
        weights=weights,
        max_rooms=args.max_rooms,
    )
    val_sketch, val_layout = create_mixed_datasets(
        synthetic_dir=str(synthetic_dir) if synthetic_dir.exists() else "",
        rplan_dir=str(rplan_dir) if rplan_dir else None,
        cubicasa_dir=str(cubicasa_dir) if cubicasa_dir else None,
        processor=processor,
        split="val",
        weights=weights,
        max_rooms=args.max_rooms,
    )

    logger.info(
        "Datasets loaded",
        train_sketch=len(train_sketch),
        val_sketch=len(val_sketch),
        weights=weights,
    )

    # DataLoaders
    train_loader = DataLoader(
        train_sketch,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_sketch,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
        pin_memory=True,
    )

    # Model
    model = SketchEncoderModel(
        pretrained_model=settings.vision_model_name,
        freeze_backbone=True,
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    total_steps = len(train_loader) * args.num_epochs
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=total_steps,
    )

    start_step = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_step = checkpoint.get("step", 0)
        logger.info("Resumed from checkpoint", step=start_step)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model.train()
    global_step = start_step

    for epoch in range(args.num_epochs):
        if epoch == args.freeze_backbone_epochs:
            logger.info("Unfreezing backbone")
            for param in model.vision_model.parameters():
                param.requires_grad = True

        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}

            optimizer.zero_grad()
            outputs = model(batch["pixel_values"])
            loss, loss_components = compute_loss(outputs, batch)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), settings.max_grad_norm)
            optimizer.step()
            scheduler.step()

            global_step += 1

            if global_step % 100 == 0:
                logger.info(
                    "Training step",
                    step=global_step,
                    epoch=epoch,
                    loss=loss.item(),
                    lr=scheduler.get_last_lr()[0],
                    **loss_components,
                )
                if settings.wandb_api_key:
                    wandb.log(
                        {
                            "train/loss": loss.item(),
                            **{f"train/{k}": v for k, v in loss_components.items()},
                            "train/lr": scheduler.get_last_lr()[0],
                        },
                        step=global_step,
                    )

            if global_step % args.val_every == 0:
                val_metrics = validate(model, val_loader, device)
                logger.info("Validation", step=global_step, **val_metrics)
                if settings.wandb_api_key:
                    wandb.log({f"val/{k}": v for k, v in val_metrics.items()}, step=global_step)
                model.train()

            if global_step % args.save_every == 0:
                checkpoint_path = output_dir / f"checkpoint_step_{global_step}.pt"
                torch.save({
                    "step": global_step,
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                }, checkpoint_path)
                logger.info("Checkpoint saved", path=str(checkpoint_path))

    final_path = output_dir / "final_model.pt"
    torch.save({"model_state_dict": model.state_dict()}, final_path)
    logger.info("Training complete", final_model=str(final_path))

    if settings.wandb_api_key:
        wandb.finish()


if __name__ == "__main__":
    train()
