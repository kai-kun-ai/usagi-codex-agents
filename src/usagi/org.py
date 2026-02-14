"""組織定義: TOMLから階層的なエージェント構成を読み込む。

TOML例:
```toml
[boss]
name = "社長うさぎ"
role = "boss"
model = "gpt-4.1"
personality = "personalities/boss.md"
memory = "memories/boss.md"

[[departments]]
name = "開発部"
manager.name = "開発部長うさぎ"
manager.role = "manager"
manager.model = "codex"
manager.personality = "personalities/dev_manager.md"
manager.memory = "memories/dev_manager.md"

  [[departments.members]]
  name = "実装うさぎA"
  role = "coder"
  model = "codex"
  personality = "personalities/coder_a.md"
  memory = "memories/coder_a.md"

[[departments]]
name = "レビュー部"
manager.name = "レビュー部長うさぎ"
manager.role = "manager"
...
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class AgentDef:
    """エージェント定義。TOMLから読み込まれる。"""

    name: str
    role: str  # boss | manager | coder | reviewer | ...
    model: str = "codex"
    personality_path: str | None = None
    memory_path: str | None = None
    can_edit_subordinates: bool = False

    def personality(self, base: Path | None = None) -> str:
        """性格定義Markdownを読み込む。"""
        if not self.personality_path:
            return ""
        p = Path(self.personality_path)
        if base and not p.is_absolute():
            p = base / p
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def memory(self, base: Path | None = None) -> str:
        """メモリMarkdownを読み込む。"""
        if not self.memory_path:
            return ""
        p = Path(self.memory_path)
        if base and not p.is_absolute():
            p = base / p
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def save_memory(self, content: str, base: Path | None = None) -> None:
        """メモリを書き込む。"""
        if not self.memory_path:
            return
        p = Path(self.memory_path)
        if base and not p.is_absolute():
            p = base / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


@dataclass
class Department:
    """部署。マネージャー + メンバーリスト。"""

    name: str
    manager: AgentDef
    members: list[AgentDef] = field(default_factory=list)


@dataclass
class Organization:
    """組織全体。boss + 部署リスト。"""

    boss: AgentDef
    departments: list[Department] = field(default_factory=list)

    def all_agents(self) -> list[AgentDef]:
        """全エージェントをフラットに返す。"""
        agents = [self.boss]
        for dept in self.departments:
            agents.append(dept.manager)
            agents.extend(dept.members)
        return agents

    def find_agent(self, name: str) -> AgentDef | None:
        """名前でエージェントを検索。"""
        for a in self.all_agents():
            if a.name == name:
                return a
        return None


def _parse_agent(data: dict, *, is_boss: bool = False) -> AgentDef:
    return AgentDef(
        name=data.get("name", "名無しうさぎ"),
        role=data.get("role", "coder"),
        model=data.get("model", "codex"),
        personality_path=data.get("personality"),
        memory_path=data.get("memory"),
        can_edit_subordinates=is_boss or data.get("role") == "manager",
    )


def load_org(path: Path) -> Organization:
    """TOMLファイルから組織定義を読み込む。"""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    boss_data = raw.get("boss", {"name": "社長うさぎ", "role": "boss"})
    boss = _parse_agent(boss_data, is_boss=True)

    departments: list[Department] = []
    for dept_data in raw.get("departments", []):
        mgr_data = dept_data.get("manager", {})
        manager = _parse_agent(mgr_data)
        manager.can_edit_subordinates = True

        members = [
            _parse_agent(m) for m in dept_data.get("members", [])
        ]
        departments.append(
            Department(
                name=dept_data.get("name", "無名部"),
                manager=manager,
                members=members,
            )
        )

    return Organization(boss=boss, departments=departments)


def default_org() -> Organization:
    """デフォルト組織（後方互換: 社長/実装/監査の3匹）。"""
    return Organization(
        boss=AgentDef(
            name="社長うさぎ",
            role="boss",
            model="codex",
            can_edit_subordinates=True,
        ),
        departments=[
            Department(
                name="開発部",
                manager=AgentDef(
                    name="開発部長うさぎ",
                    role="manager",
                    model="codex",
                    can_edit_subordinates=True,
                ),
                members=[
                    AgentDef(name="実装うさぎ", role="coder"),
                ],
            ),
            Department(
                name="品質管理部",
                manager=AgentDef(
                    name="品質部長うさぎ",
                    role="manager",
                    model="codex",
                    can_edit_subordinates=True,
                ),
                members=[
                    AgentDef(name="監査うさぎ", role="reviewer"),
                ],
            ),
        ],
    )
