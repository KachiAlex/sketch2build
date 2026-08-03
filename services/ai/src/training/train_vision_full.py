"""Comprehensive training script for the Sketch-to-Graph Vision Encoder.

Trains the cross-attention room detection head on top of CLIP vision encoder
using synthetic + real floor plan data. Supports:
- Mixed dataset training (synthetic + RPlan + CubiCasa5K)
- Multi-task loss (presence + type + bbox + adjacency)
- Checkpointing with best model tracking
- W&B logging
- Early stopping
- Learning rate scheduling with warmup
- Gradient clipping
- Validation with metrics

Usage:
    python -m src.training.train_vision_full \
        --data_dir /app/data \
        --output_dir /app/models/vision_encoder \
        --batch_size 8 \
        --epochs 100 \
        --lr 1e-4 \
        --warmup_steps 1000 \
        --use_wandb
"""

import argparse
import os
import time
import structlog
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR

from src.models.vision.sketch_encoder import SketchEncoderModel
from src.training.data.dataset import SketchDataset
from src.config import get_settings
from transformers import CLIPProcessor

logger = structlog.get_logger()
settings = get_settings()


def collate_fn(batch):
    """Collate batch into padded tensors for multi-room prediction."""
    max_rooms = 20

    # SketchDataset already returns processed tensors
    pixel_values = torch.stack([item["pixel_values"] for item in batch])

    B = len(batch)
    room_presence = torch.zeros(B, max_rooms)
    room_types = torch.full((B, max_rooms), -1, dtype=torch.long)  # -1 = padding
    bboxes = torch.zeros(B, max_rooms, 4)
    adjacency = torch.zeros(B, max_rooms, max_rooms)
    mask = torch.zeros(B, max_rooms, dtype=torch.bool)

    for b, item in enumerate(batch):
        # Dataset returns mask and room_types already padded to max_rooms
        item_mask = item.get("mask")
        if item_mask is not None:
            mask[b] = item_mask
            room_types[b] = item["room_types"]
            bboxes[b] = item["bboxes"]
            room_presence[b] = item_mask.float()
            adjacency[b] = item["adjacency"]
        else:
            # Fallback: extract from rooms list
            rooms = item.get("rooms", [])
            for i, room in enumerate(rooms[:max_rooms]):
                room_type = room.get("type", "living")
                type_idx = room_type_to_idx.get(room_type, 0)
                room_types[b, i] = type_idx
                room_presence[b, i] = 1.0
                mask[b, i] = True
                bbox = room.get("bbox", [0, 0, 0, 0])
                if len(bbox) == 4:
                    bboxes[b, i] = torch.tensor(bbox, dtype=torch.float32)

            adj = item.get("adjacency", [])
            for pair in adj:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    a, c = int(pair[0]), int(pair[1])
                    if a < max_rooms and c < max_rooms:
                        adjacency[b, a, c] = 1.0
                        adjacency[b, c, a] = 1.0

    return {
        "pixel_values": pixel_values,
        "room_presence": room_presence,
        "room_types": room_types,
        "bboxes": bboxes,
        "adjacency": adjacency,
        "mask": mask,
    }


