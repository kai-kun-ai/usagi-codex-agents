# syntax=docker/dockerfile:1

# --- Build Go binary ---
FROM golang:1.23 AS go-build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN go mod download
RUN CGO_ENABLED=0 go build -o /out/usagi-corp ./cmd/usagi-corp

# --- Runtime image ---
FROM debian:bookworm-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates curl git bash \
  nodejs npm \
  && rm -rf /var/lib/apt/lists/*

# Official CLIs
RUN npm i -g @openai/codex
RUN curl -fsSL https://claude.ai/install.sh | bash

COPY --from=go-build /out/usagi-corp /usr/local/bin/usagi-corp

ENTRYPOINT ["usagi-corp"]
CMD ["version"]
