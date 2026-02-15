"""承認フロー付きパイプライン（社長→部長→課長→ワーカー）。

要件（最小）:
- 社長(boss)は計画/意思決定のみ（実装しない）
- ワーカー(worker)が実装する
- 課長(lead)がレビューして承認/差戻し
- 部長(manager)が課ブランチを main にマージして良いか判断（運用ポリシーとして）
- 重大判断は 3人格多数決（否決なら秘書経由で人間に質問を投げる）

このモジュールは watch/autopilot から呼ばれることを想定し、
レポート用メッセージログも返す。

注意:
- 現時点では「課ブランチ/マージの強制」や「Docker sandbox実行」は段階的。
  まずはロール/階層とレビュー・判断の流れを一気通貫で動かす。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from usagi.agents import AgentMessage, LLMBackend, OfflineBackend, OpenAIBackend, UsagiAgent
from usagi.approval import Assignment, assign_default
from usagi.git_ops import team_branch
from usagi.org import AgentDef, Organization
from usagi.report import render_report
from usagi.runtime import RuntimeMode
from usagi.secretary import place_input_for_boss
from usagi.spec import UsagiSpec
from usagi.vote import Vote, decide_2of3, parse_decision


@dataclass
class ApprovalRunResult:
    report: str
    messages: list[AgentMessage] = field(default_factory=list)
    assignment: Assignment | None = None


def _agent_for(agent: AgentDef, *, role: str, system_prompt: str) -> UsagiAgent:
    return UsagiAgent(name=agent.name or agent.id, role=role, system_prompt=system_prompt)


def run_approval_pipeline(
    *,
    spec: UsagiSpec,
    workdir: Path,
    model: str,
    offline: bool,
    org: Organization,
    runtime: RuntimeMode,
    root: Path,
) -> ApprovalRunResult:
    backend: LLMBackend = OfflineBackend() if offline else OpenAIBackend()
    started = datetime.now(tz=UTC).isoformat()

    # assignment
    assignment = assign_default(org, boss_id=runtime.boss_id)
    boss = org.find(assignment.boss_id)
    manager = org.find(assignment.manager_id)
    lead = org.find(assignment.lead_id)
    worker = org.find(assignment.worker_id)
    if not (boss and manager and lead and worker):
        raise RuntimeError("assignment invalid")

    msgs: list[AgentMessage] = []
    actions: list[str] = []

    # boss: plan (意思決定)
    boss_agent = _agent_for(
        boss,
        role="planner",
        system_prompt=(
            "あなたは社長(boss)です。絶対に実装しません。\n"
            "与えられた依頼を『部長/課長/ワーカーに委任できる形』に分解し、\n"
            "方針/手順/リスク/完了条件 をMarkdownで書いてください。"
        ),
    )
    plan = boss_agent.run(user_prompt=_build_plan_prompt(spec), model=model, backend=backend)
    msgs.append(plan)

    # worker: implement (差分)
    worker_agent = _agent_for(
        worker,
        role="coder",
        system_prompt=(
            "あなたはワーカー(worker)です。\n"
            "課長のレビューを通すため、変更は小さく安全に。\n"
            "変更は Unified diff 形式で出力してください。"
        ),
    )
    impl_prompt = (
        f"社長の方針/計画:\n\n{plan.content}\n\n"
        f"プロジェクト名: {spec.project}\n"
        f"課ブランチ: {team_branch(lead.id)}\n"
    )
    impl = worker_agent.run(user_prompt=impl_prompt, model=model, backend=backend)
    msgs.append(impl)

    # apply patch (従来通り workdir に apply)
    workdir.mkdir(parents=True, exist_ok=True)
    patch_path = workdir / ".usagi.patch"
    patch_path.write_text(impl.content, encoding="utf-8")
    actions.append(f"write {patch_path.name}")

    # lead: review/approve
    lead_agent = _agent_for(
        lead,
        role="reviewer",
        system_prompt=(
            "あなたは課長(lead)でレビュー責任者です。\n"
            "ワーカーの差分をレビューし、\n"
            "承認する場合は必ず 'APPROVE' と書き、差戻しなら 'CHANGES_REQUESTED' と書いてください。"
        ),
    )
    review_prompt = (
        f"ワーカー差分:\n\n{impl.content}\n\n"
        "判断: APPROVE / CHANGES_REQUESTED\n"
    )
    lead_review = lead_agent.run(user_prompt=review_prompt, model=model, backend=backend)
    msgs.append(lead_review)

    approved_by_lead = "APPROVE" in lead_review.content.upper()

    # manager: merge decision (課ブランチをmainへ)
    manager_agent = _agent_for(
        manager,
        role="planner",
        system_prompt=(
            "あなたは部長(manager)です。\n"
            "課長のレビュー結果を踏まえ、課ブランチを main にマージしてよいか判断してください。\n"
            "判断は 'MERGE_OK' / 'NEED_MORE_REVIEW' / 'ESCALATE_TO_BOSS' のいずれかを必ず含めてください。"
        ),
    )
    manager_prompt = (
        f"社長計画:\n\n{plan.content}\n\n"
        f"課長レビュー:\n\n{lead_review.content}\n\n"
        f"課ブランチ: {team_branch(lead.id)}\n"
        "判断: MERGE_OK / NEED_MORE_REVIEW / ESCALATE_TO_BOSS\n"
    )
    manager_decision = manager_agent.run(user_prompt=manager_prompt, model=model, backend=backend)
    msgs.append(manager_decision)

    decision_text = manager_decision.content.upper()

    # critical path: escalation or lead did not approve
    need_vote = (not approved_by_lead) or ("ESCALATE_TO_BOSS" in decision_text)

    if need_vote and runtime.vote.enabled:
        votes = _run_3persona_vote(
            backend=backend,
            model=model,
            org=org,
            runtime=runtime,
            context=(
                f"依頼: {spec.project}\n\n"
                f"社長計画:\n{plan.content}\n\n"
                f"課長レビュー:\n{lead_review.content}\n\n"
                f"部長判断:\n{manager_decision.content}\n"
            ),
        )
        # ログに残す
        for v in votes:
            msgs.append(
                AgentMessage(
                    agent_name=v.voter_id,
                    role="vote",
                    content=f"decision={v.decision}\nreason={v.reason}",
                )
            )

        outcome = decide_2of3(votes)
        if outcome != "approve":
            # 否決またはtieは秘書経由で人間に質問
            questions = _build_questions_for_human(
                spec=spec,
                approved_by_lead=approved_by_lead,
                manager_decision=manager_decision.content,
                outcome=outcome,
            )
            place_input_for_boss(
                root=root,
                title=f"要確認: {spec.project}",
                dialog_lines=questions,
            )
            actions.append("secretary: ask human")

    report = render_report(
        spec=spec,
        workdir=workdir,
        started=started,
        messages=msgs,
        actions=actions,
    )

    return ApprovalRunResult(report=report, messages=msgs, assignment=assignment)


def _build_plan_prompt(spec: UsagiSpec) -> str:
    tasks = "\n".join([f"- {t}" for t in spec.tasks]) if spec.tasks else "(なし)"
    constraints = "\n".join([f"- {c}" for c in spec.constraints]) if spec.constraints else "(なし)"
    return (
        f"目的:\n{spec.objective}\n\n"
        f"背景:\n{spec.context}\n\n"
        f"やること:\n{tasks}\n\n"
        f"制約:\n{constraints}\n"
    )


def _run_3persona_vote(
    *,
    backend: LLMBackend,
    model: str,
    org: Organization,
    runtime: RuntimeMode,
    context: str,
) -> list[Vote]:
    votes: list[Vote] = []
    voter_ids = list(runtime.vote.voters)
    if len(voter_ids) < 3:
        # 最低3人格が前提
        voter_ids = (voter_ids + [runtime.boss_id, "ghost_boss", "secretary"])[:3]

    for vid in voter_ids[:3]:
        a = org.find(vid)
        name = a.name if a else vid
        agent = UsagiAgent(
            name=name,
            role="vote",
            system_prompt=(
                "あなたは社長の人格の一つです。\n"
                "以下の判断に対し、approve / block / abstain のいずれかで投票してください。\n"
                "出力に必ず decision: approve|block|abstain を含めてください。"
            ),
        )
        resp = agent.run(user_prompt=context, model=model, backend=backend)
        decision = parse_decision(resp.content)
        votes.append(Vote(voter_id=vid, decision=decision, reason=resp.content.strip()))
    return votes


def _build_questions_for_human(
    *,
    spec: UsagiSpec,
    approved_by_lead: bool,
    manager_decision: str,
    outcome: str,
) -> list[str]:
    lines = [
        "以下の判断が割れました。人間の意思決定が必要です。",
        "",
        f"- project: {spec.project}",
        f"- lead_approved: {approved_by_lead}",
        f"- manager_decision: {manager_decision.strip()}",
        f"- 3人格投票: {outcome}",
        "",
        "質問:",
        "- この変更を進めてよいですか？（Yes/No）",
        "- リスク許容度は？（低/中/高）",
        "- 追加で見たい確認事項は？",
    ]
    return lines
