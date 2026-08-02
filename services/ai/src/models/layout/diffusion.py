"""Layout Diffusion Model.

A transformer-based U-Net diffusion model that generates floor plans
from room adjacency graphs and text/style embeddings.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Any


class SinusoidalPositionEmbedding(nn.Module):
    """Sinusoidal embeddings for diffusion timesteps."""

    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        half_dim = self.dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, device=timesteps.device) * -emb)
        emb = timesteps[:, None] * emb[None, :]
        emb = torch.cat([torch.sin(emb), torch.cos(emb)], dim=-1)
        return emb


class GraphConditioningEncoder(nn.Module):
    """Encodes room adjacency graph into conditioning vectors for the diffusion model."""

    def __init__(self, num_room_types: int = 12, hidden_dim: int = 256, max_rooms: int = 20):
        super().__init__()
        self.room_embed = nn.Embedding(num_room_types, hidden_dim)
        self.pos_embed = nn.Linear(4, hidden_dim)  # bounding box (x, y, w, h)
        self.adjacency_encoder = nn.Linear(max_rooms, hidden_dim)
        self.fusion = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=8, batch_first=True),
            num_layers=4,
        )
        self.output_proj = nn.Linear(hidden_dim, hidden_dim)

    def forward(
        self,
        room_types: torch.Tensor,  # (B, max_rooms)
        bboxes: torch.Tensor,      # (B, max_rooms, 4)
        adjacency: torch.Tensor,   # (B, max_rooms, max_rooms)
        mask: torch.Tensor,        # (B, max_rooms) bool, True = valid room
    ) -> torch.Tensor:
        room_emb = self.room_embed(room_types)  # (B, max_rooms, hidden_dim)
        pos_emb = self.pos_embed(bboxes)        # (B, max_rooms, hidden_dim)
        adj_emb = self.adjacency_encoder(adjacency)  # (B, max_rooms, hidden_dim)

        combined = room_emb + pos_emb + adj_emb
        # Mask padding rooms
        combined = combined * mask.unsqueeze(-1).float()

        fused = self.fusion(combined, src_key_padding_mask=~mask)
        # Global average pooling over valid rooms
        pooled = (fused * mask.unsqueeze(-1).float()).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp(min=1)
        return self.output_proj(pooled)


class LayoutUNet(nn.Module):
    """U-Net backbone for the layout diffusion model."""

    def __init__(
        self,
        in_channels: int = 3,      # RGB plan image
        out_channels: int = 3,
        model_channels: int = 128,
        num_res_blocks: int = 2,
        attention_resolutions: tuple[int, ...] = (16, 8),
        channel_mult: tuple[int, ...] = (1, 2, 4, 8),
        num_heads: int = 8,
        cond_dim: int = 256,       # graph conditioning dimension
    ):
        super().__init__()
        self.model_channels = model_channels
        self.time_embed = SinusoidalPositionEmbedding(model_channels)
        self.time_proj = nn.Linear(model_channels, model_channels * 4)

        # Graph conditioning projection
        self.cond_proj = nn.Linear(cond_dim, model_channels * 4)

        # TODO: implement full U-Net with down/up blocks, residual connections, attention
        # This is a scaffold - the full architecture would be 500+ lines
        self.input_conv = nn.Conv2d(in_channels, model_channels, 3, padding=1)
        self.blocks = nn.ModuleList([
            ResBlock(model_channels, model_channels * 4, model_channels * 2),
            ResBlock(model_channels * 2, model_channels * 4, model_channels * 4),
        ])
        self.output_conv = nn.Conv2d(model_channels * 4, out_channels, 3, padding=1)

    def forward(
        self,
        x: torch.Tensor,           # (B, C, H, W) noisy layout image
        timesteps: torch.Tensor,   # (B,)
        graph_cond: torch.Tensor,  # (B, cond_dim) from GraphConditioningEncoder
    ) -> torch.Tensor:
        t_emb = self.time_embed(timesteps)
        t_emb = self.time_proj(t_emb)
        c_emb = self.cond_proj(graph_cond)
        emb = t_emb + c_emb  # (B, model_channels * 4)

        h = self.input_conv(x)
        for block in self.blocks:
            h = block(h, emb)
        return self.output_conv(h)


class ResBlock(nn.Module):
    """Residual block with time/graph conditioning via adaptive group norm."""

    def __init__(self, in_channels: int, cond_dim: int, out_channels: int | None = None):
        super().__init__()
        out_channels = out_channels or in_channels
        self.norm1 = nn.GroupNorm(32, in_channels)
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1)
        self.norm2 = nn.GroupNorm(32, out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1)
        self.shortcut = nn.Conv2d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()
        self.cond_proj = nn.Linear(cond_dim, out_channels * 2)  # scale + shift

    def forward(self, x: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        scale, shift = self.cond_proj(cond)[:, :, None, None].chunk(2, dim=1)
        h = h * (1 + scale) + shift
        h = F.silu(h)
        h = self.conv1(h)
        h = self.norm2(h)
        h = F.silu(h)
        h = self.conv2(h)
        return h + self.shortcut(x)


class LayoutDiffusionModel(nn.Module):
    """Full diffusion model with forward/backward diffusion."""

    def __init__(self, num_train_timesteps: int = 1000):
        super().__init__()
        self.num_train_timesteps = num_train_timesteps
        self.unet = LayoutUNet()
        self.graph_encoder = GraphConditioningEncoder()

        # Precompute noise schedule (linear beta schedule)
        betas = torch.linspace(1e-4, 0.02, num_train_timesteps)
        alphas = 1.0 - betas
        alphas_cumprod = torch.cumprod(alphas, dim=0)
        self.register_buffer("betas", betas)
        self.register_buffer("alphas", alphas)
        self.register_buffer("alphas_cumprod", alphas_cumprod)
        self.register_buffer("sqrt_alphas_cumprod", torch.sqrt(alphas_cumprod))
        self.register_buffer("sqrt_one_minus_alphas_cumprod", torch.sqrt(1.0 - alphas_cumprod))

    def forward(
        self,
        x0: torch.Tensor,          # clean layout image (B, C, H, W)
        room_types: torch.Tensor,
        bboxes: torch.Tensor,
        adjacency: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        """Training forward pass: add noise and predict it."""
        batch_size = x0.size(0)
        device = x0.device

        # Sample random timesteps
        t = torch.randint(0, self.num_train_timesteps, (batch_size,), device=device)

        # Sample noise
        noise = torch.randn_like(x0)

        # Forward diffusion: x_t = sqrt(alpha_t) * x_0 + sqrt(1 - alpha_t) * noise
        sqrt_alpha_t = self.sqrt_alphas_cumprod[t].view(-1, 1, 1, 1)
        sqrt_one_minus_alpha_t = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1, 1, 1)
        xt = sqrt_alpha_t * x0 + sqrt_one_minus_alpha_t * noise

        # Condition on graph
        graph_cond = self.graph_encoder(room_types, bboxes, adjacency, mask)

        # Predict noise
        pred_noise = self.unet(xt, t, graph_cond)
        return F.mse_loss(pred_noise, noise)

    @torch.no_grad()
    def generate(
        self,
        room_types: torch.Tensor,
        bboxes: torch.Tensor,
        adjacency: torch.Tensor,
        mask: torch.Tensor,
        shape: tuple[int, ...] = (1, 3, 256, 256),
        num_inference_steps: int = 50,
    ) -> torch.Tensor:
        """DDPM sampling: generate layout from noise."""
        device = room_types.device
        xt = torch.randn(shape, device=device)
        graph_cond = self.graph_encoder(room_types, bboxes, adjacency, mask)

        # DDPM sampling with fewer steps (simple approach)
        step_ratio = self.num_train_timesteps // num_inference_steps
        timesteps = torch.arange(0, self.num_train_timesteps, step_ratio, device=device).flip(0)

        for t in timesteps:
            t_batch = t.expand(shape[0])
            pred_noise = self.unet(xt, t_batch, graph_cond)

            alpha_t = self.alphas[t]
            alpha_cumprod_t = self.alphas_cumprod[t]
            beta_t = self.betas[t]

            # Predict x_0
            pred_x0 = (xt - torch.sqrt(1 - alpha_cumprod_t) * pred_noise) / torch.sqrt(alpha_cumprod_t)

            # Compute x_{t-1}
            if t > 0:
                noise = torch.randn_like(xt) if t > 1 else torch.zeros_like(xt)
                alpha_cumprod_prev = self.alphas_cumprod[t - 1]
                variance = beta_t * (1 - alpha_cumprod_prev) / (1 - alpha_cumprod_t)
                xt = torch.sqrt(alpha_cumprod_prev) * pred_x0 + torch.sqrt(1 - alpha_cumprod_prev - variance) * pred_noise + torch.sqrt(variance.clamp(min=0)) * noise
            else:
                xt = pred_x0

        return xt.clamp(-1, 1)
