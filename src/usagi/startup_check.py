"""起動時セルフチェック。

目的:
- Codex CLI が利用可能かを events.log に残す
- API疎通を軽く試す（任意）。失敗してもwatch/TUIを落とさない。

注意:
- secrets をログに出さない
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from usagi.runtime import RuntimeMode


def _event(event_log_path: Path | None, msg: str) -> None:
    if event_log_path is None:
        return
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with event_log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _check_codex_cli(event_log_path: Path | None) -> bool:
    """codex CLI が PATH 上にあるかチェック。"""
    found = shutil.which("codex") is not None
    _event(event_log_path, f"startup_check: codex_cli={'found' if found else 'not_found'}")
    return found


def _check_claude_cli(event_log_path: Path | None) -> bool:
    """claude CLI が PATH 上にあるかチェック。"""
    found = shutil.which("claude") is not None
    _event(event_log_path, f"startup_check: claude_cli={'found' if found else 'not_found'}")
    return found


def _check_codex_auth(event_log_path: Path | None) -> bool:
    """codex CLI で軽い疎通テスト（codex exec でヘルスチェック）。"""
    try:
        result = subprocess.run(
            ["codex", "exec", "reply with just OK"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        ok = result.returncode == 0 and "OK" in (result.stdout or "")
        _event(
            event_log_path,
            f"startup_check: codex_auth={'ok' if ok else 'fail'}",
        )
        return ok
    except Exception as e:
        _event(event_log_path, f"startup_check: codex_auth=fail ({type(e).__name__})")
        return False


def run_startup_check(
    *,
    runtime: RuntimeMode,
    model: str,
    offline: bool,
    event_log_path: Path | None,
) -> None:
    if offline:
        _event(event_log_path, "startup_check: offline -> skip")
        return

    # CLI の存在チェック
    has_codex = _check_codex_cli(event_log_path)
    _check_claude_cli(event_log_path)

    # Codex CLI があれば疎通テスト
    if has_codex:
        _check_codex_auth(event_log_path)
