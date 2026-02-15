# usagi-corp

Go版（大規模リライト）の進行中ブランチです。最終的に `usagi-corp` バイナリとして提供します。

- 旧Python実装は `legacy/python/` に退避（要件取りこぼし防止の比較用）
- Docker前提で動作させます

## Build / Test

```bash
make go-test
make d-test
```

## Shell

```bash
make d-shell
# codex / claude が同梱されている
codex
claude
```
