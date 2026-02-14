# うさぎさん株式会社 (usagi)

Markdownの指示書を渡すと、**社長うさぎ(計画)** → **実装うさぎ(生成/編集案)** → **監査うさぎ(簡易チェック)** の順で動いて、最後に **Markdownレポート**を出します。

> コンセプト: うさぎさんの会社。

## できること (MVP)

- Markdownから「目的/背景/やること/制約」を抽出
- Codex(OpenAI API)で計画 → 差分(unified diff)生成
- `git apply` で差分を適用して成果物を作成
- 実行ログ + レポート(Markdown)出力

## インストール

```bash
npm i
npm run build
npm link
```

### 必要な環境変数

```bash
export OPENAI_API_KEY="..."
```

## Dockerで使う

Dockerが入っていれば、ローカルにnode環境を用意しなくても動かせます。

```bash
docker build -t usagi .
# カレントのspecs/をコンテナに渡して実行
docker run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" -v "$PWD":/work -w /work usagi run specs/sample.md --workdir ./out/sample --out ./out/report.md
```

## 使い方

### 1) 指示書を作る

例: `specs/hello.md`

```md
---
project: hello-usagi
---

## 目的

README と簡単なCLIを作って。

## やること

- README.md を作成
- Node.jsで `hello` と表示するCLIを作る

## 制約

- 文章は日本語
```

### 2) 実行

```bash
usagi run specs/hello.md --workdir ./out/hello --out ./out/report.md
```

- `--out` を省略すると標準出力にレポートを出します
- `--dry-run` を付けると計画だけ出します

## 開発

```bash
npm run dev -- run specs/hello.md --workdir ./out/hello
```

## 注意

- このツールは **ローカルファイルを書き換えます**（workdir配下）
- unified diff の適用は `git apply` を使います

## ライセンス

MIT
