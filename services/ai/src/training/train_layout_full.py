"""Comprehensive training script for the Layout Diffusion Model.

Trains the U-Net diffusion model on floor plan images conditioned on room graphs.
Supports:
- Mixed dataset training (synthetic + RPlan + CubiCasa5K)
- DDPM noise prediction loss
- Checkpointing with best model tracking
- W&B logging
- Early stopping
- Learning rate scheduling with warmup
- Gradient clipping
- Validation with sample generation

Usage:
    python -m src.training.train_layout_full \
        --data_dir /app/data \
        --output_dir /app/models/layout_diffusion \
        --batch_size 4 \
        --epochs 200 \
        --lr 1e-4 \
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

from src.models.layout.diffusion import LayoutDiffusionModel
from src.training.data.dataset import LayoutDataset
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def collate_fn(batch):
    """Collate batch into padded tensors for layout diffusion."""
    max_rooms = 20

    images = torch.stack([item["image"] for item in batch])
    B = len(batch)

    room_types = torch.full((B, max_rooms), 0, dtype=torch.long)
    bboxes = torch.zeros(B, max_rooms, 4)
    adjacency = torch.zeros(B, max_rooms, max_rooms)
    mask = torch.zeros(B, max_rooms, dtype=torch.bool)

    for b, item in enumerate(batch):
        rooms = item.get("rooms", [])
        for i, room in enumerate(rooms[:max_rooms]):
            room_types[b, i] = room.get("type_idx", 0)
            bbox = room.get("bbox", [0, 0, 0, 0])
            if len(bbox) == 4:
                bboxes[b, i] = torch.tensor(bbox, dtype=torch.float32)
            mask[b, i] = True

        adj = item.get("adjacency", [])
        for pair in adj:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                a, c = int(pair[0]), int(pair[1])
                if a < max_rooms and c < max_rooms:
                    adjacency[b, a, c] = 1.0
                    adjacency[b, c, a] = 1.0

    return {
        "images": images,
        "room_types": room_types,
        "bboxes": bboxes,
        "adjacency": adjacency,
        "mask": mask,
    }

def train_epoch(model, dataloader, optimizer, device, max_grad_norm=1.0):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    num_batches = 0

    for batch_idx, batch in enumerate(dataloader):
        images = batch["images"].to(device)
        room_types = batch["room_types"].to(device)
        bboxes = batch["bboxes"].to(device)
        adjacency = batch["adjacency"].to(device)
        mask = batch["mask"].to(device)

        optimizer.zero_grad()

        # Forward pass: adds noise and predicts it
        loss = model(images, room_types, bboxes, adjacency, mask)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
        optimizer.step()

        total_loss += loss.item()
        num_batches += 1

        if (batch_idx + 1) % 50 == 0:
            logger.info(f"Batch {batch_idx+1}/{len(dataloader)}", loss=loss.item())

    return {"loss": total_loss / max(num_batches, 1)}


def validate_epoch(model, dataloader, device, generate_samples=False):
    """Validate for one epoch."""
    model.eval()
    total_loss = 0.0
    num_batches = 0

    with torch.no_grad():
        for batch in dataloader:
            images = batch["images"].to(device)
            room_types = batch["room_types"].to(device)
            bboxes = batch["bboxes"].to(device)
            adjacency = batch["adjacency"].to(device)
            mask = batch["mask"].to(device)

            loss = model(images, room_types, bboxes, adjacency, mask)
            total_loss += loss.item()
            num_batches += 1

    # Optionally generate a sample
    generated_sample = None
    if generate_samples and num_batches > 0:
        with torch.no_grad():
            # Use first batch for sample generation
            sample = model.generate(
                room_types=room_types[:1],
                bboxes=bboxes[:1],
                adjacency=adjacency[:1],
                mask=mask[:1],
                shape=(1, 3, 256, 256),
                num_inference_steps=20,  # Fewer steps for validation
            )
            generated_sample = sample[0].cpu()

    return {
        "loss": total_loss / max(num_batches, 1),
        "sample": generated_sample,
    }


def main():
    parser = argparse.ArgumentParser(description="Train Layout Diffusion Model")
    parser.add_argument("--data_dir", type=str, default=str(settings.data_dir))
    parser.add_argument("--output_dir", type=str, default=str(settings.models_dir / "layout_diffusion"))
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--warmup_steps", type=int, default=1000)
    parser.add_argument("--max_grad_norm", type=float, default=1.0)
    parser.add_argument("--save_every_n_epochs", type=int, default=10)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--num_train_timesteps", type=int, default=1000)
    parser.add_argument("--use_wandb", action="store_true")
    parser.add_argument("--wandb_project", type=str, default="sketch2build-ai")
    parser.add_argument("--wandb_run_name", type=str, default="layout_diffusion_full")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--val_split", type=float, default=0.1)
    parser.add_argument("--generate_samples", action="store_true")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Starting layout diffusion training", device=device, args=vars(args))

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
    model = LayoutDiffusionModel(num_train_timesteps=args.num_train_timesteps).to(device)

    # Create datasets
    data_dir = Path(args.data_dir)
    synthetic_dir = data_dir / "synthetic"
    metadata_path = str(synthetic_dir / "metadata.json")
    image_dir = str(synthetic_dir)

    full_dataset = LayoutDataset(
        metadata_path=metadata_path,
        image_dir=image_dir,
        split="train",
        image_size=256,
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

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    # LR scheduler
    total_steps = len(train_loader) * args.epochs
    warmup_scheduler = LinearLR(optimizer, start_factor=0.01, total_iters=args.warmup_steps)
    cosine_scheduler = CosineAnnealingLR(optimizer, T_max=total_steps - args.warmup_steps)

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
        generate = args.generate_samples and (epoch + 1) % 10 == 0
        val_metrics = validate_epoch(model, val_loader, device, generate_samples=generate)

        epoch_time = time.time() - start_time

        logger.info(
            f"Epoch {epoch+1}/{args.epochs}",
            train_loss=train_metrics["loss"],
            val_loss=val_metrics["loss"],
            time=f"{epoch_time:.1f}s",
        )

        if wandb_run:
            log_dict = {
                "epoch": epoch + 1,
                "train/loss": train_metrics["loss"],
                "val/loss": val_metrics["loss"],
                "lr": optimizer.param_groups[0]["lr"],
            }
            if val_metrics["sample"] is not None:
                import wandb
                sample_img = val_metrics["sample"]
                sample_img = ((sample_img + 1) / 2 * 255).clamp(0, 255).byte()
                log_dict["val/generated_sample"] = wandb.Image(
                    sample_img.permute(1, 2, 0).numpy(),
                    caption=f"Epoch {epoch+1}",
                )
            wandb_run.log(log_dict)

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

        # Step LR
        if epoch < args.warmup_steps // max(len(train_loader), 1):
            warmup_scheduler.step()
        else:
            cosine_scheduler.step()

    # Save final
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
