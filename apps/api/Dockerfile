FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies for native modules
RUN apk add --no-cache python3 make g++

# Copy workspace root for monorepo install
COPY package*.json ./
COPY apps/api/package*.json ./apps/api/
COPY packages/shared/package*.json ./packages/shared/

# Install all deps
RUN npm install

# Copy source
COPY apps/api ./apps/api
COPY packages/shared ./packages/shared

# Generate Prisma client
RUN npm run db:generate -w apps/api

# Build shared lib
RUN npm run build -w packages/shared

# Build API
RUN npm run build -w apps/api

EXPOSE 3000

CMD ["node", "/app/apps/api/dist/index.js"]
