FROM node:20-alpine AS base

WORKDIR /app

COPY package*.json ./
COPY apps/web/package*.json ./apps/web/
COPY packages/shared/package*.json ./packages/shared/

RUN npm install

COPY apps/web ./apps/web
COPY packages/shared ./packages/shared

RUN npm run build -w packages/shared
RUN npm run build -w apps/web

EXPOSE 5173

CMD ["npx", "vite", "preview", "--config", "/app/apps/web/vite.config.ts", "--host", "0.0.0.0", "--port", "5173"]
