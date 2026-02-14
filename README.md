# うさぎさん株式会社 (usagi)

Markdownの指示書を渡すと、**社長うさぎ(計画)** → **実装うさぎ(生成/編集案)** → **監査うさぎ(簡易チェック)** の順で動いて、最後に **Markdownレポート**を出します。

> コンセプト: うさぎさんの会社。

---

## セットアップ（Docker前提）

通常運用は Docker を前提にします。

```bash
docker build -t usagi .
```

### ローカルpip（debug用途）

Dockerが使えない/デバッグ用途のみ。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

### 必要な環境変数

```bash
export OPENAI_API_KEY="..."
# 複数キーがある場合
export USAGI_API_KEYS="key1,key2,key3"
```

---

## Lint / Test

ローカル（debug）:

```bash
make test
```

Docker（運用前提）:

```bash
make d-test
```

---

## inputs 監視（watch）

`inputs/` に指示書Markdownを置くと、追加/更新を検知して自動で処理し、`outputs/` にレポートを書き出します。

```bash
usagi watch --inputs inputs --outputs outputs --work-root work --state .usagi/state.json --offline
```

停止はCtrl+C、または `.usagi/STOP` を作成。

---

## autopilot（止めるまで走る）

```bash
usagi autopilot-start --offline
# 停止
usagi autopilot-stop
```

`STOP_USAGI` という文字列をDiscordで送る運用も可能（後述）。

---

## Discord連携（OpenClaw非依存 / discord.py）

現状の実装:
- 進捗投稿のフォーマット: **`[AI名] 文章`**
- `@everyone` / `@here` は抑止
- allowlist（チャンネル/ユーザー）を設定して誤爆/注入を防止
- メンションされたら `.usagi/inbox/` に boss input を保存
- `STOP_USAGI` を受信したら `.usagi/STOP` を作り停止

### 実行に必要な環境変数

```bash
export USAGI_DISCORD_TOKEN="..."
export USAGI_DISCORD_CHANNEL_ID="1234567890123"
```

※ Bot側で Message Content Intent を有効化してください。

---

## 組織図（権力階層）設定: org.toml

- `examples/org.toml` を参照
- `[[agents]]` の `id / reports_to / can_command` で指揮系統を明示
- role は `boss / ghost_boss / manager / worker / reviewer`

---

## runtimeモード: usagi.runtime.toml

- `examples/usagi.runtime.toml` を参照
- merge/vote/autopilot の方針を切り替える土台

---

## 注意（秘密情報）

- APIキーやDiscordトークンは **設定ファイルに直書きしない**
- 環境変数 or トークンファイル参照のみ

## ライセンス

MIT
