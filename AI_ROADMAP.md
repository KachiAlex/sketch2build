# AI Architectural Design Engine — Roadmap

## Phase 1: Foundation (Weeks 1-4)

- [ ] **1. Scaffold AI training pipeline project structure**
  - FastAPI inference service, models/, training/, data/, docker/
- [ ] **2. Build synthetic data generator for floor plan + sketch pairs**
  - Procedural layout engine using House-GAN / GraphRNN approach
  - Synthetic sketch generation via edge detection + warping from real plans
- [ ] **3. Set up training infrastructure**
  - GPU Docker image (PyTorch 2.0 + CUDA)
  - Data loaders, experiment tracking (Weights & Biases or MLflow)
- [ ] **4. Implement Sketch-to-Graph Vision Encoder**
  - Fine-tune CLIP/SigLIP on architectural sketches
  - Output: structured JSON (room types, dimensions, adjacency, structural elements)

## Phase 2: Core Layout Generation (Weeks 5-10)

- [ ] **5. Implement 2D Layout Diffusion Model**
  - Transformer-based U-Net or Graph Transformer
  - Input: room adjacency graph + sketch embedding + text prompt
  - Output: vectorized floor plan (walls, doors, windows as polygons)
- [ ] **6. Train Layout Model on datasets**
  - Synthetic data (millions of samples) + RPlan + CubiCasa5K
  - LTR (Learning to Rank) loss on real architect ratings

## Phase 3: Compliance & Constraints (Weeks 11-16)

- [ ] **7. Build Compliance RAG Engine**
  - Vector store of building codes (IBC, ASHRAE, Eurocode, local zoning)
  - Fine-tune Llama 3 8B on regulatory text interpretation
- [ ] **8. Integrate compliance into layout generation**
  - Constrained diffusion: hard constraints on setbacks, FAR, room sizes
  - Soft constraints on natural light, egress, ventilation

## Phase 4: 3D & Export (Weeks 17-24)

- [ ] **9. Implement 3D Massing / Extrusion pipeline**
  - RoomFormer or custom CNN to extrude 2D plans into 3D
  - Gaussian Splatting or NeRF for visualization
- [ ] **10. Build FastAPI inference service with Celery + Redis**
  - Async job queue for generation requests
  - GPU worker scaling on RunPod / Vast.ai / AWS
- [ ] **11. Design external API v1 spec**
  - `POST /api/v1/design/generate`, `GET /jobs/{id}`, alternatives, compliance report
- [ ] **12. Implement BIM/IFC export and 3D model generation**
  - GLB, DXF, IFC formats
  - Revit/ArchiCAD API integration

## Phase 5: Polish & Scale (Weeks 25+)

- [ ] **13. Add explainability layer**
  - Design rationale per room/decision (e.g., "Northern light per ASHRAE 90.1")
- [ ] **14. Regional fine-tuning**
  - Separate models for Nordic daylight, Middle East shading, tropical ventilation, etc.
- [ ] **15. Production deployment**
  - GPU worker auto-scaling, monitoring, CI/CD for model updates

---

## Competitive Differentiators

1. **Compliance-first generation** — intrinsic constraints, not post-hoc validation
2. **Multi-scale optimization** — site, building, and room level simultaneously
3. **Explainability** — architects trust decisions with rationale
4. **Native BIM output** — direct Revit/ArchiCAD integration, not just images
5. **Regional adaptation** — fine-tuned models per climate zone and building code

## Estimated Resources

- **GPU Hours**: ~5,000-10,000 for layout model training (A100/L40S)
- **Data**: Millions of synthetic plans + ~10K-50K real annotated plans
- **Team**: 2-3 ML engineers + 1 architect for data labeling and validation
