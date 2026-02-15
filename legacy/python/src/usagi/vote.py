"""vote: ゴースト社長など複数エージェントで意思決定する。

現段階は「投票ロジックの土台」だけ。
実際のLLM呼び出し・人格/メモリ連携は後続PRで統合する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Vote:
    voter_id: str
    decision: str  # approve | block | abstain
    reason: str = ""


def parse_decision(text: str) -> str:
    t = (text or "").lower()
    if "approve" in t or "go" in t or "進め" in t:
        return "approve"
    if "block" in t or "stop" in t or "止め" in t:
        return "block"
    return "abstain"


def decide_2of3(votes: list[Vote]) -> str:
    """2/3ルールの判定。

    returns: approve | block | tie
    """
    approve = sum(1 for v in votes if v.decision == "approve")
    block = sum(1 for v in votes if v.decision == "block")

    if approve >= 2:
        return "approve"
    if block >= 2:
        return "block"
    return "tie"
