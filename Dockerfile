# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# System deps + official CLIs
#
# NOTE:
# - worker-only container execution uses Docker-outside-of-Docker.
# - docker daemon is NOT required inside this image, but the docker CLI IS required.
# - In some environments, Debian's `docker.io` package may not be available/installed as expected.
#   Prefer Docker official repo and install CLI-only.
RUN apt-get update && apt-get install -y --no-install-recommends \
  git bash curl ca-certificates \
  nodejs npm \
  gnupg \
  && rm -rf /var/lib/apt/lists/*

# Docker CLI (official repo; CLI-only)
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
  install -m 0755 -d /etc/apt/keyrings; \
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
  chmod a+r /etc/apt/keyrings/docker.gpg; \
  . /etc/os-release; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin; \
  rm -rf /var/lib/apt/lists/*

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
