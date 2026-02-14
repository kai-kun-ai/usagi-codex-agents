# うさぎさん株式会社 (usagi)

Markdownの指示書を渡すと、**社長うさぎ(計画)** → **実装うさぎ(生成/編集案)** → **監査うさぎ(簡易チェック)** の順で動いて、最後に **Markdownレポート**を出します。

> コンセプト: うさぎさんの会社。

## できること (MVP)

- Markdownから「目的/背景/やること/制約」を抽出
- Codex(OpenAI API)で計画 → 差分(unified diff)生成
- `git apply` で差分を適用して成果物を作成
- 実行ログ + レポート(Markdown)出力

## セットアップ（Python）

### uv（推奨）

```bash
uv venv
uv pip install -e .
```

### pip

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

### 必要な環境変数

```bash
export OPENAI_API_KEY="..."
```

## 使い方

### 1) 指示書を作る

例: `specs/sample.md`

```md
---
project: hello-usagi
---

## 目的

README と簡単なスクリプト/CLIを作って。

## やること

- README.md を作成
- Pythonで `hello` と表示するスクリプト/CLIを作る

## 制約

- 文章は日本語
```

### 2) 実行

```bash
usagi run specs/sample.md --workdir ./out/hello --out ./out/report.md
```

- `--out` を省略すると標準出力にレポートを出します
- `--dry-run` を付けると計画だけ出します（APIは呼びません）
- `--offline` を付けると OpenAI APIを呼ばずに動作確認できます（ダミーの計画/差分を使います）

## Lint / Test

```bash
make test
```

## inputs 監視（watch）

`inputs/` に指示書Markdownを置くと、追加/更新を検知して自動で処理し、`outputs/` にレポートを書き出します。

```bash
usagi watch --inputs inputs --outputs outputs --work-root work --state .usagi/state.json --offline
```

## 注意

- このツールは **ローカルファイルを書き換えます**（workdir配下）
- unified diff の適用は `git apply` を使います

## ライセンス

MIT
