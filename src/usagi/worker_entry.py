"""worker_entry: workerコンテナ内でパイプラインを実行するためのエントリ。

ホスト側(usagi本体)から docker run で呼び出されることを想定する。

- 入力spec Markdownを読み取り
- approval pipeline を実行
- レポートMarkdownを stdout に出力

注意:
- secrets を表示しない（このモジュール自体は secrets を扱わない）
"""

from __future__ import annotations

import argparse
from pathlib import Path

from usagi.approval_pipeline import run_approval_pipeline
from usagi.org import load_org
from usagi.runtime import load_runtime
from usagi.spec import parse_spec_markdown


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m usagi.worker_entry")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--model", type=str, default="codex")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--org", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)

    args = p.parse_args(argv)

    md = args.spec.read_text(encoding="utf-8")
    spec = parse_spec_markdown(md)

    res = run_approval_pipeline(
        spec=spec,
        workdir=args.workdir,
        model=args.model,
        offline=bool(args.offline),
        org=load_org(args.org),
        runtime=load_runtime(args.runtime),
        root=args.root,
    )

    print(res.report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
