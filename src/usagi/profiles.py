"""Codex/CLI プロファイル管理。

profiles.toml で複数の Codex アカウントを定義し、
org.toml の各agentが `profile = "xxx"` で参照する。

### profiles.toml

```toml
[[profiles]]
name = "account_a"
codex_config = "/home/user/.codex/config_a.toml"
docker_image = "usagi-worker:latest"

[[profiles]]
name = "account_b"
codex_config = "/home/user/.codex/config_b.toml"
docker_image = "usagi-worker:latest"
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class ProfileDef:
    """1つのCodex/CLIプロファイル定義。"""

    name: str
    codex_config: str = ""  # .codex/config.toml へのパス
    docker_image: str = "usagi-worker:latest"
    env: dict[str, str] = field(default_factory=dict)  # 追加環境変数


@dataclass
class ProfileStore:
    """プロファイル一覧。"""

    profiles: list[ProfileDef] = field(default_factory=list)

    def get(self, name: str) -> ProfileDef | None:
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def names(self) -> list[str]:
        return [p.name for p in self.profiles]


def load_profiles(path: Path) -> ProfileStore:
    """profiles.toml を読み込む。"""
    if not path.exists():
        return ProfileStore()

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    profiles: list[ProfileDef] = []
    for p in raw.get("profiles", []):
        name = str(p.get("name", ""))
        if not name:
            continue
        profiles.append(
            ProfileDef(
                name=name,
                codex_config=str(p.get("codex_config", "")),
                docker_image=str(p.get("docker_image", "usagi-worker:latest")),
                env=dict(p.get("env", {})),
            )
        )
    return ProfileStore(profiles=profiles)
