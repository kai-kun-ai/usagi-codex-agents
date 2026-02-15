# usagi-codex-agents

うさぎさん株式会社（Codex志向マルチエージェント）CLI。

- 実装言語: **Python**
- 運用: **Docker前提**（ローカルpipはデバッグ用途）
- Discord連携: **discord.py**（OpenClaw非依存）
- Codex/Claude: 公式CLIをDockerに同梱（プロファイルをvolumeで切替）

## テスト

```bash
make test      # ローカル
make d-test    # Docker
```

## Codex / Claude login（複数セッション）

- Codex: `/root/.codex`
- Claude: `/root/.claude`

プロファイル例（alice）:

```bash
mkdir -p .usagi/sessions/codex/alice .usagi/sessions/claude/alice

docker run --rm -it \
  -v "$PWD":/app \
  -v "$PWD/.usagi/sessions/codex/alice":/root/.codex \
  -v "$PWD/.usagi/sessions/claude/alice":/root/.claude \
  usagi-dev bash

# コンテナ内で
codex   # 初回ログイン
claude  # setup-token 等
```

## CLI（主要）

- `usagi tui`（統合CUI。ここから start/stop/状態確認ができる）
- `usagi run` / `usagi validate`
- `usagi watch`
- `usagi autopilot-start` / `usagi autopilot-stop`
- `usagi status`
- `usagi input`
- `usagi mcp`
