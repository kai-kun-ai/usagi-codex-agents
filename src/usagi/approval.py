"""承認フロー（社長→部長→課長→ワーカー）。

目的:
- 組織（org.toml）の階層に基づいて担当者を選び、
  ワーカーの成果物を課長(lead)が承認し、部長(manager)がマージ可否を判断する。

現段階は「選定ロジック + 最小の判定データ構造」を提供する。
実際のコンテナ実行/PR作成/マージ等の配線は watch/pipeline 側で行う。
"""

from __future__ import annotations

from dataclasses import dataclass

from usagi.org import ROLE_LEAD, ROLE_MANAGER, ROLE_WORKER, AgentDef, Organization


@dataclass(frozen=True)
class Assignment:
    boss_id: str
    manager_id: str
    lead_id: str
    worker_id: str


def choose_first_manager(org: Organization, *, boss_id: str = "boss") -> AgentDef:
    mgrs = [a for a in org.subordinates_of(boss_id) if a.role == ROLE_MANAGER]
    if not mgrs:
        raise ValueError("no manager under boss")
    return mgrs[0]


def choose_first_lead(org: Organization, *, manager_id: str) -> AgentDef:
    leads = [a for a in org.subordinates_of(manager_id) if a.role == ROLE_LEAD]
    if not leads:
        raise ValueError(f"no lead under manager: {manager_id}")
    return leads[0]


def choose_first_worker(org: Organization, *, lead_id: str) -> AgentDef:
    workers = [a for a in org.subordinates_of(lead_id) if a.role == ROLE_WORKER]
    if not workers:
        raise ValueError(f"no worker under lead: {lead_id}")
    return workers[0]


def assign_default(org: Organization, *, boss_id: str = "boss") -> Assignment:
    mgr = choose_first_manager(org, boss_id=boss_id)
    lead = choose_first_lead(org, manager_id=mgr.id)
    worker = choose_first_worker(org, lead_id=lead.id)
    return Assignment(boss_id=boss_id, manager_id=mgr.id, lead_id=lead.id, worker_id=worker.id)
