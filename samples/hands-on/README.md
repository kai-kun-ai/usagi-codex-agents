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

`make run`（TUI）だけを起動しても、Codex/Claude の「ログイン画面」は出ません。
**公式CLI（`codex` / `claude`）を一度起動してログインセッションを作る**必要があります。

また、ログインした `PROFILE` と、後で `make run ... PROFILE=...` で起動する `PROFILE` は必ず揃えてください。

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

## 6. usagi を起動して動作確認（オフライン→オンライン）

### 6.0 保存場所（`WORKDIR` とログインセッション）

- `WORKDIR=$PWD` はコンテナ内 `/work` にマウントされ、usagi は `--root /work` で動きます。
  - そのため、`inputs/`, `outputs/`, `.usagi/` は **リポジトリ直下（WORKDIR）**に作られます。
- 一方、ログインセッション（`/root/.codex` / `/root/.claude`）は
  `./.usagi/sessions/**/<PROFILE>` に永続化されます（リポジトリ側の別ディレクトリ）。

「作業データ」と「ログインセッション」は置き場所が違う、という前提を押さえておくと迷いません。

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

`make run WORKDIR=$PWD ...` で起動している場合、**usagi はコンテナ内で動いています**が、
`WORKDIR`（リポジトリ直下）は **ホスト ↔ コンテナで volume 共有**されています。
そのため、inputs を置く操作は **ホスト側で実行してOK** です（コンテナ内から実行しても同じ場所に書き込まれます）。

#### A) すでに `make run` を起動している場合（おすすめ: ホスト側で実行）

ホスト側（別ターミナル、リポジトリ直下）で、サンプル指示書を `inputs/` に置きます:

```bash
mkdir -p inputs
cp samples/hands-on/specs/hello.md inputs/hello.md
```

しばらく待つと `outputs/hello.report.md` が生成されます。

```bash
ls -la outputs
cat outputs/hello.report.md
```

#### B) `make d-shell` でコンテナに入っている場合（コンテナ内で実行）

コンテナ内でも同様に実行できます（同じ volume に書き込まれます）:

```bash
mkdir -p inputs
cp samples/hands-on/specs/hello.md inputs/hello.md
```

### 6.3 オンライン（Codexログイン前提）で動かす

OFFLINEを外して実行してください（Codexログインが完了していること）。

```bash
make run WORKDIR=$PWD PROFILE=alice
```

### 6.4 実運用テスト（ミニCLI: topもどき をゼロから作る）

このリポジトリを「本当に使う」最終テストとして、ミニCLIツール（topもどき）を作らせます。

1) 指示書を inputs に投入:

```bash
mkdir -p inputs
cp specs/hands-on-minitop.md inputs/minitop.md
```

2) 生成物を確認（しばらく待つ）:

```bash
ls -la outputs
sed -n '1,120p' outputs/minitop.report.md
```

期待:
- レポートが出力される
- 生成された `minitop` プロジェクトのファイル（README / テスト / 実装）が作業ディレクトリ配下に作られる

補足:
- 生成物の場所は `work/` 配下（実行ごとにジョブIDのディレクトリが作られる）です。

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
