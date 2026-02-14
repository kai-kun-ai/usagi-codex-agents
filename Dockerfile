# syntax=docker/dockerfile:1
FROM node:22-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json ./
RUN npm ci

# Copy sources
COPY . .

# Build TypeScript
RUN npm run build

# Provide the CLI
RUN npm link

ENV NODE_ENV=production

ENTRYPOINT ["usagi"]
CMD ["--help"]
