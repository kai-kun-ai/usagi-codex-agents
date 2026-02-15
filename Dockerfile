# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# System deps + official CLIs
RUN apt-get update && apt-get install -y --no-install-recommends \
  git bash curl ca-certificates \
  nodejs npm \
  docker.io \
  && rm -rf /var/lib/apt/lists/*

# Codex CLI (official)
RUN npm i -g @openai/codex

# Claude Code (official)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Python deps first (cache)
COPY requirements.txt ./
RUN pip install -U pip && pip install -r requirements.txt

# App
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY examples ./examples

RUN pip install .

ENTRYPOINT ["usagi"]
CMD ["--help"]
