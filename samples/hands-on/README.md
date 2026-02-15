# ハンズオン（完全版）: usagi を実際に動かす

この手順は「初めて usagi を触る」人向けの、最短で動作確認できるハンズオンです。

## 0. 前提

- Docker が使えること
- このリポジトリを clone 済み

```bash
git clone https://github.com/kai-kun-ai/usagi-codex-agents
cd usagi-codex-agents
```

## 1. （任意）Discord連携の環境変数を設定する

Discord連携を使う場合は、ホスト側に環境変数を設定してから `make run` / `make d-shell` を実行してください（コンテナへ引き継がれます）。

- Botトークン方式（受信/送信）:
  - `USAGI_DISCORD_TOKEN`
  - `USAGI_DISCORD_CHANNEL_ID`
- Webhook方式（進捗投稿のみ / 任意）:
  - `USAGI_DISCORD_WEBHOOK_URL`

例（bash）:

```bash
export USAGI_DISCORD_TOKEN="..."
export USAGI_DISCORD_CHANNEL_ID="123456789012345678"
# export USAGI_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

## 2. Dockerイメージを作る

```bash
make d-build
```

## 3. ログインプロファイルを作る（Codex / Claude）

例として `alice` というプロファイル名を使います。

```bash
mkdir -p .usagi/sessions/codex/alice .usagi/sessions/claude/alice
```

## 4. プロファイルをマウントしてコンテナに入る

以降は `WORKDIR` を絶対パスで指定します（例: リポジトリ直下）。

```bash
make d-shell WORKDIR=$PWD PROFILE=alice
```

## 5. コンテナ内でサブスクログイン（トークン取り込み）

### 5.1 Codex（ChatGPTアカウント）

```bash
codex
```

- 初回起動時にログインが走ります。
- 成功するとログイン状態が `/root/.codex` に保存されます（ホスト側のプロファイルへ永続化）。

### 5.2 Claude Code（Claude Pro/Max/Teams/Enterprise）

```bash
claude
```

- 初回起動時にセットアップが走ります。
- 環境によっては `claude setup-token` の運用になります。
- 成功するとログイン状態が `/root/.claude` に保存されます（ホスト側のプロファイルへ永続化）。

## 6. usagi を起動して動作確認

### 6.1 統合CUI（おすすめ）

ホスト側で（コンテナを別途起動する必要なし）:

```bash
make run WORKDIR=$PWD PROFILE=alice OFFLINE=1
```

※ 画面だけ見たい場合はデモモード:

```bash
make demo
```

- `s` キーで Start/Stop（STOPファイルの切替）
- inputs の pending/processed が見えます

> まずは `--offline` で UI/監視/レポート出力の流れを確認するのが安全です。

### 6.2 inputs を投入して watch を動かす

コンテナ内で、サンプル指示書を inputs に置きます:

```bash
mkdir -p inputs
cp samples/hands-on/specs/hello.md inputs/hello.md
```

しばらく待つと `outputs/hello.report.md` が生成されます。

```bash
ls -la outputs
cat outputs/hello.report.md
```

### 6.3 オンライン（API/CLI）で動かす

OFFLINEを外して実行してください。

```bash
make run WORKDIR=$PWD PROFILE=alice
```

またはコマンド単体（コンテナ内で実行したい場合）:

```bash
make d-shell WORKDIR=$PWD PROFILE=alice
# コンテナ内で
usagi autopilot-start
```

## 7. STOP（停止）

- CUIの `s` か、
- 別ターミナルで `usagi autopilot-stop`

で停止できます。

## トラブルシューティング

- ログインが必要: まず `codex` / `claude` を単体で起動して初期設定してください
- レポートが出ない:
  - `inputs/*.md` が存在するか
  - `.usagi/STOP` が残っていないか
  - `outputs/` が書き込み可能か
