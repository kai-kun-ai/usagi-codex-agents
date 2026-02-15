"""workdir に残すアーティファクト（受け渡し用の短期メモリ）。

目的:
- 社長→部長→課長→ワーカーの間で「何を渡したか」をファイルとして残す
- 失敗時に workdir を見れば状況が追える

注意:
- secrets を直接書かない（プロンプト/ログに秘密が混ざる運用をしない前提）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactPaths:
    root: Path

    def path(self, name: str) -> Path:
        return self.root / name


def artifacts_dir(workdir: Path) -> Path:
    return workdir / ".usagi" / "artifacts"


def ensure_artifacts(workdir: Path) -> ArtifactPaths:
    d = artifacts_dir(workdir)
    d.mkdir(parents=True, exist_ok=True)
    return ArtifactPaths(root=d)


def write_artifact(workdir: Path, name: str, content: str) -> Path:
    ap = ensure_artifacts(workdir)
    p = ap.path(name)
    p.write_text(content, encoding="utf-8")
    return p
