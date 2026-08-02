# Sketch2Build API Gateway & Orchestration Service

Node.js / Express / TypeScript service handling:

- Authentication and authorization
- REST API for projects, jobs, compliance, exports
- Async job orchestration via BullMQ + Redis
- File upload coordination to S3-compatible storage

## Local development

```bash
# From repo root
npm install
npm run build -w packages/shared
npm run dev -w apps/api
```

## Database

```bash
npm run db:migrate -w apps/api
npm run db:seed -w apps/api
```

## Environment

Copy `.env.example` to `.env` and configure.
