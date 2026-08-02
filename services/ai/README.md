# Sketch2Build AI Engine

Multi-modal AI service for architectural sketch-to-plan generation.

## Architecture

```
src/
  api/v1/          # FastAPI routes (generate, jobs, health)
  models/
    vision/        # Sketch-to-Graph Encoder (CLIP + detection head)
    layout/        # Layout Diffusion Model (U-Net + graph conditioning)
    massing/       # 3D extrusion model (Phase 4)
  training/
    data/          # Synthetic data generator, sketch warper, datasets
    utils/         # Metrics, visualization
    config/        # YAML training configs
  inference/       # Pipeline orchestration (vision → layout → 3D)
  services/        # Celery queue, storage
  config.py        # Pydantic settings
  main.py          # FastAPI entry point
```

## Quick Start

### Local Development (requires GPU)

```bash
cd services/ai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate synthetic dataset (100K samples)
python -m src.training.data.synthetic_generator
# Or use the builder:
python -c "from src.training.data.synthetic_generator import SyntheticDatasetBuilder; SyntheticDatasetBuilder('data/synthetic').build(num_samples=100000)"

# Train vision encoder
python -m src.training.train_vision --data_dir data/synthetic --output_dir output/vision

# Train layout diffusion model
python -m src.training.train_layout --data_dir data/synthetic --output_dir output/layout

# Start FastAPI server
uvicorn src.main:app --reload

# Start Celery worker (in another terminal)
celery -A src.services.queue worker -l info -c 1 --pool=solo
```

### Docker (GPU)

```bash
cd services/ai/docker
docker-compose up --build
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/design/generate` | POST | Submit design generation job |
| `/api/v1/jobs/{job_id}` | GET | Poll job status |
| `/api/v1/jobs/{job_id}/result` | GET | Get completed results |

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis for Celery broker |
| `CELERY_BROKER_URL` | Celery broker (Redis) |
| `CELERY_RESULT_BACKEND` | Celery result backend (Redis) |
| `R2_ENDPOINT` | Cloudflare R2 S3 endpoint |
| `R2_BUCKET` | R2 bucket name |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `WANDB_API_KEY` | Weights & Biases API key (optional) |
| `HF_TOKEN` | HuggingFace token (for model downloads) |

## Phase Status

- **Phase 1 (Foundation)**: In progress — scaffolding complete, synthetic generator ready
- **Phase 2 (Layout Generation)**: Scaffolded — diffusion model architecture defined
- **Phase 3 (Compliance)**: Not started
- **Phase 4 (3D & Export)**: Not started
- **Phase 5 (Polish)**: Not started

## Training

### Vision Encoder

Fine-tunes CLIP vision backbone with a RoomGraphHead to detect:
- Room types (12 classes)
- Bounding boxes (x, y, w, h)
- Adjacency matrix (room-to-room connections)
- Plan validity (contrastive learning with invalid samples)

```bash
python -m src.training.train_vision \
  --data_dir data/synthetic \
  --output_dir output/vision \
  --batch_size 32 \
  --learning_rate 1e-4 \
  --num_epochs 50
```

### Layout Diffusion

Trains a U-Net diffusion model conditioned on room graphs:
- Forward diffusion: adds noise to clean floor plans
- Reverse diffusion: generates plans from noise + graph conditioning
- Uses DDPM sampling with 50-1000 steps

```bash
python -m src.training.train_layout \
  --data_dir data/synthetic \
  --output_dir output/layout \
  --batch_size 16 \
  --learning_rate 1e-4 \
  --num_epochs 100
```

## Notes

- The diffusion model U-Net is currently a scaffold. The full architecture would include 4+ down/up blocks with attention at 16x16 and 8x8 resolutions.
- Synthetic data generator uses simple grid-based placement. Replace with graph-based growth (House-GAN style) for more realistic plans.
- 3D massing and compliance engine are stubbed in `src/inference/pipeline.py` and will be implemented in Phases 3-4.
