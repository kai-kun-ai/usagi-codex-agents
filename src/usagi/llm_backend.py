"""LLM backend switch: OpenAI / Ollama.

このPRではOllamaの最小対応（HTTP）を追加。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from openai import OpenAI


@dataclass
class LLMConfig:
    backend: str = "openai"  # openai | ollama
    model: str = "codex"

    # ollama
    ollama_url: str = "http://localhost:11434"


class LLM:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    def generate(self, prompt: str) -> str:
        if self.cfg.backend == "ollama":
            return self._ollama(prompt)
        return self._openai(prompt)

    def _openai(self, prompt: str) -> str:
        # OpenAI client reads OPENAI_API_KEY env
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        resp = client.responses.create(model=self.cfg.model, input=prompt)
        return resp.output_text or ""

    def _ollama(self, prompt: str) -> str:
        url = self.cfg.ollama_url.rstrip("/") + "/api/generate"
        r = requests.post(url, json={"model": self.cfg.model, "prompt": prompt, "stream": False}, timeout=60)
        r.raise_for_status()
        data = r.json()
        return str(data.get("response", ""))
