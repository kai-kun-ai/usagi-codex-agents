"""Skills 対応（超軽量）。

ここでいう Skills は「外部コマンドテンプレ」を指す。
Docker運用を前提に、コンテナ内で安全に実行する。

- skills.toml に定義
- `usagi skill run <name>` で実行（このPRでは枠だけ）
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    command: list[str]
