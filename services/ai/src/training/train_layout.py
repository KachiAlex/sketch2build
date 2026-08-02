"""Training script for the Layout Diffusion Model.

Trains a transformer-based U-Net diffusion model to generate floor plans
from room adjacency graphs using synthetic data.
"""

import argparse
import structlog
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import get_cosine_schedule_with_warmup
import wandb

from src.config import get_settings
from src.models.layout.diffusion import LayoutDiffusionModel
from src.training.data.dataset import LayoutDataset

logger = structlog.get_logger()
settings = get_settings()


def parse_args():
    parser = argparse.ArgumentParser(description="Train Layout Diffusion Model")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="./output/layout_diffusion")
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--num_epochs", type=int, default=100)
    parser.add_argument("--warmup_steps", type=int, default=2000)
    parser.add_argument("--image_size", type=int, default=256)
    parser.add_argument("--num_train_timesteps", type=int, default=1000)
    parser.add_argument("--val_every", type=int, default=2000)
    parser.add_argument("--save_every", type=int, default=10000)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--resume", type=str, default=None)
    return parser.parse_args()


def collate_fn(batch: list) -> dict:
    return {
        "x0": torch.stack([b["x0"] for b in batch]),
        "room_types": torch.stack([b["room_types"] for b in batch]),
        "bboxes": torch.stack([b["bboxes"] for b in batch]),
        "mask": torch.stack([b["mask"] for b in batch]),
        "adjacency": torch.stack([b["adjacency"] for b in batch]),
    }


@torch.no_grad()
def validate(model: nn.Module, dataloader: DataLoader, device: str) -> dict:
    model.eval()
    total_loss = 0.0
    total_samples = 0

    for batch in dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        loss = model(batch["x0"], batch["room_types"], batch["bboxes"], batch["adjacency"], batch["mask"])
        total_loss += loss.item() * batch["x0"].size(0)
        total_samples += batch["x0"].size(0)

    # Generate a few samples for visualization
    batch = next(iter(dataloader))
    batch = {k: v.to(device) for k, v in batch.items()}
    generated = model.generate(
        batch["room_types"][:4],
        batch["bboxes"][:4],
        batch["adjacency"][:4],
        batch["mask"][:4],
        shape=(4, 3, 256, 256),
        num_inference_steps=50,
    )

    # Save sample images
    # TODO: log to W&B or save to disk

    model.train()
    return {"val_loss": total_loss / total_samples}


def train():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Starting layout training", device=device, args=args)

    if settings.wandb_api_key:
        wandb.init(
            project=settings.wandb_project,
            entity=settings.wandb_entity,
            name="layout_diffusion",
            config=vars(args),
        )

    # Data
    train_dataset = LayoutDataset(
        metadata_path=Path(args.data_dir) / "metadata.json",
        image_dir=args.data_dir,
        split="train",
        image_size=args.image_size,
    )
    val_dataset = LayoutDataset(
        metadata_path=Path(args.data_dir) / "metadata.json",
        image_dir=args.data_dir,
        split="val",
        image_size=args.image_size,
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
    model = LayoutDiffusionModel(num_train_timesteps=args.num_train_timesteps).to(device)

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
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}

            optimizer.zero_grad()
            loss = model(batch["x0"], batch["room_types"], batch["bboxes"], batch["adjacency"], batch["mask"])
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
                )
                if settings.wandb_api_key:
                    wandb.log({"train/loss": loss.item(), "train/lr": scheduler.get_last_lr()[0]}, step=global_step)

            if global_step % args.val_every == 0:
                val_metrics = validate(model, val_loader, device)
                logger.info("Validation", step=global_step, **val_metrics)
                if settings.wandb_api_key:
                    wandb.log({f"val/{k}": v for k, v in val_metrics.items()}, step=global_step)

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
