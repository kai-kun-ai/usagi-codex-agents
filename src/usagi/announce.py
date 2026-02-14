"""Discord 進捗宣言（Webhook）

discord.py の Webhook 機能を利用して、
`[AI名] ...` 形式で開始/終了を投稿する。

env:
- USAGI_DISCORD_WEBHOOK_URL
"""

from __future__ import annotations

import asyncio
import os

import discord

from usagi.discord_client import format_message


def webhook_available() -> bool:
    return bool(os.environ.get("USAGI_DISCORD_WEBHOOK_URL", ""))


def announce(agent_name: str, text: str) -> None:
    url = os.environ.get("USAGI_DISCORD_WEBHOOK_URL", "")
    if not url:
        return

    async def _send() -> None:
        wh = discord.Webhook.from_url(url, client=discord.Client(intents=discord.Intents.none()))
        await wh.send(
            format_message(agent_name, text),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    try:
        asyncio.run(_send())
    except RuntimeError:
        # already running loop (rare in CLI). fallback: create task
        loop = asyncio.get_event_loop()
        loop.create_task(_send())
