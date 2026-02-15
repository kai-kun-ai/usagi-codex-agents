"""APIトークン管理。

複数のOpenAI APIキーをセキュアに管理する。
読み込み優先順位:
1. 環境変数 USAGI_API_KEYS (カンマ区切り)
2. 環境変数 OPENAI_API_KEY (単一)
3. TOMLの tokens セクション(キーファイルパス指定)

トークンはメモリ上でのみ保持し、ログやレポートには絶対に出力しない。
"""

from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class TokenPool:
    """複数APIキーをラウンドロビンで返すプール。"""

    _keys: list[str] = field(default_factory=list, repr=False)
    _cycle: itertools.cycle | None = field(  # type: ignore[type-arg]
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self._keys:
            self._cycle = itertools.cycle(self._keys)

    @property
    def available(self) -> bool:
        return len(self._keys) > 0

    @property
    def count(self) -> int:
        return len(self._keys)

    def next_key(self) -> str:
        """次のAPIキーを返す。なければエラー。"""
        if not self._cycle:
            msg = (
                "APIキーが設定されていません。\n"
                "USAGI_API_KEYS または OPENAI_API_KEY 環境変数を設定するか、"
                "TOML設定の [tokens] セクションを確認してください。"
            )
            raise RuntimeError(msg)
        return next(self._cycle)


def load_tokens(
    toml_path: Path | None = None,
) -> TokenPool:
    """トークンを読み込んでプールを作る。"""
    keys: list[str] = []

    # 1. USAGI_API_KEYS (カンマ区切り)
    env_keys = os.environ.get("USAGI_API_KEYS", "")
    if env_keys:
        keys.extend(
            k.strip() for k in env_keys.split(",") if k.strip()
        )

    # 2. OPENAI_API_KEY
    single = os.environ.get("OPENAI_API_KEY", "")
    if single and single not in keys:
        keys.append(single)

    # 3. TOML tokens section
    if toml_path and toml_path.exists():
        raw = tomllib.loads(
            toml_path.read_text(encoding="utf-8")
        )
        tokens_section = raw.get("tokens", {})

        # key_files: トークンファイルのリスト
        for kf in tokens_section.get("key_files", []):
            p = Path(kf)
            if not p.is_absolute() and toml_path.parent:
                p = toml_path.parent / p
            if p.exists():
                content = p.read_text(encoding="utf-8").strip()
                if content and content not in keys:
                    keys.append(content)

        # direct keys (非推奨だが対応)
        for k in tokens_section.get("keys", []):
            if k and k not in keys:
                keys.append(k)

    return TokenPool(_keys=keys)
