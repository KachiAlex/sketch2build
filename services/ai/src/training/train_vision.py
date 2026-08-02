"""Training script for the Sketch-to-Graph Vision Encoder.

Fine-tunes a CLIP vision backbone with a custom RoomGraphHead
to extract room types, bounding boxes, and adjacency from sketches.
"""

import argparse
import structlog
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import CLIPProcessor, get_cosine_schedule_with_warmup
import wandb

from src.config import get_settings
from src.models.vision.sketch_encoder import SketchEncoderModel
from src.training.data.dataset import SketchDataset

logger = structlog.get_logger()
settings = get_settings()


def parse_args():
    parser = argparse.ArgumentParser(description="Train Sketch-to-Graph Vision Encoder")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to synthetic dataset directory")
    parser.add_argument("--output_dir", type=str, default="./output/vision_encoder", help="Output directory for checkpoints")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--num_epochs", type=int, default=50)
    parser.add_argument("--warmup_steps", type=int, default=1000)
    parser.add_argument("--freeze_backbone_epochs", type=int, default=5, help="Freeze CLIP backbone for N epochs")
    parser.add_argument("--val_every", type=int, default=1000, help="Run validation every N steps")
    parser.add_argument("--save_every", type=int, default=5000, help="Save checkpoint every N steps")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint to resume from")
    return parser.parse_args()


def collate_fn(batch: list) -> dict:
    """Custom collate for variable-length room graphs."""
    return {
        "pixel_values": torch.stack([b["pixel_values"] for b in batch]),
        "room_types": torch.stack([b["room_types"] for b in batch]),
        "bboxes": torch.stack([b["bboxes"] for b in batch]),
        "mask": torch.stack([b["mask"] for b in batch]),
        "adjacency": torch.stack([b["adjacency"] for b in batch]),
        "is_valid": torch.stack([b["is_valid"] for b in batch]),
    }


def compute_loss(outputs: dict, batch: dict) -> torch.Tensor:
    """Multi-task loss: room type + bbox + adjacency + validity."""
    batch_size = batch["pixel_values"].size(0)

    # Room type classification (cross-entropy per room, masked)
    room_type_loss = 0.0
    for i in range(batch_size):
        valid_mask = batch["mask"][i]
        if valid_mask.sum() == 0:
            continue
        logits = outputs["room_type_logits"][i].unsqueeze(0).expand(valid_mask.sum(), -1)
        targets = batch["room_types"][i][valid_mask]
        room_type_loss += nn.functional.cross_entropy(logits, targets)
    room_type_loss = room_type_loss / batch_size

    # Bounding box regression (MSE, masked)
    bbox_loss = nn.functional.mse_loss(
        outputs["bbox_logits"] * batch["mask"].unsqueeze(-1).float(),
        batch["bboxes"] * batch["mask"].unsqueeze(-1).float(),
    )

    # Adjacency classification (BCE, masked)
    adj_mask = batch["mask"].unsqueeze(-1) & batch["mask"].unsqueeze(1)
    adj_targets = batch["adjacency"] * adj_mask.float()
    adj_logits = outputs["adjacency_logits"] * adj_mask.float()
    adjacency_loss = nn.functional.binary_cross_entropy_with_logits(adj_logits, adj_targets)

    # Validity classification (BCE)
    validity_loss = nn.functional.binary_cross_entropy_with_logits(
        outputs["room_presence_logits"].mean(dim=1),  # proxy for plan validity
        batch["is_valid"],
    )

    total_loss = room_type_loss + 0.5 * bbox_loss + 0.3 * adjacency_loss + 0.1 * validity_loss
    return total_loss, {
        "room_type": room_type_loss.item(),
        "bbox": bbox_loss.item(),
        "adjacency": adjacency_loss.item(),
        "validity": validity_loss.item(),
    }


@torch.no_grad()
def validate(model: nn.Module, dataloader: DataLoader, device: str) -> dict:
    model.eval()
    total_loss = 0.0
    total_samples = 0

    for batch in dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(batch["pixel_values"])
        loss, _ = compute_loss(outputs, batch)
        total_loss += loss.item() * batch["pixel_values"].size(0)
        total_samples += batch["pixel_values"].size(0)

    return {"val_loss": total_loss / total_samples}


def train():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Starting training", device=device, args=args)

    # W&B setup
    if settings.wandb_api_key:
        wandb.init(
            project=settings.wandb_project,
            entity=settings.wandb_entity,
            name="vision_encoder",
            config=vars(args),
        )

    # Data
    processor = CLIPProcessor.from_pretrained(settings.vision_model_name)
    train_dataset = SketchDataset(
        metadata_path=Path(args.data_dir) / "metadata.json",
        image_dir=args.data_dir,
        processor=processor,
        split="train",
    )
    val_dataset = SketchDataset(
        metadata_path=Path(args.data_dir) / "metadata.json",
        image_dir=args.data_dir,
        processor=processor,
        split="val",
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
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

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    total_steps = len(train_loader) * args.num_epochs
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=total_steps,
    )

    # Resume
    start_step = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_step = checkpoint.get("step", 0)
        logger.info("Resumed from checkpoint", step=start_step, path=args.resume)

    # Training loop
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model.train()
    global_step = start_step

    for epoch in range(args.num_epochs):
        # Unfreeze backbone after initial warmup
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
                    wandb.log({"train/loss": loss.item(), **{f"train/{k}": v for k, v in loss_components.items()}, "train/lr": scheduler.get_last_lr()[0]}, step=global_step)

            # Validation
            if global_step % args.val_every == 0:
                val_metrics = validate(model, val_loader, device)
                logger.info("Validation", step=global_step, **val_metrics)
                if settings.wandb_api_key:
                    wandb.log({f"val/{k}": v for k, v in val_metrics.items()}, step=global_step)
                model.train()

            # Save checkpoint
            if global_step % args.save_every == 0:
                checkpoint_path = output_dir / f"checkpoint_step_{global_step}.pt"
                torch.save({
                    "step": global_step,
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                }, checkpoint_path)
                logger.info("Checkpoint saved", path=str(checkpoint_path))

    # Final save
    final_path = output_dir / "final_model.pt"
    torch.save({"model_state_dict": model.state_dict()}, final_path)
    logger.info("Training complete", final_model=str(final_path))

    if settings.wandb_api_key:
        wandb.finish()


if __name__ == "__main__":
    train()
