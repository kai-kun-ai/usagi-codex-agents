"""コンテキスト圧縮（Context Compression）。

目的:
- 長いレポート/ログをそのまま保持せず、要点だけを長期メモリ(md)へ残す
- LLMへの入力サイズを抑えつつ継続運用できるようにする

このPRではまず「圧縮フォーマット」と「ルールベース圧縮（オフライン）」を実装。
後続でLLM要約（OpenAI/Ollama）にも差し替え可能にする。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompressionConfig:
    max_chars: int = 6000


def compress_text(text: str, cfg: CompressionConfig | None = None) -> str:
    """簡易圧縮。

    - max_chars を超える場合は先頭/末尾を残し、間を省略
    - Markdownの見出しはなるべく残す
    """
    if cfg is None:
        cfg = CompressionConfig()

    t = text or ""
    if len(t) <= cfg.max_chars:
        return t

    head = int(cfg.max_chars * 0.6)
    tail = cfg.max_chars - head

    return (
        t[:head]
        + "\n\n<!-- usagi: compressed -->\n\n"
        + t[-tail:]
    )


def summarize_report_to_memory(report_md: str) -> str:
    """レポートMarkdownを長期メモリ向けに整形（ルールベース）。"""
    lines = report_md.splitlines()
    keep: list[str] = []

    # 目的/依頼内容/実行ログの先頭だけを拾う
    capture = False
    for line in lines:
        if line.startswith("## 目的"):
            capture = True
            keep.append(line)
            continue
        if line.startswith("## 依頼内容"):
            capture = True
            keep.append(line)
            continue
        if line.startswith("## 実行ログ"):
            capture = True
            keep.append(line)
            continue
        if line.startswith("## ") and not (
            line.startswith("## 目的")
            or line.startswith("## 依頼内容")
            or line.startswith("## 実行ログ")
        ):
            capture = False

        if capture:
            keep.append(line)

    if not keep:
        keep = ["# memory", "", "(no summary)"]

    return "\n".join(keep).strip() + "\n"
