# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# System deps for git apply
RUN apt-get update && apt-get install -y --no-install-recommends git bash && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN pip install -U pip && pip install -e .

ENTRYPOINT ["usagi"]
CMD ["--help"]
