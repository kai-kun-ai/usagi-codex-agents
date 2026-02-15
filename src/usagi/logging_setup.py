"""logging の初期化。

- 詳細ログ: `.usagi/logs/usagi.log`
- 人間向けイベント: `events.log`（既存）

目的:
- watch/autopilot/tui/run の状況分析を容易にする
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(*, root: Path, level: str = "INFO") -> None:
    log_dir = root / ".usagi" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "usagi.log"

    # 既に設定済みなら二重設定しない
    if getattr(setup_logging, "_configured", False):
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # noisy lib
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    setup_logging._configured = True  # type: ignore[attr-defined]
