"""表示名/絵文字などUI向け補助。"""

from __future__ import annotations

from usagi.org import (
    ROLE_BOSS,
    ROLE_GHOST_BOSS,
    ROLE_LEAD,
    ROLE_MANAGER,
    ROLE_REVIEWER,
    ROLE_WORKER,
    AgentDef,
)


def default_emoji_for_role(role: str) -> str:
    return {
        ROLE_BOSS: "🐰",
        ROLE_GHOST_BOSS: "👻",
        ROLE_MANAGER: "🦊",
        ROLE_LEAD: "🦉",
        ROLE_WORKER: "🐿️",
        ROLE_REVIEWER: "🦉",
    }.get(role, "🐾")


def display_name(agent: AgentDef) -> str:
    emoji = agent.emoji.strip() or default_emoji_for_role(agent.role)
    name = agent.name.strip() or agent.id
    return f"{emoji} {name}".strip()
