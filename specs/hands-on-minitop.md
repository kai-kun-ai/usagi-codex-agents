---
project: hands-on-minitop
---

## 目的

Linux上で動く「topもどき」のミニCLIツールをゼロから作る。
リフレッシュUIは不要で、一定間隔でループ出力する方式にする。

補足:

- このリポジトリ（usagi-codex-agents）を使った **Codexログイン後の実運用テスト用**
- 依存を増やしすぎない（psutil無し、/proc を読む）
- まずは正確性より「動く・テストがある・READMEがある」ことを重視

## やること

- 新しいPythonパッケージ `minitop` を作成する
  - エントリポイント: `minitop` コマンド
  - `python -m minitop` でも動く
- /proc から情報を取得して、テキストを標準出力に出す
  - 1回だけ出力するモード（`--once`）
  - ループ出力するモード（デフォルト、`--interval` 秒、`--count` 回）
  - 上位N件表示（`--top-n`）
- 表示内容（最低限）
  - 現在時刻
  - CPUの概況（/proc/stat を読む）
  - メモリの概況（/proc/meminfo を読む）
  - 上位プロセス一覧（/proc/[pid]/stat, /proc/[pid]/status など）
    - pid, rss, cmd, (可能ならcpu%風の指標)
- README（日本語）
  - 使い方、例、注意（Linux専用で良い）
- テスト（pytest）
  - /proc のパース部分は fixture 文字列で単体テスト
  - CLI引数の最低限のテスト
- ruff に通す

## 制約

- Pythonで実装
- 既存ツールの構造に合わせる（ruff/pytest）
- トークン等の秘密情報を出力しない
- 大きなファイルは生成しない
