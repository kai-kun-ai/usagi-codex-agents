"""runtime: ツールとしての動作モードを定義する。

- 完全自走（CI greenなら自動マージ）
- マージは常に人間確認
- 投票（2/3）で進行

設定ファイル: `usagi.runtime.toml`（デフォルト）

秘密情報（Discord token / API key など）はこのファイルに直書きしない。
環境変数またはトークンファイル参照で扱う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class MergePolicy:
    policy: str = "ask_human"  # never | ask_human | auto_on_ci_green
    require_human_on: list[str] = field(default_factory=list)


@dataclass
class VotePolicy:
    enabled: bool = True
    threshold: str = "2of3"
    voters: list[str] = field(default_factory=lambda: ["boss", "ghost_boss", "reviewer"])
    ask_human_on_tie: bool = True


@dataclass
class PromptCompression:
    enabled: bool = True
    max_chars_default: int = 2500
    max_chars_vote: int = 3500


@dataclass
class AutopilotConfig:
    enabled: bool = False
    inputs_dir: str = "inputs"
    outputs_dir: str = "outputs"
    work_root: str = "work"
    stop_commands: list[str] = field(default_factory=lambda: ["STOP_USAGI", "usagi autopilot stop"])


@dataclass
class RuntimeMode:
    name: str = "manual"
    merge: MergePolicy = field(default_factory=MergePolicy)
    vote: VotePolicy = field(default_factory=VotePolicy)
    autopilot: AutopilotConfig = field(default_factory=AutopilotConfig)

    gh_enabled: bool = False
    docker_required: bool = True

    boss_id: str = "boss"  # PR merge等の実行権限者
    worker_pool_size: int = 5  # autopilot/watch で同時起動するworkerコンテナ数
    use_worker_container: bool = True  # worker処理を別コンテナで実行する
    worker_image_build: str = "auto"  # auto | never
    input_postprocess: str = "keep"  # keep | trash

    compress: PromptCompression = field(default_factory=PromptCompression)


def load_runtime(path: Path | None = None) -> RuntimeMode:
    if path is None:
        path = Path("usagi.runtime.toml")
    if not path.exists():
        return RuntimeMode()

    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    mode = raw.get("mode", {})
    merge = raw.get("merge", {})
    vote = raw.get("vote", {})
    autopilot = raw.get("autopilot", {})

    system = raw.get("system", {})

    return RuntimeMode(
        name=str(mode.get("name", "manual")),
        merge=MergePolicy(
            policy=str(merge.get("policy", "ask_human")),
            require_human_on=list(merge.get("require_human_on", []) or []),
        ),
        vote=VotePolicy(
            enabled=bool(vote.get("enabled", True)),
            threshold=str(vote.get("threshold", "2of3")),
            voters=list(vote.get("voters", ["boss", "ghost_boss", "reviewer"]) or []),
            ask_human_on_tie=bool(vote.get("ask_human_on_tie", True)),
        ),
        autopilot=AutopilotConfig(
            enabled=bool(autopilot.get("enabled", False)),
            inputs_dir=str(autopilot.get("inputs_dir", "inputs")),
            outputs_dir=str(autopilot.get("outputs_dir", "outputs")),
            work_root=str(autopilot.get("work_root", "work")),
            stop_commands=list(autopilot.get("stop_commands", []) or ["STOP_USAGI"]),
        ),
        gh_enabled=bool(system.get("gh_enabled", False)),
        docker_required=bool(system.get("docker_required", True)),
        boss_id=str(system.get("boss_id", "boss")),
        worker_pool_size=int(system.get("worker_pool_size", 5)),
        use_worker_container=bool(system.get("use_worker_container", True)),
        worker_image_build=str(system.get("worker_image_build", "auto")),
        input_postprocess=str(system.get("input_postprocess", "keep")),
        compress=PromptCompression(
            enabled=bool(system.get("compress", {}).get("enabled", True)),
            max_chars_default=int(system.get("compress", {}).get("max_chars_default", 2500)),
            max_chars_vote=int(system.get("compress", {}).get("max_chars_vote", 3500)),
        ),
    )
