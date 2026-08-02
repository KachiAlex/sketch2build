# AI Architectural Design Engine — Roadmap

## Phase 1: Foundation (Weeks 1-4) — COMPLETE

- [x] **1. Scaffold AI training pipeline project structure**
  - FastAPI inference service, models/, training/, data/, docker/
- [x] **2. Build synthetic data generator for floor plan + sketch pairs**
  - Procedural layout engine using House-GAN / GraphRNN approach
  - Synthetic sketch generation via edge detection + warping from real plans
- [x] **3. Set up training infrastructure**
  - GPU Docker image (PyTorch 2.0 + CUDA)
  - Data loaders, experiment tracking (Weights & Biases or MLflow)
- [x] **4. Implement Sketch-to-Graph Vision Encoder**
  - Fine-tune CLIP/SigLIP on architectural sketches
  - Output: structured JSON (room types, dimensions, adjacency, structural elements)

## Phase 2: Core Layout Generation + Real Data (Weeks 5-10) — COMPLETE

- [x] **5. Implement 2D Layout Diffusion Model**
  - Transformer-based U-Net or Graph Transformer
  - Input: room adjacency graph + sketch embedding + text prompt
  - Output: vectorized floor plan (walls, doors, windows as polygons)
- [x] **5b. Refine synthetic generator with graph-based room growth**
  - Adjacency-aware placement (House-GAN style)
  - Realistic room sizing and connections
- [x] **6. Create dataset loaders for RPlan + CubiCasa5K**
  - SVG/JSON parsing for real-world floor plan annotations
  - Synthetic sketch generation from real plans via edge detection + warping
- [x] **6b. Build mixed training pipeline**
  - Weighted sampling across synthetic (50%) + RPlan (30%) + CubiCasa5K (20%)
  - `MixedSketchDataset` and `MixedLayoutDataset` for both vision and diffusion models
- [ ] **6c. Train Layout Model on mixed datasets** (requires GPU)
  - Run on GPU (A100/L40S) with W&B logging
  - LTR (Learning to Rank) loss on real architect ratings
- [ ] **6d. Evaluate and iterate** (requires GPU)
  - FID scores on generated vs. real floor plans
  - Architect validation of room adjacency accuracy

## Phase 3: Compliance & Constraints (Weeks 11-16) — COMPLETE

- [x] **7. Build Compliance RAG Engine**
  - Vector store of building codes (IBC, ASHRAE, Eurocode, local zoning)
  - Semantic search with sentence-transformers (all-MiniLM-L6-v2)
  - ChromaDB/FAISS for regulation storage and retrieval
  - 34 curated regulations covering IBC, ASHRAE, NFPA, ADA, Eurocode, Zoning
- [x] **7b. Compliance Validator Service**
  - Hard constraint checking (minimum room sizes, door widths, egress, FAR)
  - Soft constraint checking (natural light, ventilation, energy efficiency)
  - Building-level checks (bathroom-kitchen separation, bedroom egress, FAR)
  - ComplianceReport with score, violations, and suggested fixes
- [x] **7c. RAG Query Engine**
  - Natural language building code questions → semantic search + structured answer
  - Check specific design values against regulations
  - Design guidance for room types
- [x] **8. Integrate compliance into layout generation**
  - Constrained diffusion sampler with rejection sampling for hard violations
  - Compliance validation during pipeline execution
  - Alternatives ranked by compliance score (best first)
  - Compliance results embedded in generation output
- [x] **8b. Compliance API v1**
  - `POST /api/v1/compliance/query` — RAG question answering
  - `POST /api/v1/compliance/validate` — Floor plan validation
  - `POST /api/v1/compliance/check-requirement` — Single value check
  - `POST /api/v1/compliance/design-guidance` — Room type guidance
  - `GET /api/v1/compliance/regulations` — List regulations

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
