"""秘書エージェント（🐻）: 対話→ input.md 整形。

方針:
- TUI上では社長と直接チャットせず、秘書と対話する。
- 秘書は会話ログを蓄積し、ユーザーが「社長に渡す」操作をした時に
  input spec Markdown を生成して inputs/ に配置する。
- 秘書の応答は LLM（Codex CLI）経由で生成する。
  offline 時はテンプレ応答にフォールバック。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SECRETARY_SYSTEM_PROMPT = """\
あなたは「🐻 秘書クマ」です。ユーザー（社長の代理人）と対話し、
社長（AIエージェント）への依頼内容を整理する役割です。

振る舞い:
- 丁寧だけど堅すぎない口調で話す
- ユーザーの要望を聞き出し、明確にする質問をする
- 曖昧な指示があれば確認する
- 「社長に渡す」と言われたら、内容を要約して確認する
- 短く簡潔に返す（1-3文程度）

あなたは秘書なので、技術的な実装はしません。
依頼内容の整理・確認・要約が仕事です。
"""

FALLBACK_REPLIES = [
    "了解。もう少し詳しく教えてもらえる？",
    "なるほど。他に伝えたいことはある？",
    "了解。社長に渡す内容として整理するね。",
    "わかった。何か制約や条件はある？",
    "OK。優先度はどのくらい？",
]


@dataclass
class SecretaryConfig:
    root: Path
    secretary_id: str = "secretary"
    secretary_name: str = "🐻 秘書クマ"
    offline: bool = False


@dataclass
class SecretaryAgent:
    """秘書エージェント: LLM経由で対話する。"""

    config: SecretaryConfig
    _history: list[dict[str, str]] = field(default_factory=list)
    _fallback_idx: int = 0

    def reply(self, user_message: str) -> str:
        """ユーザーメッセージに対して秘書として返答する。"""
        self._history.append({"role": "user", "content": user_message})

        if self.config.offline:
            return self._fallback_reply()

        try:
            return self._llm_reply()
        except Exception as e:
            logger.warning("secretary LLM failed, using fallback: %s", e)
            return self._fallback_reply()

    def _llm_reply(self) -> str:
        from usagi.llm_backend import LLM, LLMConfig

        llm = LLM(LLMConfig(backend="codex_cli", model="codex"))

        # 直近の対話をプロンプトに含める
        context = "\n".join(
            f"{'ユーザー' if m['role'] == 'user' else '秘書'}: {m['content']}"
            for m in self._history[-10:]
        )
        prompt = (
            f"{SECRETARY_SYSTEM_PROMPT}\n\n"
            f"## これまでの対話\n{context}\n\n"
            "秘書として短く返答してください。"
        )

        reply = llm.generate(prompt).strip()
        if not reply:
            return self._fallback_reply()

        self._history.append({"role": "assistant", "content": reply})
        return reply

    def summarize_for_boss(self, dialog_lines: list[str]) -> str:
        """対話ログを要約して社長向けの依頼仕様書を生成する。"""
        dialog_text = "\n".join(dialog_lines[-50:])

        if self.config.offline:
            return self._fallback_summary(dialog_text)

        try:
            return self._llm_summarize(dialog_text)
        except Exception as e:
            logger.warning("secretary summarize failed, using fallback: %s", e)
            return self._fallback_summary(dialog_text)

    def _llm_summarize(self, dialog_text: str) -> str:
        from usagi.llm_backend import LLM, LLMConfig

        llm = LLM(LLMConfig(backend="codex_cli", model="codex"))
        prompt = (
            f"{SECRETARY_SYSTEM_PROMPT}\n\n"
            "## タスク\n"
            "以下の対話ログから、社長（AIエージェント）への依頼内容を整理してください。\n"
            "出力フォーマット:\n"
            "```\n"
            "## 目的\n(依頼の目的を1-2文で)\n\n"
            "## やること\n- (具体的なタスクをリストで)\n\n"
            "## 制約\n- (あれば制約をリストで)\n"
            "```\n\n"
            f"## 対話ログ\n{dialog_text}\n"
        )
        result = llm.generate(prompt).strip()
        return result if result else self._fallback_summary(dialog_text)

    def _fallback_summary(self, dialog_text: str) -> str:
        """オフライン時のフォールバック: 対話ログをそのまま整形。"""
        return (
            "## 目的\n(秘書との対話から抽出)\n\n"
            "## やること\n(対話ログを参照)\n\n"
            "## 対話ログ\n" + dialog_text
        )

    def _fallback_reply(self) -> str:
        reply = FALLBACK_REPLIES[self._fallback_idx % len(FALLBACK_REPLIES)]
        self._fallback_idx += 1
        self._history.append({"role": "assistant", "content": reply})
        return reply


def secretary_log_path(root: Path) -> Path:
    return root / ".usagi/secretary.log"


def append_secretary_log(root: Path, who: str, text: str) -> None:
    log = secretary_log_path(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {who}: {text}\n")


def format_input_from_dialog(
    title: str,
    dialog_lines: list[str],
    *,
    summary: str | None = None,
) -> str:
    if summary:
        return (
            "---\n"
            f"project: {title}\n"
            "---\n\n"
            f"{summary}\n"
        )
    body = "\n".join(dialog_lines).strip()
    return (
        "# usagi spec\n\n"
        f"title: {title}\n\n"
        "## request\n\n"
        "以下は秘書(🐻)との対話ログから整形した依頼です。\n\n"
        f"{body}\n"
    )


def place_input_for_boss(
    root: Path,
    title: str,
    dialog_lines: list[str],
    *,
    summary: str | None = None,
) -> Path:
    inputs_dir = root / "inputs" / "secretary"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    p = inputs_dir / f"{ts}.md"
    p.write_text(
        format_input_from_dialog(
            title=title, dialog_lines=dialog_lines, summary=summary,
        ),
        encoding="utf-8",
    )
    return p
