"""Discord連携（OpenClaw非依存）。

- 進捗投稿: `[AI名] ...` 形式
- メンション/STOPメッセージ受信: boss input へ流す（次のPRでキュー統合）

秘密情報は env で受け取る:
- USAGI_DISCORD_TOKEN
- USAGI_DISCORD_CHANNEL_ID

受信は allowlist を強制する（チャンネル/ユーザー）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import discord

from usagi.autopilot import request_stop
from usagi.boss_inbox import BossInput, write_boss_input


def sanitize_mentions(text: str) -> str:
    return text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")


def format_message(agent_name: str, text: str) -> str:
    return f"[{agent_name}] {sanitize_mentions(text)}"


@dataclass
class DiscordConfig:
    token_env: str = "USAGI_DISCORD_TOKEN"
    channel_id_env: str = "USAGI_DISCORD_CHANNEL_ID"
    user_allowlist: list[int] = field(default_factory=list)
    channel_allowlist: list[int] = field(default_factory=list)
    stop_phrases: list[str] = field(default_factory=lambda: ["STOP_USAGI"])

    project_root: str = "."  # STOPやinbox書き込み先

    def token(self) -> str:
        v = os.environ.get(self.token_env, "")
        if not v:
            raise RuntimeError(f"Discord token env not set: {self.token_env}")
        return v

    def channel_id(self) -> int:
        v = os.environ.get(self.channel_id_env, "")
        if not v:
            raise RuntimeError(f"Discord channel id env not set: {self.channel_id_env}")
        return int(v)


class DiscordClient:
    def __init__(self, cfg: DiscordConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._cfg = cfg

        @self._client.event
        async def on_ready():  # noqa: ANN202
            return None

        @self._client.event
        async def on_message(message: discord.Message):  # noqa: ANN202
            if message.author.bot:
                return

            if (
                self._cfg.channel_allowlist
                and message.channel.id not in self._cfg.channel_allowlist
            ):
                return
            if self._cfg.user_allowlist and message.author.id not in self._cfg.user_allowlist:
                return

            content = (message.content or "").strip()
            if not content:
                return

            root = Path(self._cfg.project_root)

            # STOP
            if content in self._cfg.stop_phrases:
                request_stop(root)
                return

            # mention -> boss input
            me = self._client.user
            if me and me in message.mentions:
                # remove mention tokens from content (simple)
                stripped = content.replace(f"<@{me.id}>", "").replace(f"<@!{me.id}>", "")
                stripped = stripped.strip()
                if stripped:
                    write_boss_input(
                        root,
                        BossInput(
                            source="discord_mention",
                            text=stripped,
                        ),
                    )
                return

    async def send(self, agent_name: str, text: str) -> None:
        channel = self._client.get_channel(self._cfg.channel_id())
        if channel is None:
            raise RuntimeError("Discord channel not found")
        await channel.send(
            format_message(agent_name, text),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    def run(self) -> None:
        self._client.run(self._cfg.token())
