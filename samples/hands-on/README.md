# ハンズオン（完全版）: usagi を実際に動かす

この手順は「初めて usagi を触る」人向けの、最短で動作確認できるハンズオンです。

## 0. 前提

- Docker が使えること
- このリポジトリを clone 済み

```bash
git clone https://github.com/kai-kun-ai/usagi-codex-agents
cd usagi-codex-agents
```

## 1. Dockerイメージを作る

```bash
docker build -t usagi-dev .
```

## 2. ログインプロファイルを作る（Codex / Claude）

例として `alice` というプロファイル名を使います。

```bash
mkdir -p .usagi/sessions/codex/alice .usagi/sessions/claude/alice
```

## 3. プロファイルをマウントしてコンテナに入る

```bash
docker run --rm -it \
  -v "$PWD":/app \
  -v "$PWD/.usagi/sessions/codex/alice":/root/.codex \
  -v "$PWD/.usagi/sessions/claude/alice":/root/.claude \
  usagi-dev bash
```

## 4. コンテナ内でサブスクログイン（トークン取り込み）

### 4.1 Codex（ChatGPTアカウント）

```bash
codex
```

- 初回起動時にログインが走ります。
- 成功するとログイン状態が `/root/.codex` に保存されます（ホスト側のプロファイルへ永続化）。

### 4.2 Claude Code（Claude Pro/Max/Teams/Enterprise）

```bash
claude
```

- 初回起動時にセットアップが走ります。
- 環境によっては `claude setup-token` の運用になります。
- 成功するとログイン状態が `/root/.claude` に保存されます（ホスト側のプロファイルへ永続化）。

## 5. usagi を起動して動作確認

### 5.1 統合CUI（おすすめ）

同じコンテナ内で:

```bash
usagi tui --offline
```

- `s` キーで Start/Stop（STOPファイルの切替）
- inputs の pending/processed が見えます

> まずは `--offline` で UI/監視/レポート出力の流れを確認するのが安全です。

### 5.2 inputs を投入して watch を動かす

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

### 5.3 オンライン（API/CLI）で動かす

`--offline` を外して実行してください。

```bash
usagi tui
```

またはコマンド単体:

```bash
usagi autopilot-start
```

## 6. STOP（停止）

- CUIの `s` か、
- 別ターミナルで `usagi autopilot-stop`

で停止できます。

## トラブルシューティング

- ログインが必要: まず `codex` / `claude` を単体で起動して初期設定してください
- レポートが出ない:
  - `inputs/*.md` が存在するか
  - `.usagi/STOP` が残っていないか
  - `outputs/` が書き込み可能か
