"""Agent retraining (personality/memory md) with approval.

Goal:
- Supervisors can propose edits to subordinate personality/memory md files.
- No unilateral changes: requires approval from an upper role.
- CEO(boss) changing a manager requires board vote.
- If board vote fails, record a human-judgement request in outputs/report.md.

This is an initial scaffold: propose -> approve/apply.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from usagi.approval_pipeline import _run_3persona_vote  # reuse existing vote runner
from usagi.git_ops import GitRepo
from usagi.human_judgement import append_human_judgement
from usagi.mailbox import deliver_markdown
from usagi.org import Organization
from usagi.prompt_compact import compact_for_prompt
from usagi.runtime import RuntimeMode
from usagi.vote import decide_2of3


@dataclass(frozen=True)
class RetrainProposal:
    proposer_id: str
    target_id: str
    target_path: str
    reason: str
    patch: str


def proposal_dir(root: Path) -> Path:
    d = root / ".usagi" / "retrain"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_proposal(root: Path, p: RetrainProposal) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = proposal_dir(root) / f"{ts}-{p.proposer_id}-to-{p.target_id}.json"
    out.write_text(json.dumps(p.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_proposal(path: Path) -> RetrainProposal:
    d = json.loads(path.read_text(encoding="utf-8"))
    return RetrainProposal(**d)


def propose_retrain(
    *,
    root: Path,
    outputs_dir: Path,
    org: Organization,
    runtime: RuntimeMode,
    proposer_id: str,
    target_id: str,
    reason: str,
) -> Path:
    proposer = org.find(proposer_id)
    target = org.find(target_id)
    if not proposer or not target:
        raise RuntimeError("unknown proposer/target")

    # target file path (personality preferred; fallback memory)
    target_path = target.personality or target.memory
    if not target_path:
        raise RuntimeError("target has no personality/memory path")

    abs_path = (root / target_path).resolve()
    if not abs_path.exists():
        raise RuntimeError(f"target md not found: {target_path}")

    old = abs_path.read_text(encoding="utf-8")

    # Ask proposer LLM (codex_cli via unified backend) to output unified diff
    from usagi.llm_backend import LLM, LLMConfig

    llm = LLM(LLMConfig(backend="codex_cli", model="codex"))
    prompt = (
        "あなたは上司です。部下の性格(またはメモリ)を『再教育』するために、\n"
        "次のファイルを編集する unified diff を作ってください。\n"
        "目的: チーム運用を改善し、指示の解釈ミス/報告不足/暴走を減らす。\n\n"
        f"対象ファイル: {target_path}\n"
        f"理由: {reason}\n\n"
        "出力は unified diff のみ。\n\n"
        "--- 現在の内容 ---\n"
        f"{compact_for_prompt(old, stage='retrain_old', max_chars=2500)}\n"
    )
    patch = llm.generate(prompt).strip()

    prop = RetrainProposal(
        proposer_id=proposer_id,
        target_id=target_id,
        target_path=target_path,
        reason=reason,
        patch=patch,
    )
    prop_path = write_proposal(root, prop)

    # Determine approver route
    approver_id = target.reports_to or "boss"
    need_board = (proposer_id == runtime.boss_id) and (target.role == "manager")

    if need_board:
        deliver_markdown(
            root=root,
            from_agent=proposer_id,
            to_agent="board",
            title=f"再教育提案(要投票): {target_id}",
            body=f"proposal: {prop_path}\nreason: {reason}\nfile: {target_path}",
        )
        append_human_judgement(
            outputs_dir=outputs_dir,
            title=f"取締役会投票待ち: {target_id} の再教育",
            details=f"proposal={prop_path}",
        )
    else:
        deliver_markdown(
            root=root,
            from_agent=proposer_id,
            to_agent=approver_id,
            title=f"再教育承認依頼: {target_id}",
            body=f"proposal: {prop_path}\nreason: {reason}\nfile: {target_path}",
        )

    return prop_path


def decide_and_apply(
    *,
    root: Path,
    outputs_dir: Path,
    org: Organization,
    runtime: RuntimeMode,
    proposal_path: Path,
    decider_id: str,
    offline: bool,
) -> str:
    prop = load_proposal(proposal_path)
    target = org.find(prop.target_id)
    if not target:
        raise RuntimeError("target not found")

    need_board = (prop.proposer_id == runtime.boss_id) and (target.role == "manager")

    if need_board:
        if not runtime.vote.enabled:
            append_human_judgement(
                outputs_dir=outputs_dir,
                title=f"取締役会投票が無効: {prop.target_id} 再教育の可否",
                details=f"proposal={proposal_path}",
            )
            return "vote disabled"

        # run board vote (2of3)
        from usagi.agents import CodexCLIBackend, OfflineBackend

        backend = OfflineBackend() if offline else CodexCLIBackend()
        votes = _run_3persona_vote(
            backend=backend,
            model="codex",
            org=org,
            runtime=runtime,
            context=(
                f"再教育提案: {prop.target_id}\n"
                f"理由: {prop.reason}\n"
                f"対象: {prop.target_path}\n"
                "パッチ:\n"
                f"{compact_for_prompt(prop.patch, stage='retrain_patch', max_chars=2500, enabled=runtime.compress.enabled)}"  # noqa: E501
                "\n"
            ),
        )
        outcome = decide_2of3(votes)
        if outcome != "approve":
            append_human_judgement(
                outputs_dir=outputs_dir,
                title=f"取締役会合意が取れない: {prop.target_id} 再教育",
                details=f"proposal={proposal_path} outcome={outcome}",
            )
            return f"blocked: {outcome}"

    else:
        # require upper approval: decider must be target.reports_to
        if decider_id != (target.reports_to or runtime.boss_id):
            raise RuntimeError("decider is not upper approver")

    # apply patch
    abs_path = (root / prop.target_path).resolve()
    repo = GitRepo(root)
    repo.ensure_repo()
    repo.ensure_initial_commit()
    patch_path = proposal_path.with_suffix(".patch")
    patch_path.write_text(prop.patch, encoding="utf-8")

    import subprocess

    r = subprocess.run(["git", "apply", str(patch_path)], cwd=root, text=True, capture_output=True)
    if r.returncode != 0:
        append_human_judgement(
            outputs_dir=outputs_dir,
            title=f"再教育パッチ適用失敗: {prop.target_id}",
            details=(r.stderr or "").strip()[:500],
        )
        return "apply failed"

    return f"applied: {abs_path}"
