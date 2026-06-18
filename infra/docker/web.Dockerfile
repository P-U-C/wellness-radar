FROM node:22-slim

WORKDIR /app

COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && pnpm install

COPY apps/web apps/web

EXPOSE 5173
