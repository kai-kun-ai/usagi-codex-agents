# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends git bash && rm -rf /var/lib/apt/lists/*

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
