# usagi-codex-agents

うさぎさん株式会社（Codex志向マルチエージェント）CLI。

- 実装言語: **Python**
- 運用: **Docker前提**（ローカルpipはデバッグ用途）
- Discord連携: **discord.py**（OpenClaw非依存）
- Codex/Claude: 公式CLIをDockerに同梱（プロファイルをvolumeで切替）

## Discord連携（任意）

Discord へ進捗を投稿したり、メンションを受け取って boss inbox に流す場合は、以下の環境変数が必要です。

- **受信/送信（Botトークン方式）**
  - `USAGI_DISCORD_TOKEN`（Bot Token）
  - `USAGI_DISCORD_CHANNEL_ID`（投稿・監視するチャンネルID）
- **進捗投稿（Webhook方式 / 任意）**
  - `USAGI_DISCORD_WEBHOOK_URL`（Incoming Webhook URL）

`make run` / `make d-shell` は、上記の環境変数がホスト側に設定されていればコンテナへ引き継ぎます（未設定なら何もしません）。

## テスト

```bash
make test      # ローカル
make d-test    # Docker
make run WORKDIR=$PWD PROFILE=alice OFFLINE=1  # Dockerで統合CUI起動
make demo                                      # Dockerで完全デモ起動（WORKDIR/PROFILE不要）
```

## Codex / Claude login（複数セッション）

このツールは **APIキー方式** だけでなく、**Codex/Claudeの公式CLIログイン（サブスク由来のトークン含む）** も使えるようにしています。

- Codex: `/root/.codex`（ChatGPTログインセッション）
- Claude: `/root/.claude`（Claude Codeログインセッション）

### 1) プロファイル（複数ログイン）ディレクトリを作る

例: `alice` プロファイル

```bash
mkdir -p .usagi/sessions/codex/alice .usagi/sessions/claude/alice
```

### 2) プロファイルを volume mount してコンテナに入る

```bash
make d-shell WORKDIR=$PWD PROFILE=alice
```

### 3) コンテナ内で公式CLIを使ってサブスクログイン（トークン取り込み）

#### Codex（ChatGPTサブスクのログイン）

```bash
codex
# 初回起動時にサインインが走る（ChatGPTアカウントでログイン）
# ログイン状態は /root/.codex に保存され、ホスト側プロファイルに永続化される
```

#### Claude Code（Pro/Max/Teams/Enterprise のログイン）

```bash
claude
# 初回セットアップでログインが走る
# 手元運用によっては `claude setup-token` を使う
# ログイン状態は /root/.claude に保存され、ホスト側プロファイルに永続化される
```

### 4) 実行

ログインが完了したら、同じプロファイルをマウントした状態で `usagi` を実行します。

```bash
# 例: 統合CUI
usagi tui

# 例: watch/autopilot
usagi autopilot-start --offline
```

注意:
- **トークン文字列を手でコピペして保存する必要はありません**。公式CLIのログイン状態がプロファイルディレクトリに保存されます。
- `.usagi/sessions/**` の中身は秘密情報を含みうるため、**git管理しない**（.gitignore対象）前提です。

## ハンズオン

完全な手順書（ログイン→CUI→inputs投入→outputs確認）:

- `samples/hands-on/README.md`

---

## CLI（主要）

### 統合CUI

- `usagi tui`
  - `ctrl+s`: Start/Stop（STOPファイルの作成/解除）
  - 社長チャット: 画面から社長inboxへメッセージ送信（.usagi/inbox/）
  - 組織図: `--org` の定義をツリー表示（絵文字/名前の表示に対応）
  - うさぎの稼働状態（working/idle）とタスク
  - inputs一覧（pending/processed）
  - eventsログ
- `usagi tui --demo`
  - API/CLIを叩かず、疑似的に inputs/status/events/outputs を更新して画面デモを行う

### サブコマンド

- `usagi run` / `usagi validate`
- `usagi watch`
- `usagi autopilot-start` / `usagi autopilot-stop`
- `usagi status`
- `usagi input`
- `usagi mcp`
