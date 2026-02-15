"""起動時セルフチェック。

- APIキーの有無
- OpenAI APIの疎通（任意）

注意:
- secrets をログに出さない
- 失敗しても例外で落とさず、events.log に記録して続行
"""

from __future__ import annotations

import os
from pathlib import Path

from usagi.llm_backend import LLM, LLMConfig
from usagi.runtime import RuntimeMode


def _event(event_log_path: Path | None, msg: str) -> None:
    if event_log_path is None:
        return
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    from time import strftime

    ts = strftime("%Y-%m-%d %H:%M:%S")
    with event_log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def run_startup_check(
    *,
    runtime: RuntimeMode,
    model: str,
    offline: bool,
    event_log_path: Path | None,
) -> None:
    """起動時に実行して良い軽量チェック。"""

    if offline:
        _event(event_log_path, "startup_check: offline -> skip")
        return

    # 現状は OpenAI API が主。codex_cli 等に移行する前提。
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    _event(event_log_path, f"startup_check: OPENAI_API_KEY={'set' if has_openai else 'missing'}")

    if not has_openai:
        return

    try:
        llm = LLM(LLMConfig(backend="openai", model=model))
        out = llm.generate("healthcheck: reply with OK")
        ok = "OK" in (out or "")
        _event(event_log_path, f"startup_check: openai_api={'ok' if ok else 'unexpected'}")
    except Exception as e:  # pragma: no cover
        _event(event_log_path, f"startup_check: openai_api=fail ({type(e).__name__})")
