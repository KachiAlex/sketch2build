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


class AttentionBlock(nn.Module):
    """Self-attention block for spatial features."""

    def __init__(self, channels: int, num_heads: int = 8):
        super().__init__()
        self.norm = nn.GroupNorm(32, channels)
        self.q = nn.Conv2d(channels, channels, 1)
        self.k = nn.Conv2d(channels, channels, 1)
        self.v = nn.Conv2d(channels, channels, 1)
        self.proj_out = nn.Conv2d(channels, channels, 1)
        self.num_heads = num_heads
        self.scale = (channels // num_heads) ** -0.5

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        h = self.norm(x)
        q = self.q(h).reshape(B, self.num_heads, C // self.num_heads, H * W)
        k = self.k(h).reshape(B, self.num_heads, C // self.num_heads, H * W)
        v = self.v(h).reshape(B, self.num_heads, C // self.num_heads, H * W)

        attn = torch.einsum("bhdn,bhem->bhnm", q, k) * self.scale
        attn = attn.softmax(dim=-1)

        out = torch.einsum("bhnm,bhdn->bhdn", attn, v)
        out = out.reshape(B, C, H, W)
        out = self.proj_out(out)
        return x + out


class DownBlock(nn.Module):
    """Downsampling block: ResBlocks + optional attention + downsample."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        cond_dim: int,
        num_res_blocks: int = 2,
        use_attention: bool = False,
        num_heads: int = 8,
        downsample: bool = True,
    ):
        super().__init__()
        self.res_blocks = nn.ModuleList()
        self.attentions = nn.ModuleList()

        for i in range(num_res_blocks):
            ic = in_channels if i == 0 else out_channels
            self.res_blocks.append(ResBlock(ic, cond_dim, out_channels))
            if use_attention:
                self.attentions.append(AttentionBlock(out_channels, num_heads))
            else:
                self.attentions.append(nn.Identity())

        self.downsample = nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1) if downsample else None

    def forward(self, x: torch.Tensor, cond: torch.Tensor) -> tuple[torch.Tensor, list[torch.Tensor]]:
        skips = []
        for res, attn in zip(self.res_blocks, self.attentions):
            x = res(x, cond)
            x = attn(x)
            skips.append(x)
        if self.downsample:
            x = self.downsample(x)
        return x, skips


class UpBlock(nn.Module):
    """Upsampling block: ResBlocks + optional attention + upsample + skip connections."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        cond_dim: int,
        skip_channels: int,
        num_res_blocks: int = 2,
        use_attention: bool = False,
        num_heads: int = 8,
        upsample: bool = True,
    ):
        super().__init__()
        self.res_blocks = nn.ModuleList()
        self.attentions = nn.ModuleList()

        for i in range(num_res_blocks):
            ic = in_channels + skip_channels if i == 0 else out_channels + skip_channels
            self.res_blocks.append(ResBlock(ic, cond_dim, out_channels))
            if use_attention:
                self.attentions.append(AttentionBlock(out_channels, num_heads))
            else:
                self.attentions.append(nn.Identity())

        self.upsample = nn.ConvTranspose2d(out_channels, out_channels, 4, stride=2, padding=1) if upsample else None

    def forward(self, x: torch.Tensor, cond: torch.Tensor, skips: list[torch.Tensor]) -> torch.Tensor:
        for res, attn, skip in zip(self.res_blocks, self.attentions, reversed(skips)):
            x = torch.cat([x, skip], dim=1)
            x = res(x, cond)
            x = attn(x)
        if self.upsample:
            x = self.upsample(x)
        return x


class LayoutUNet(nn.Module):
    """Full U-Net backbone for the layout diffusion model.

    Encoder-decoder with skip connections, attention at specified resolutions,
    and adaptive conditioning (timestep + graph) via ResBlocks.
    """

    def __init__(
        self,
        in_channels: int = 3,
        out_channels: int = 3,
        model_channels: int = 128,
        num_res_blocks: int = 2,
        attention_resolutions: tuple[int, ...] = (32,),
        channel_mult: tuple[int, ...] = (1, 2, 4, 4),
        num_heads: int = 8,
        cond_dim: int = 256,
        image_size: int = 256,
    ):
        super().__init__()
        self.model_channels = model_channels
        self.image_size = image_size

        # Time + condition embedding
        self.time_embed = SinusoidalPositionEmbedding(model_channels)
        self.time_proj = nn.Sequential(
            nn.Linear(model_channels, model_channels * 4),
            nn.SiLU(),
            nn.Linear(model_channels * 4, model_channels * 4),
        )
        self.cond_proj = nn.Sequential(
            nn.Linear(cond_dim, model_channels * 4),
            nn.SiLU(),
            nn.Linear(model_channels * 4, model_channels * 4),
        )

        # Input convolution
        self.input_conv = nn.Conv2d(in_channels, model_channels, 3, padding=1)

        # Determine which levels get attention
        # resolutions at each level: image_size // (2^level)
        levels = len(channel_mult)
        attention_levels = set()
        for level in range(levels):
            res = image_size // (2 ** level)
            if res in attention_resolutions:
                attention_levels.add(level)

        # Encoder (down blocks)
        self.down_blocks = nn.ModuleList()
        skip_channels_per_level = []
        channels = model_channels
        for level in range(levels):
            level_out = model_channels * channel_mult[level]
            use_attn = level in attention_levels
            downsample = level < levels - 1
            self.down_blocks.append(DownBlock(
                in_channels=channels,
                out_channels=level_out,
                cond_dim=model_channels * 4,
                num_res_blocks=num_res_blocks,
                use_attention=use_attn,
                num_heads=num_heads,
                downsample=downsample,
            ))
            skip_channels_per_level.append(level_out)
            channels = level_out

        # Middle block (always has attention)
        self.mid_block_1 = ResBlock(channels, model_channels * 4, channels)
        self.mid_attn = AttentionBlock(channels, num_heads)
        self.mid_block_2 = ResBlock(channels, model_channels * 4, channels)

        # Decoder (up blocks) — reversed order
        self.up_blocks = nn.ModuleList()
        for level in reversed(range(levels)):
            level_out = model_channels * channel_mult[level]
            use_attn = level in attention_levels
            upsample = level > 0
            self.up_blocks.append(UpBlock(
                in_channels=channels,
                out_channels=level_out,
                cond_dim=model_channels * 4,
                skip_channels=skip_channels_per_level[level],
                num_res_blocks=num_res_blocks,
                use_attention=use_attn,
                num_heads=num_heads,
                upsample=upsample,
            ))
            channels = level_out

        # Output normalization + convolution
        self.out_norm = nn.GroupNorm(32, channels)
        self.out_conv = nn.Conv2d(channels, out_channels, 3, padding=1)

    def forward(
        self,
        x: torch.Tensor,
        timesteps: torch.Tensor,
        graph_cond: torch.Tensor,
    ) -> torch.Tensor:
        # Embeddings
        t_emb = self.time_embed(timesteps)
        t_emb = self.time_proj(t_emb)
        c_emb = self.cond_proj(graph_cond)
        emb = t_emb + c_emb  # (B, model_channels * 4)

        # Input
        h = self.input_conv(x)

        # Encoder
        all_skips = []
        for down_block in self.down_blocks:
            h, skips = down_block(h, emb)
            all_skips.append(skips)

        # Middle
        h = self.mid_block_1(h, emb)
        h = self.mid_attn(h)
        h = self.mid_block_2(h, emb)

        # Decoder
        for up_block, skips in zip(self.up_blocks, reversed(all_skips)):
            h = up_block(h, emb, skips)

        # Output
        h = self.out_norm(h)
        h = F.silu(h)
        h = self.out_conv(h)
        return h


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
        h = F.silu(h)
        h = self.conv1(h)
        h = self.norm2(h)
        scale, shift = self.cond_proj(cond)[:, :, None, None].chunk(2, dim=1)
        h = h * (1 + scale) + shift
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

        # DDPM sampling with fewer steps
        step_ratio = self.num_train_timesteps // num_inference_steps
        timesteps = list(range(self.num_train_timesteps - 1, -1, -step_ratio))

        for i, t in enumerate(timesteps):
            t_tensor = torch.full((shape[0],), t, device=device, dtype=torch.long)
            pred_noise = self.unet(xt, t_tensor, graph_cond)

            alpha_cumprod_t = self.alphas_cumprod[t]
            beta_t = self.betas[t]

            # Predict x_0
            pred_x0 = (xt - torch.sqrt(1 - alpha_cumprod_t) * pred_noise) / torch.sqrt(alpha_cumprod_t)

            # Compute x_{t-1} using the previous timestep in the schedule
            if i < len(timesteps) - 1:
                t_prev = timesteps[i + 1]
                alpha_cumprod_prev = self.alphas_cumprod[t_prev]
                noise = torch.randn_like(xt)
                variance = beta_t * (1 - alpha_cumprod_prev) / (1 - alpha_cumprod_t)
                xt = torch.sqrt(alpha_cumprod_prev) * pred_x0 + torch.sqrt(1 - alpha_cumprod_prev - variance) * pred_noise + torch.sqrt(variance.clamp(min=0)) * noise
            else:
                xt = pred_x0

        return xt.clamp(-1, 1)

    def save_checkpoint(self, path: str, optimizer=None, epoch: int = 0, best_loss: float = float("inf")):
        """Save model checkpoint."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        checkpoint = {
            "model_state_dict": self.state_dict(),
            "epoch": epoch,
            "best_loss": best_loss,
            "num_train_timesteps": self.num_train_timesteps,
        }
        if optimizer:
            checkpoint["optimizer_state_dict"] = optimizer.state_dict()
        torch.save(checkpoint, path)

    def load_checkpoint(self, path: str, optimizer=None, device: str = "cpu") -> tuple[int, float]:
        """Load model checkpoint. Returns (epoch, best_loss)."""
        checkpoint = torch.load(path, map_location=device)
        self.load_state_dict(checkpoint["model_state_dict"])
        if optimizer and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        return checkpoint.get("epoch", 0), checkpoint.get("best_loss", float("inf"))
