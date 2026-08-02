# AI Architectural Design Platform

AI-assisted architectural design platform for Kreatix Technologies. Converts hand-drawn sketches or natural-language design briefs into dimensioned, code-aware floor plans with CAD/BIM export.

## Capabilities

- **Sketch-to-Plan**: digitize hand-drawn or photographed floor plan sketches into editable vector plans.
- **Prompt-to-Design**: generate optimized floor plan layouts from a structured or free-text design brief.
- **Compliance**: validate layouts against the active jurisdiction ruleset (Nigerian NBC at MVP).
- **Export**: DXF, IFC, PDF/PNG output.

## Tech Stack

- **Frontend**: React, Vite, TypeScript, TailwindCSS, shadcn/ui
- **API / Orchestration**: Node.js, Express, TypeScript, Prisma
- **AI Processing**: Python, FastAPI
- **Database**: PostgreSQL
- **Message Queue**: Redis
- **Object Storage**: S3-compatible (MinIO locally)
- **Containerization**: Docker, Docker Compose

## Monorepo Structure

```
c:\sketch2build
├── apps
│   ├── web          # React frontend
│   ├── api          # API Gateway + Orchestration Service (Node/Express)
│   └── ai           # AI processing services (Python/FastAPI)
├── packages
│   └── shared       # Shared TypeScript types and utilities
├── docker-compose.yml
└── package.json     # Workspace root
```

## Quick Start

### Prerequisites

- Docker Desktop
- Node.js 20+ (for local frontend/backend dev)
- Python 3.11+ (for AI service dev)

### Run the full stack locally

```bash
docker compose up --build
```

### Services

- Web app: http://localhost:5173
- API Gateway: http://localhost:3000
- AI Service: http://localhost:8000
- API docs: http://localhost:3000/api/docs

## Development

See individual `README.md` files in `apps/web`, `apps/api`, and `apps/ai`.

## Status

Phase 0 — Project setup and scaffolding in progress.