def train_epoch(model, dataloader, optimizer, device, max_grad_norm=1.0):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    total_presence = 0.0
    total_type = 0.0
    total_bbox = 0.0
    total_adj = 0.0
    num_batches = 0

    for batch_idx, batch in enumerate(dataloader):
        pixel_values = batch["pixel_values"].to(device)
        targets = {
            "room_presence": batch["room_presence"].to(device),
            "room_types": batch["room_types"].to(device),
            "bboxes": batch["bboxes"].to(device),
            "adjacency": batch["adjacency"].to(device),
            "mask": batch["mask"].to(device),
        }

        optimizer.zero_grad()

        outputs = model(pixel_values)
        losses = model.compute_loss(outputs, targets)

        losses["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
        optimizer.step()

        total_loss += losses["total"].item()
        total_presence += losses["presence"].item()
        total_type += losses["type"].item()
        total_bbox += losses["bbox"].item()
        total_adj += losses["adjacency"].item()
        num_batches += 1

    return {
        "loss": total_loss / max(num_batches, 1),
        "presence": total_presence / max(num_batches, 1),
        "type": total_type / max(num_batches, 1),
        "bbox": total_bbox / max(num_batches, 1),
        "adjacency": total_adj / max(num_batches, 1),
    }


def validate_epoch(model, dataloader, device):
    """Validate for one epoch."""
    model.eval()
    total_loss = 0.0
    num_batches = 0
    correct_types = 0
    total_rooms = 0

    with torch.no_grad():
        for batch in dataloader:
            pixel_values = batch["pixel_values"].to(device)
            targets = {
                "room_presence": batch["room_presence"].to(device),
                "room_types": batch["room_types"].to(device),
                "bboxes": batch["bboxes"].to(device),
                "adjacency": batch["adjacency"].to(device),
                "mask": batch["mask"].to(device),
            }

            outputs = model(pixel_values)
            losses = model.compute_loss(outputs, targets)
            total_loss += losses["total"].item()
            num_batches += 1

            # Type accuracy
            valid = targets["room_types"] >= 0
            if valid.any():
                pred_types = outputs["room_type_logits"][valid].argmax(dim=-1)
                true_types = targets["room_types"][valid]
                correct_types += (pred_types == true_types).sum().item()
                total_rooms += valid.sum().item()

    return {
        "loss": total_loss / max(num_batches, 1),
        "type_accuracy": correct_types / max(total_rooms, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Train Sketch-to-Graph Vision Encoder")
    parser.add_argument("--data_dir", type=str, default=str(settings.data_dir))
    parser.add_argument("--output_dir", type=str, default=str(settings.models_dir / "vision_encoder"))
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--warmup_steps", type=int, default=1000)
    parser.add_argument("--max_grad_norm", type=float, default=1.0)
    parser.add_argument("--save_every_n_epochs", type=int, default=5)
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience")
    parser.add_argument("--freeze_backbone", action="store_true", help="Freeze CLIP backbone")
    parser.add_argument("--use_wandb", action="store_true")
    parser.add_argument("--wandb_project", type=str, default="sketch2build-ai")
    parser.add_argument("--wandb_run_name", type=str, default="vision_encoder_full")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--val_split", type=float, default=0.1)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Starting training", device=device, args=vars(args))

    # W&B
    wandb_run = None
    if args.use_wandb:
        try:
            import wandb
            wandb_run = wandb.init(
                project=args.wandb_project,
                name=args.wandb_run_name,
                config=vars(args),
            )
        except Exception as e:
            logger.warning("W&B init failed", error=str(e))

    # Create model
    model = SketchEncoderModel(
        pretrained_model=settings.vision_model_name,
        freeze_backbone=args.freeze_backbone,
    ).to(device)

    # Create CLIP processor for image preprocessing
    processor = CLIPProcessor.from_pretrained(settings.vision_model_name)

    # Create datasets
    data_dir = Path(args.data_dir)
    synthetic_dir = data_dir / "synthetic"
    metadata_path = str(synthetic_dir / "metadata.json")
    image_dir = str(synthetic_dir)

    full_dataset = SketchDataset(
        metadata_path=metadata_path,
        image_dir=image_dir,
        processor=processor,
        split="train",
        max_rooms=20,
    )

    val_size = int(len(full_dataset) * args.val_split)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size]
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

    logger.info("Dataset loaded", train=train_size, val=val_size)

    # Optimizer with weight decay
    optimizer = AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    # LR scheduler: warmup + cosine annealing
    total_steps = len(train_loader) * args.epochs
    warmup_scheduler = LinearLR(
        optimizer,
        start_factor=0.01,
        total_iters=args.warmup_steps,
    )
    cosine_scheduler = CosineAnnealingLR(
        optimizer,
        T_max=total_steps - args.warmup_steps,
    )

    # Training loop
    best_val_loss = float("inf")
    patience_counter = 0
    os.makedirs(args.output_dir, exist_ok=True)

    for epoch in range(args.epochs):
        start_time = time.time()

        # Train
        train_metrics = train_epoch(
            model, train_loader, optimizer, device, args.max_grad_norm
        )

        # Validate
        val_metrics = validate_epoch(model, val_loader, device)

        epoch_time = time.time() - start_time

        logger.info(
            f"Epoch {epoch+1}/{args.epochs}",
            train_loss=train_metrics["loss"],
            val_loss=val_metrics["loss"],
            val_type_acc=val_metrics["type_accuracy"],
            time=f"{epoch_time:.1f}s",
        )

        if wandb_run:
            wandb_run.log({
                "epoch": epoch + 1,
                "train/loss": train_metrics["loss"],
                "train/presence_loss": train_metrics["presence"],
                "train/type_loss": train_metrics["type"],
                "train/bbox_loss": train_metrics["bbox"],
                "train/adjacency_loss": train_metrics["adjacency"],
                "val/loss": val_metrics["loss"],
                "val/type_accuracy": val_metrics["type_accuracy"],
                "lr": optimizer.param_groups[0]["lr"],
            })

        # Save checkpoint
        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            patience_counter = 0
            model.save_checkpoint(
                os.path.join(args.output_dir, "best.pt"),
                optimizer=optimizer,
                epoch=epoch + 1,
                best_loss=best_val_loss,
            )
            logger.info("New best model saved", val_loss=best_val_loss)
        else:
            patience_counter += 1

        # Periodic checkpoint
        if (epoch + 1) % args.save_every_n_epochs == 0:
            model.save_checkpoint(
                os.path.join(args.output_dir, f"checkpoint_epoch_{epoch+1}.pt"),
                optimizer=optimizer,
                epoch=epoch + 1,
                best_loss=best_val_loss,
            )

        # Early stopping
        if patience_counter >= args.patience:
            logger.info("Early stopping triggered", epoch=epoch + 1, patience=args.patience)
            break

        # Step LR scheduler
        if epoch < args.warmup_steps // max(len(train_loader), 1):
            warmup_scheduler.step()
        else:
            cosine_scheduler.step()

    # Save final model
    model.save_checkpoint(
        os.path.join(args.output_dir, "final.pt"),
        optimizer=optimizer,
        epoch=args.epochs,
        best_loss=best_val_loss,
    )

    logger.info("Training complete", best_val_loss=best_val_loss, output_dir=args.output_dir)

    if wandb_run:
        wandb_run.finish()


if __name__ == "__main__":
    main()
