.PHONY: test d-test d-build d-shell run demo

IMAGE ?= usagi-dev
WORKDIR ?=
PROFILE ?= default
OFFLINE ?= 0
DEMO ?= 0

# ----------------
# Local (debug)
# ----------------

test:
	ruff check .
	pytest -q

# ----------------
# Docker (primary)
# ----------------

d-build:
	docker build -t $(IMAGE) .

d-test: d-build
	docker run --rm \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  --entrypoint bash \
	  $(IMAGE) -lc 'make test'

# Dockerコンテナに入って公式CLIでログイン等を行う
# 例: make d-shell PROFILE=alice
# - /root/.codex と /root/.claude は profile で永続化
# - /app はこのリポジトリ
# - /work は作業ルート（絶対パス必須）

d-shell: d-build
	@if [ -z "$(WORKDIR)" ]; then \
		echo "WORKDIR is required (absolute path). Example: make d-shell WORKDIR=$$PWD PROFILE=alice"; \
		exit 2; \
	fi
	@case "$(WORKDIR)" in \
		/*) ;; \
		*) echo "WORKDIR must be an absolute path: $(WORKDIR)"; exit 2 ;; \
	esac
	docker run --rm -it \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -e USAGI_DISCORD_TOKEN \
	  -e USAGI_DISCORD_CHANNEL_ID \
	  -e USAGI_DISCORD_WEBHOOK_URL \
	  -e OPENAI_API_KEY \
	  -e ANTHROPIC_API_KEY \
	  -v "$(WORKDIR)":/work \
	  -v "$$PWD":/app \
	  -v "$$PWD/.usagi/sessions/codex/$(PROFILE)":/root/.codex \
	  -v "$$PWD/.usagi/sessions/claude/$(PROFILE)":/root/.claude \
	  -w /app \
	  --entrypoint bash \
	  $(IMAGE)

# 統合CUIを起動
# 例: make run WORKDIR=$$PWD PROFILE=alice
#      make run WORKDIR=$$PWD PROFILE=alice OFFLINE=1
#      make run WORKDIR=$$PWD PROFILE=alice DEMO=1

run: d-build
	@if [ -z "$(WORKDIR)" ]; then \
		echo "WORKDIR is required (absolute path). Example: make run WORKDIR=$$PWD PROFILE=alice"; \
		exit 2; \
	fi
	@case "$(WORKDIR)" in \
		/*) ;; \
		*) echo "WORKDIR must be an absolute path: $(WORKDIR)"; exit 2 ;; \
	esac
	@OFFLINE_FLAG=""; \
	if [ "$(OFFLINE)" = "1" ]; then OFFLINE_FLAG="--offline"; fi; \
	DEMO_FLAG=""; \
	if [ "$(DEMO)" = "1" ]; then DEMO_FLAG="--demo"; fi; \
	docker run --rm -it \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -e USAGI_DISCORD_TOKEN \
	  -e USAGI_DISCORD_CHANNEL_ID \
	  -e USAGI_DISCORD_WEBHOOK_URL \
	  -e OPENAI_API_KEY \
	  -e ANTHROPIC_API_KEY \
	  -v "$(WORKDIR)":/work \
	  -v "$$PWD":/app \
	  -v "$$PWD/.usagi/sessions/codex/$(PROFILE)":/root/.codex \
	  -v "$$PWD/.usagi/sessions/claude/$(PROFILE)":/root/.claude \
	  -w /app \
	  $(IMAGE) tui --root /work --org /app/examples/org.toml $$OFFLINE_FLAG $$DEMO_FLAG

# 完全なデモ（ホストのWORKDIR/PROFILE不要）
# - /work は匿名volume（ホストに永続化しない）
# - セッションマウントもしない
# - API/CLIは叩かない

demo: d-build
	docker run --rm -it \
	  -v /var/run/docker.sock:/var/run/docker.sock \
	  -v /work \
	  -w /app \
	  $(IMAGE) tui --root /work --org /app/examples/org.toml --demo
