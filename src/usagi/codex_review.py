"""Codex CLI review helpers."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from usagi.agents import AgentMessage


def run_codex_review(*, diff_text: str, cwd: Path) -> AgentMessage:
    """Run `codex review` against a diff (text).

    We intentionally review the diff only (not full repo) to keep role separation.

    Output must include a final decision line:
    - APPROVE or CHANGES_REQUESTED
    """

    log = logging.getLogger(__name__)

    diff_text = diff_text or ""
    prompt = (
        "あなたは課長(lead)のレビュー担当です。\n"
        "以下のUnified diffをレビューして、短くレビューコメントを書いてください。\n"
        "最後の行に必ず `APPROVE` か `CHANGES_REQUESTED` のどちらかだけを書いてください。\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(diff_text)
        diff_path = Path(f.name)

    try:
        cmd = ["codex", "review", "--file", str(diff_path), "--message", prompt]
        log.info("codex review cmd: %s", " ".join(cmd))
        r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)

        if r.returncode != 0:
            tail = "\n".join((r.stderr or "").splitlines()[-50:])
            if tail:
                log.error("codex review failed stderr tail:\n%s", tail)
            return AgentMessage(
                agent_name="lead",
                role="reviewer",
                content=(
                    f"(codex review failed with code {r.returncode})\n"
                    "CHANGES_REQUESTED\n"
                ),
            )

        out = (r.stdout or "").strip()
        if not out:
            return AgentMessage(agent_name="lead", role="reviewer", content="CHANGES_REQUESTED")

        # Ensure decision line exists
        up = out.upper().splitlines()
        if not any(line.strip() in {"APPROVE", "CHANGES_REQUESTED"} for line in up[-3:]):
            out = out.rstrip() + "\n\nCHANGES_REQUESTED\n"

        return AgentMessage(agent_name="lead", role="reviewer", content=out)
    finally:
        diff_path.unlink(missing_ok=True)
