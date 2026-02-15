"""認証プロファイル（複数ログインセッション）サポート。

目的:
- Codex/Claude CLI のログイン状態を「プロファイル」単位で切替可能にする
- Docker前提: プロファイルディレクトリを volume mount で差し替える

設計:
- codex: `~/.codex` が状態ディレクトリ
- claude: CLIの実装差があるため、デフォルトは `~/.claude` として扱い、必要に応じて上書き

注意:
- このモジュールは"ディレクトリの解決"のみ行い、秘密情報の中身は扱わない。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuthProfileConfig:
    codex_profiles_root: Path = Path(".usagi/sessions/codex")
    claude_profiles_root: Path = Path(".usagi/sessions/claude")

    codex_state_dirname: str = ".codex"
    claude_state_dirname: str = ".claude"


def codex_profile_dir(cfg: AuthProfileConfig, profile: str) -> Path:
    return cfg.codex_profiles_root / profile


def claude_profile_dir(cfg: AuthProfileConfig, profile: str) -> Path:
    return cfg.claude_profiles_root / profile


def ensure_profile_dirs(cfg: AuthProfileConfig, profile: str) -> None:
    codex_profile_dir(cfg, profile).mkdir(parents=True, exist_ok=True)
    claude_profile_dir(cfg, profile).mkdir(parents=True, exist_ok=True)
