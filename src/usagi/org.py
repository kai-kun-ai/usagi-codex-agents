"""組織定義: TOMLから権力階層（指揮系統）つきのエージェント構成を読み込む。

このモジュールは「誰が誰に指示できるか」「誰をワーカーとして指定できるか」を
TOMLで明示できるようにするための基盤。

### 推奨TOML（新形式）

```toml
[[agents]]
id = "boss"
name = "社長うさぎ"
role = "boss"
model = "codex"
reports_to = ""
can_command = ["dev_mgr", "qa_mgr"]
personality = "personalities/boss.md"
memory = "memories/boss.md"

[[agents]]
id = "ghost"
name = "ゴースト社長"
role = "ghost_boss"
model = "codex"
reports_to = "boss"

[[agents]]
id = "dev_mgr"
name = "開発部長うさぎ"
role = "manager"
model = "codex"
reports_to = "boss"
can_command = ["w1", "w2", "w3", "w4"]

[[agents]]
id = "w1"
name = "ワーカー1"
role = "worker"
reports_to = "dev_mgr"
```

### 互換TOML（旧形式 / departments）

`[boss]` + `[[departments]]` を読み込み、内部のagentsに変換する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


ROLE_BOSS = "boss"
ROLE_GHOST_BOSS = "ghost_boss"
ROLE_MANAGER = "manager"
ROLE_WORKER = "worker"
ROLE_REVIEWER = "reviewer"


@dataclass
class AgentDef:
    """エージェント定義。"""

    id: str
    name: str
    role: str  # boss | ghost_boss | manager | worker | reviewer | ...
    model: str = "codex"

    emoji: str = ""  # 表示用（例: 🐰 🐶）
    reports_to: str = ""  # 上長id（最上位は空）
    can_command: list[str] = field(default_factory=list)  # 指揮できる相手のid

    personality_path: str | None = None
    memory_path: str | None = None

    # 人間が編集できるか / 上司が編集できるか は runtime 側のポリシーで制御する想定。

    def personality(self, base: Path | None = None) -> str:
        if not self.personality_path:
            return ""
        p = Path(self.personality_path)
        if base and not p.is_absolute():
            p = base / p
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def memory(self, base: Path | None = None) -> str:
        if not self.memory_path:
            return ""
        p = Path(self.memory_path)
        if base and not p.is_absolute():
            p = base / p
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def save_memory(self, content: str, base: Path | None = None) -> None:
        if not self.memory_path:
            return
        p = Path(self.memory_path)
        if base and not p.is_absolute():
            p = base / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


@dataclass
class Organization:
    """組織全体（agentsフラット + 階層情報）。"""

    agents: list[AgentDef] = field(default_factory=list)

    def find(self, agent_id: str) -> AgentDef | None:
        for a in self.agents:
            if a.id == agent_id:
                return a
        return None

    def by_name(self, name: str) -> AgentDef | None:
        for a in self.agents:
            if a.name == name:
                return a
        return None

    def subordinates_of(self, agent_id: str) -> list[AgentDef]:
        """直属の部下を返す（reports_toで判定）。"""
        return [a for a in self.agents if a.reports_to == agent_id]

    def can_command(self, commander_id: str, target_id: str) -> bool:
        """指揮権限チェック。明示can_command、または直属関係で判断。"""
        commander = self.find(commander_id)
        if not commander:
            return False
        if target_id in commander.can_command:
            return True
        # 直属の上司が部下に指示するのは許可
        target = self.find(target_id)
        if target and target.reports_to == commander_id:
            return True
        return False

    def pick_worker(
        self,
        *,
        worker_id: str | None = None,
        under_manager: str | None = None,
    ) -> AgentDef | None:
        """ワーカーを選ぶ。

        - worker_id 指定があれば最優先
        - under_manager 指定があれば、その配下の worker から選ぶ（先頭）
        """
        if worker_id:
            w = self.find(worker_id)
            return w if w and w.role == ROLE_WORKER else None

        if under_manager:
            subs = self.subordinates_of(under_manager)
            for a in subs:
                if a.role == ROLE_WORKER:
                    return a
        return None


def _parse_agent_new(data: dict) -> AgentDef:
    return AgentDef(
        id=str(data.get("id", "")),
        name=str(data.get("name", "名無しうさぎ")),
        role=str(data.get("role", ROLE_WORKER)),
        model=str(data.get("model", "codex")),
        emoji=str(data.get("emoji", "")),
        reports_to=str(data.get("reports_to", "")),
        can_command=list(data.get("can_command", []) or []),
        personality_path=data.get("personality"),
        memory_path=data.get("memory"),
    )


def load_org(path: Path) -> Organization:
    """TOMLファイルから組織定義を読み込む。"""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    # 新形式: [[agents]]
    if "agents" in raw:
        agents = [_parse_agent_new(a) for a in raw.get("agents", [])]
        # id必須
        agents = [a for a in agents if a.id]
        return Organization(agents=agents)

    # 旧形式: boss + departments
    return _load_org_legacy(raw)


def _load_org_legacy(raw: dict) -> Organization:
    agents: list[AgentDef] = []

    boss_data = raw.get("boss", {"name": "社長うさぎ"})
    boss = AgentDef(
        id="boss",
        name=boss_data.get("name", "社長うさぎ"),
        role=ROLE_BOSS,
        model=boss_data.get("model", "codex"),
        emoji=boss_data.get("emoji", ""),
        reports_to="",
        can_command=[],
        personality_path=boss_data.get("personality"),
        memory_path=boss_data.get("memory"),
    )
    agents.append(boss)

    # departments を manager/worker/reviewer に変換
    for idx, dept in enumerate(raw.get("departments", []), start=1):
        mgr_data = dept.get("manager", {})
        mgr_id = mgr_data.get("id", f"mgr{idx}")
        manager = AgentDef(
            id=mgr_id,
            name=mgr_data.get("name", f"部長うさぎ{idx}"),
            role=ROLE_MANAGER,
            model=mgr_data.get("model", "codex"),
            emoji=mgr_data.get("emoji", ""),
            reports_to="boss",
            can_command=[],
            personality_path=mgr_data.get("personality"),
            memory_path=mgr_data.get("memory"),
        )
        agents.append(manager)

        for midx, m in enumerate(dept.get("members", []), start=1):
            role = m.get("role", ROLE_WORKER)
            # coder→worker 互換
            if role == "coder":
                role = ROLE_WORKER
            mem_id = m.get("id", f"{mgr_id}_m{midx}")
            agents.append(
                AgentDef(
                    id=mem_id,
                    name=m.get("name", f"メンバー{midx}"),
                    role=role,
                    model=m.get("model", "codex"),
                    emoji=m.get("emoji", ""),
                    reports_to=mgr_id,
                    can_command=[],
                    personality_path=m.get("personality"),
                    memory_path=m.get("memory"),
                )
            )

    return Organization(agents=agents)


def default_org() -> Organization:
    """デフォルト組織（社長/開発部長/ワーカー/品質部長/レビュー）。"""
    return Organization(
        agents=[
            AgentDef(id="boss", name="社長うさぎ", role=ROLE_BOSS, reports_to=""),
            AgentDef(
                id="dev_mgr",
                name="開発部長うさぎ",
                role=ROLE_MANAGER,
                reports_to="boss",
                can_command=["worker1"],
            ),
            AgentDef(id="worker1", name="実装うさぎ", role=ROLE_WORKER, reports_to="dev_mgr"),
            AgentDef(
                id="qa_mgr",
                name="品質部長うさぎ",
                role=ROLE_MANAGER,
                reports_to="boss",
                can_command=["reviewer1"],
            ),
            AgentDef(id="reviewer1", name="監査うさぎ", role=ROLE_REVIEWER, reports_to="qa_mgr"),
        ]
    )
