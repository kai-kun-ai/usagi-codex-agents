# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
  git bash curl ca-certificates \
  nodejs npm \
  && rm -rf /var/lib/apt/lists/*

# --- Official CLIs ---
# Codex CLI (official install): npm i -g @openai/codex
RUN npm i -g @openai/codex

# Claude Code (official install): curl -fsSL https://claude.ai/install.sh | bash
# NOTE: This runs the vendor install script during image build.
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install deps first (cache)
COPY requirements.txt ./
RUN pip install -U pip && pip install -r requirements.txt

# Copy app
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

# Install package
RUN pip install .

ENTRYPOINT ["usagi"]
CMD ["--help"]
