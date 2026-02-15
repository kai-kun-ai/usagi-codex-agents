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

from usagi.agents import AgentMessage, CodexCLIBackend, LLMBackend, OfflineBackend, UsagiAgent
from usagi.approval import Assignment, assign_default
from usagi.artifacts import write_artifact
from usagi.prompt_compact import compact_for_prompt
from usagi.git_ops import team_branch
from usagi.org import AgentDef, Organization
from usagi.report import render_report
from usagi.runtime import RuntimeMode
from usagi.secretary import place_input_for_boss
from usagi.spec import UsagiSpec
from usagi.state import AgentStatus, load_status, save_status
from usagi.mailbox import deliver_markdown
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
    status_path: Path | None = None,
    repo_root: Path | None = None,
) -> ApprovalRunResult:
    backend: LLMBackend = OfflineBackend() if offline else CodexCLIBackend()
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

    def _set(agent_id: str, name: str, state: str, task: str) -> None:
        if status_path is None:
            return
        st = load_status(status_path)
        st.set(AgentStatus(agent_id=agent_id, name=name, state=state, task=task))
        save_status(status_path, st)

    # artifacts
    write_artifact(
        workdir,
        "00-spec.md",
        _build_plan_prompt(spec),
    )

    # boss: plan (意思決定)
    _set(boss.id, boss.name or boss.id, "working", f"plan: {spec.project or 'default'}")
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
    write_artifact(workdir, "10-boss-plan.md", plan.content)
    _set(boss.id, boss.name or boss.id, "idle", "")

    # worker: implement (差分)
    # DooD は複雑なため、まずは worktree 方式（ローカルgit）に寄せる。
    _set(worker.id, worker.name or worker.id, "working", f"impl: {spec.project or 'default'}")
    impl = _run_worker_step_worktree(
        worker=worker,
        lead=lead,
        plan=plan,
        spec=spec,
        workdir=workdir,
        repo_root=repo_root or workdir,
        model=model,
        backend=backend,
        runtime=runtime,
        offline=offline,
    )
    msgs.append(impl)
    write_artifact(workdir, "20-worker-impl.diff", impl.content)
    _set(worker.id, worker.name or worker.id, "idle", "")

    # apply patch (従来通り workdir に apply)
    workdir.mkdir(parents=True, exist_ok=True)
    patch_path = workdir / ".usagi.patch"
    patch_path.write_text(impl.content, encoding="utf-8")
    actions.append(f"write {patch_path.name}")

    # lead: review/approve
    _set(lead.id, lead.name or lead.id, "working", f"review: {spec.project or 'default'}")
    lead_agent = _agent_for(
        lead,
        role="reviewer",
        system_prompt=(
            "あなたは課長(lead)でレビュー責任者です。\n"
            "ワーカーの差分をレビューし、\n"
            "承認する場合は必ず 'APPROVE' と書き、差戻しなら 'CHANGES_REQUESTED' と書いてください。"
        ),
    )
    impl_compact = compact_for_prompt(
        impl.content,
        stage="lead_review_impl",
        max_chars=runtime.compress.max_chars_default,
        enabled=runtime.compress.enabled,
    )
    review_prompt = (
        f"ワーカー差分(圧縮):\n\n{impl_compact}\n\n"
        "判断: APPROVE / CHANGES_REQUESTED\n"
    )
    lead_review = lead_agent.run(user_prompt=review_prompt, model=model, backend=backend)
    msgs.append(lead_review)
    write_artifact(workdir, "30-lead-review.md", lead_review.content)
    _set(lead.id, lead.name or lead.id, "idle", "")

    approved_by_lead = "APPROVE" in lead_review.content.upper()

    # manager: merge decision (課ブランチをmainへ)
    _set(manager.id, manager.name or manager.id, "working", f"decision: {spec.project or 'default'}")
    manager_agent = _agent_for(
        manager,
        role="planner",
        system_prompt=(
            "あなたは部長(manager)です。\n"
            "課長のレビュー結果を踏まえ、課ブランチを main にマージしてよいか判断してください。\n"
            "判断は 'MERGE_OK' / 'NEED_MORE_REVIEW' / 'ESCALATE_TO_BOSS' "
            "のいずれかを必ず含めてください。\n"
            "また、判断内容は必ず社長へ報告する前提で、報告用に要点も簡潔に書いてください。"
        ),
    )
    plan_compact = compact_for_prompt(
        plan.content,
        stage="manager_plan",
        max_chars=runtime.compress.max_chars_default,
        enabled=runtime.compress.enabled,
    )
    lead_review_compact = compact_for_prompt(
        lead_review.content,
        stage="manager_lead_review",
        max_chars=runtime.compress.max_chars_default,
        enabled=runtime.compress.enabled,
    )
    manager_prompt = (
        f"社長計画(圧縮):\n\n{plan_compact}\n\n"
        f"課長レビュー(圧縮):\n\n{lead_review_compact}\n\n"
        f"課ブランチ: {team_branch(lead.id)}\n"
        "判断: MERGE_OK / NEED_MORE_REVIEW / ESCALATE_TO_BOSS\n"
    )
    manager_decision = manager_agent.run(user_prompt=manager_prompt, model=model, backend=backend)
    msgs.append(manager_decision)
    write_artifact(workdir, "40-manager-decision.md", manager_decision.content)

    # Manager must report upward to boss (md handoff).
    report_body = compact_for_prompt(
        (
            f"project: {spec.project}\n\n"
            "## 社長計画(要約)\n" + plan.content + "\n\n"
            "## 課長レビュー(要約)\n" + lead_review.content + "\n\n"
            "## 部長判断\n" + manager_decision.content + "\n"
        ),
        stage="manager_report_to_boss",
        max_chars=runtime.compress.max_chars_vote,
        enabled=runtime.compress.enabled,
    )
    deliver_markdown(
        root=root,
        from_agent=manager.id,
        to_agent=boss.id,
        title=f"部長報告: {spec.project or 'default'}",
        body=report_body,
    )
    actions.append("mailbox: manager -> boss report")

    # Dev manager should also notify QA/Ops managers (cross-department awareness).
    if manager.id == "dev_mgr":
        for peer in ["qa_mgr", "ops_mgr"]:
            if org.find(peer) is not None:
                deliver_markdown(
                    root=root,
                    from_agent=manager.id,
                    to_agent=peer,
                    title=f"共有: 開発判断 {spec.project or 'default'}",
                    body=report_body,
                )
        actions.append("mailbox: dev_mgr -> qa_mgr/ops_mgr share")

    _set(manager.id, manager.name or manager.id, "idle", "")

    decision_text = manager_decision.content.upper()

    # MERGE_OK の場合は main に反映し、teamブランチを削除（部長判断がトリガ）
    if approved_by_lead and ("MERGE_OK" in decision_text):
        try:
            from usagi.git_ops import GitRepo

            base_repo = (repo_root or workdir) / ".usagi" / "repo"
            wt_dir = (repo_root or workdir) / ".usagi" / "worktrees" / team_branch(lead.id)
            repo = GitRepo(base_repo)
            repo.merge_to_main_and_delete_branch(team_branch(lead.id))
            repo.worktree_remove(wt_dir)
            actions.append(f"git merge main <= {team_branch(lead.id)}")
            actions.append(f"git branch delete {team_branch(lead.id)}")
        except Exception as e:  # noqa: BLE001
            actions.append(f"merge/delete failed: {type(e).__name__}: {e}")

    # critical path: escalation or lead did not approve
    need_vote = (not approved_by_lead) or ("ESCALATE_TO_BOSS" in decision_text)

    if need_vote and runtime.vote.enabled:
        votes = _run_3persona_vote(
            backend=backend,
            model=model,
            org=org,
            runtime=runtime,
            context=(
                compact_for_prompt(
                    (
                        f"依頼: {spec.project}\n\n"
                        f"社長計画:\n{plan.content}\n\n"
                        f"課長レビュー:\n{lead_review.content}\n\n"
                        f"部長判断:\n{manager_decision.content}\n"
                    ),
                    stage="vote_context",
                    max_chars=runtime.compress.max_chars_vote,
                    enabled=runtime.compress.enabled,
                )
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
    write_artifact(workdir, "90-report.md", report)

    return ApprovalRunResult(report=report, messages=msgs, assignment=assignment)


def _run_worker_step_worktree(
    *,
    worker: AgentDef,
    lead: AgentDef,
    plan: AgentMessage,
    spec: UsagiSpec,
    workdir: Path,
    repo_root: Path,
    model: str,
    backend: LLMBackend,
    runtime: RuntimeMode,
    offline: bool,
) -> AgentMessage:
    """ワーカーの実装ステップ（worktree方式）。

    - DoD/DooD を避け、git worktree + codex CLI で作業する
    - 成果物は unified diff として返す
    """

    import logging
    import subprocess

    from usagi.git_ops import GitRepo

    log = logging.getLogger(__name__)

    team = team_branch(lead.id)

    # base repo: repo_root 配下に repo を作り、worktree はその横に切る
    # layout:
    # - <repo_root>/.usagi/repo/  (bareではない通常repo)
    # - <repo_root>/.usagi/worktrees/<team>/ (worktree)
    base_repo = repo_root / ".usagi" / "repo"
    wt_dir = repo_root / ".usagi" / "worktrees" / team

    repo = GitRepo(base_repo)
    base_repo.mkdir(parents=True, exist_ok=True)
    repo.ensure_repo()
    repo.ensure_initial_commit()

    # worktree を作成（既にあれば使う）
    repo.worktree_add(wt_dir, team)

    # worker prompt
    plan_compact = compact_for_prompt(
        plan.content,
        stage="worker_plan",
        max_chars=runtime.compress.max_chars_default,
        enabled=runtime.compress.enabled,
    )
    prompt = (
        f"社長の方針/計画(圧縮):\n\n{plan_compact}\n\n"
        f"プロジェクト名: {spec.project}\n"
        f"課ブランチ: {team}\n\n"
        "作業はこの作業ディレクトリ上で行ってください。\n"
        "最終的に `git diff` 相当の Unified diff 形式で出力してください。\n"
    )

    if offline:
        # backend は offline のダミーだが、作業場だけは用意
        content = backend.generate(prompt, model=model)
        return AgentMessage(agent_name=worker.name or worker.id, role="coder", content=content)

    # codex exec はカレントディレクトリのファイルに対して編集する想定
    cmd = ["codex", "exec", prompt]
    log.info("worker(worktree) cmd: %s", " ".join(cmd))
    r = subprocess.run(cmd, cwd=wt_dir, text=True, capture_output=True, check=False)
    if r.returncode != 0:
        log.error("worker(worktree) failed: code=%d", r.returncode)
        stderr_tail = "\n".join((r.stderr or "").splitlines()[-50:])
        if stderr_tail:
            log.error("worker(worktree) stderr tail:\n%s", stderr_tail)
        return AgentMessage(
            agent_name=worker.name or worker.id,
            role="coder",
            content=(
                f"(worker worktree failed with code {r.returncode})\n"
                "See `.usagi/logs/usagi.log` for stderr tail.\n"
            ),
        )

    content = (r.stdout or "").strip()
    if not content:
        # safety: if codex didn't output diff, fall back to actual git diff
        try:
            diff = subprocess.run(
                ["git", "diff"],
                cwd=wt_dir,
                text=True,
                capture_output=True,
                check=False,
            ).stdout
            content = diff.strip()
        except Exception:
            content = ""

    return AgentMessage(agent_name=worker.name or worker.id, role="coder", content=content)


def _run_worker_in_container(
    *,
    worker: AgentDef,
    lead: AgentDef,
    plan: AgentMessage,
    spec: UsagiSpec,
    workdir: Path,
    model: str,
    runtime: RuntimeMode,
) -> AgentMessage:
    """ワーカーの実装をDockerコンテナ内で実行する。"""
    import logging
    import subprocess
    import tempfile

    log = logging.getLogger(__name__)

    # plan + spec をプロンプトとしてファイルに書き出し
    prompt = (
        f"社長の方針/計画:\n\n{plan.content}\n\n"
        f"プロジェクト名: {spec.project}\n"
        f"課ブランチ: {team_branch(lead.id)}\n\n"
        "変更は Unified diff 形式で出力してください。"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8",
    ) as f:
        f.write(prompt)
        prompt_path = Path(f.name)

    try:
        from usagi.worker_container import _ensure_worker_image

        image = "usagi-worker:latest"
        _ensure_worker_image(
            repo_root=Path(".").resolve(),
            image=image,
            image_build=runtime.worker_image_build,
        )

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{prompt_path.resolve()}:/prompt.md:ro",
            "-v", f"{workdir.resolve()}:/work",
            "-w", "/work",
            "--entrypoint", "codex",
            image,
            "exec",
            "--file", "/prompt.md",
        ]

        # NOTE: docker CLI is required in the parent(usagi) image, and host docker.sock must be mounted.

        log.info("worker container cmd: %s", " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        log.info(
            "worker container done: code=%d stdout=%d stderr=%d",
            r.returncode, len(r.stdout or ""), len(r.stderr or ""),
        )

        # Failure diagnostics:
        # - Do NOT include full stderr/stdout in the user-facing report by default (may contain secrets).
        # - Instead, write a small tail to logs so operators can debug.
        if r.returncode != 0:
            stderr = r.stderr or ""
            tail_lines = 50
            tail = "\n".join(stderr.splitlines()[-tail_lines:]) if stderr else ""
            if tail:
                log.error("worker container stderr tail (last %d lines):\n%s", tail_lines, tail)
            else:
                log.error("worker container stderr: (empty)")

        content = r.stdout or ""
        if r.returncode != 0:
            content = (
                f"(worker container failed with code {r.returncode})\n"
                "See `.usagi/logs/usagi.log` for docker stderr tail.\n\n"
                + content
            )

        return AgentMessage(
            agent_name=worker.name or worker.id,
            role="coder",
            content=content,
        )
    finally:
        prompt_path.unlink(missing_ok=True)


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
