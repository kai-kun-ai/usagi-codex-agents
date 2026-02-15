"""LLM backend switch: OpenAI / Ollama / CLI (codex/claude).

- OpenAI API
- Ollama (HTTP)
- codex/claude は外部CLIをstdin/stdoutで呼び出す（Docker前提）
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from openai import OpenAI

from usagi.cli_backend import CLIBackend


@dataclass
class LLMConfig:
    backend: str = "openai"  # openai | ollama | codex_cli | claude_cli
    model: str = "codex"

    # ollama
    ollama_url: str = "http://localhost:11434"

    # cli
    cli_command: list[str] | None = None
    home_dir: str | None = None  # プロファイル切替用途（~/.codex 等がHOME配下にある想定）


class LLM:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    def generate(self, prompt: str) -> str:
        if self.cfg.backend == "ollama":
            return self._ollama(prompt)
        if self.cfg.backend in {"codex_cli", "claude_cli"}:
            return self._cli(prompt)
        return self._openai(prompt)

    def _openai(self, prompt: str) -> str:
        # OpenAI client reads OPENAI_API_KEY env
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        resp = client.responses.create(model=self.cfg.model, input=prompt)
        return resp.output_text or ""

    def _ollama(self, prompt: str) -> str:
        url = self.cfg.ollama_url.rstrip("/") + "/api/generate"
        r = requests.post(
            url,
            json={"model": self.cfg.model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return str(data.get("response", ""))

    def _cli(self, prompt: str) -> str:
        cmd = self.cfg.cli_command
        if not cmd:
            # sensible defaults
            if self.cfg.backend == "codex_cli":
                cmd = ["codex"]
            else:
                cmd = ["claude"]

        env = None
        if self.cfg.home_dir:
            env = dict(**os.environ)
            env["HOME"] = self.cfg.home_dir

        # CLI側がモデル指定を受けられる場合のため、promptにモデル情報を含める
        full_prompt = f"[model={self.cfg.model}]\n{prompt}"
        return CLIBackend(cmd).run(full_prompt, env=env).strip()

