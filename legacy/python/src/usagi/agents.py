"""うさぎさん株式会社のエージェント定義。

各エージェントは role と prompt_template を持ち、
OpenAI API（またはオフラインダミー）で応答を生成する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


class LLMBackend(Protocol):
    """LLM呼び出しの抽象。テスト時に差し替え可能。"""

    def generate(self, prompt: str, model: str) -> str: ...


class OpenAIBackend:
    """OpenAI Responses API を使う本番バックエンド。"""

    def __init__(self) -> None:
        self._client = OpenAI()

    def generate(self, prompt: str, model: str) -> str:
        resp = self._client.responses.create(model=model, input=prompt)
        return resp.output_text or ""


class OfflineBackend:
    """APIを呼ばずにダミー応答を返すバックエンド。"""

    def generate(self, prompt: str, model: str) -> str:
        return f"(offline: model={model}, prompt_length={len(prompt)})"


@dataclass
class AgentMessage:
    """エージェント間のメッセージ。ログ/レポートに残す。"""

    agent_name: str
    role: str
    content: str


@dataclass
class UsagiAgent:
    name: str
    role: str  # planner | coder | reviewer
    system_prompt: str

    def run(self, *, user_prompt: str, model: str, backend: LLMBackend) -> AgentMessage:
        full_prompt = f"{self.system_prompt}\n\n{user_prompt}"
        content = backend.generate(full_prompt, model=model)
        return AgentMessage(agent_name=self.name, role=self.role, content=content)


# デフォルトのうさぎさんたち
SHACHO_USAGI = UsagiAgent(
    name="社長うさぎ",
    role="planner",
    system_prompt=(
        "あなたは『うさぎさん株式会社』の社長うさぎです。\n"
        "与えられた要件から実行計画をMarkdownで作成してください。\n"
        "セクション: 方針 / 作業ステップ / リスク / 完了条件"
    ),
)

JISSOU_USAGI = UsagiAgent(
    name="実装うさぎ",
    role="coder",
    system_prompt=(
        "あなたは『うさぎさん株式会社』の実装うさぎです。\n"
        "計画に沿って最小構成の成果物を作ってください。\n"
        "変更は Unified diff 形式で出力してください（git diff と同様）。\n"
        "ルートに README.md を必ず作り、文章は日本語で書いてください。"
    ),
)

KANSA_USAGI = UsagiAgent(
    name="監査うさぎ",
    role="reviewer",
    system_prompt=(
        "あなたは『うさぎさん株式会社』の監査うさぎです。\n"
        "実装うさぎが生成した成果物をレビューし、問題点や改善案をMarkdownで報告してください。\n"
        "問題がなければ「LGTM」と明記してください。"
    ),
)
