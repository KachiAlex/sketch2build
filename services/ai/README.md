# Sketch2Build AI Engine

Multi-modal AI service for architectural sketch-to-plan generation.

## Architecture

```
src/
  api/v1/          # FastAPI routes (generate, jobs, health, compliance, exports, explainability, regional, monitoring)
  models/
    vision/        # Sketch-to-Graph Encoder (CLIP + detection head)
    layout/        # Layout Diffusion Model (U-Net + graph conditioning)
    massing/       # 3D extrusion + IFC/BIM + DXF + GLB exports
      extruder.py          # Floor plan → 3D geometry (walls, rooms, multi-story)
      ifc_export.py        # IFC-STEP BIM export (Revit/ArchiCAD compatible)
      dxf_export.py        # 2D/3D AutoCAD DXF export
      glb_export.py        # Binary GLTF 2.0 for WebGL (Three.js, Babylon.js)
  compliance/      # RAG engine + validator + constrained diffusion
    vector_store.py       # ChromaDB/FAISS regulation store
    validator.py          # Hard/soft constraint checking
    rag_engine.py         # RAG question answering
    regulations_seed.py   # 34 curated regulations (IBC, ASHRAE, NFPA, ADA, Eurocode, Zoning)
    constrained_diffusion.py # Compliance-aware diffusion sampling
  explainability/  # Design rationale engine
    engine.py             # Per-room + building-level explanations (10 categories)
  regional/        # Climate-specific design profiles
    profiles.py           # 8 regional profiles (Nordic, Middle East, Tropical, Japan, etc.)
  training/
    data/          # Synthetic data generator, sketch warper, datasets
    utils/         # Metrics, visualization
    config/        # YAML training configs
  inference/       # Pipeline orchestration (vision → layout → compliance → 3D → explainability)
  services/        # Celery queue, storage, monitoring (Prometheus metrics)
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
| `/api/v1/compliance/query` | POST | RAG question answering on building codes |
| `/api/v1/compliance/validate` | POST | Validate floor plan against regulations |
| `/api/v1/compliance/check-requirement` | POST | Check if a value meets a code requirement |
| `/api/v1/compliance/design-guidance` | POST | Get guidance for room types |
| `/api/v1/compliance/regulations` | GET | List available regulations |
| `/api/v1/exports/export` | POST | Export floor plan to IFC, DXF, or GLB |
| `/api/v1/exports/3d-preview` | POST | Generate 2D axonometric preview from 3D model |
| `/api/v1/explainability/explain` | POST | Generate design rationale report |
| `/api/v1/regional/profiles` | GET | List regional design profiles |
| `/api/v1/regional/profiles/{key}` | GET | Get specific regional profile |
| `/api/v1/regional/apply` | POST | Apply regional profile to constraints |
| `/api/v1/monitoring/metrics` | GET | Prometheus metrics endpoint |
| `/api/v1/monitoring/health/detailed` | GET | Full health with GPU/model checks |
| `/api/v1/monitoring/health/live` | GET | Liveness probe |
| `/api/v1/monitoring/health/ready` | GET | Readiness probe |

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

- **Phase 1 (Foundation)**: Complete — scaffolding, synthetic generator, training infra, vision encoder, layout diffusion, FastAPI/Celery
- **Phase 2 (Layout Generation + Real Data)**: Complete — graph-based synthetic generator, RPlan/CubiCasa5K loaders, mixed training pipeline (training requires GPU)
- **Phase 3 (Compliance)**: Complete — RAG engine with 34 regulations, validator with hard/soft constraints, constrained diffusion, compliance API v1
- **Phase 4 (3D & Export)**: Complete — 3D extruder (room walls, multi-story), IFC/BIM export, 2D/3D DXF, binary GLB, 3D preview generation, exports API
- **Phase 5 (Polish & Scale)**: Complete — explainability engine (10 categories, per-room rationale), 8 regional profiles (Nordic/Middle East/Tropical/Japan/etc.), Prometheus monitoring, RunPod/Vast.ai deployment configs

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

## Compliance

### Seed Regulations

```bash
python -m scripts.seed_regulations
```

This populates the ChromaDB/FAISS vector store with 34 curated regulations from IBC, ASHRAE, NFPA, ADA, Eurocode, and local zoning.

### Validate a Floor Plan

```bash
curl -X POST http://localhost:8000/api/v1/compliance/validate \
  -H "Content-Type: application/json" \
  -d '{
    "design_id": "test-001",
    "rooms": [
      {"type": "bedroom", "width": 3.5, "depth": 4.0, "area": 14.0, "height": 2.5, "id": "b1"},
      {"type": "bathroom", "width": 2.0, "depth": 2.5, "area": 5.0, "height": 2.2, "id": "b2"}
    ],
    "adjacency": [[0, 1]],
    "code": "IBC"
  }'
```

### Query Building Codes

```bash
curl -X POST http://localhost:8000/api/v1/compliance/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the minimum bedroom size in IBC?", "code": "IBC"}'
```

## Notes

- The diffusion model U-Net is currently a scaffold. The full architecture would include 4+ down/up blocks with attention at 16x16 and 8x8 resolutions.
- Synthetic data generator now uses graph-based growth (House-GAN style) in `src/training/data/graph_generator.py`.
- Compliance engine is fully implemented with RAG, validator, and constrained diffusion in `src/compliance/`.
- 3D massing is fully implemented in `src/models/massing/` with IFC, DXF, and GLB exports.
- Explainability engine generates per-room design rationale across 10 categories (natural light, ventilation, privacy, ergonomics, etc.).
- 8 regional profiles cover Nordic, Middle East, Tropical, Japan, Australia, Continental, Arid, and Mountain climates.
- Prometheus-compatible metrics at `/api/v1/monitoring/metrics` for production observability.
- Deployment configs for RunPod and Vast.ai GPU workers in `deploy/deployment.yaml`.
- The LLM generation step in RAG uses structured summaries; replace with fine-tuned Llama 3 8B or API call in production.
- IFC export writes STEP-21 format compatible with Revit, ArchiCAD, Tekla.
- GLB export writes binary GLTF 2.0 with mesh data for WebGL renderers (Three.js, Babylon.js).
- DXF export writes AC1015 (R2000) format for AutoCAD import.
