"""Prompt compaction utilities.

We already have `usagi.compress.compress_text`, but it was not wired into the
actual prompt construction. This module centralizes compaction + logging so we
can tune token usage.

Policy:
- Compact large inputs before putting them into prompts.
- Log before/after sizes to `.usagi/logs/usagi.log` via standard logging.
- Avoid changing semantics too much; keep heads/tails.
"""

from __future__ import annotations

import logging

from usagi.compress import CompressionConfig, compress_text


DEFAULT_MAX_CHARS = 2500


def compact_for_prompt(text: str, *, stage: str, max_chars: int = DEFAULT_MAX_CHARS, enabled: bool = True) -> str:
    """Compact long text for prompt usage and log the ratio."""

    if not enabled:
        return text or ""

    log = logging.getLogger(__name__)
    before = len(text or "")
    out = compress_text(text or "", CompressionConfig(max_chars=max_chars))
    after = len(out or "")
    if before > max_chars:
        ratio = 0.0 if before == 0 else (after / before)
        log.info(
            "prompt_compact stage=%s before_chars=%d after_chars=%d ratio=%.3f max_chars=%d",
            stage,
            before,
            after,
            ratio,
            max_chars,
        )
    return out
