import path from 'node:path';
import fs from 'node:fs/promises';
import { execa } from 'execa';
import type { UsagiSpec } from './spec.js';
import { getOpenAIClient } from './openaiClient.js';

export type Ui = {
  log: (line: string) => void;
  section: (title: string) => void;
  step: (title: string) => { succeed: (t?: string) => void; fail: (t?: string) => void; text: string };
};

export async function runPipeline(opts: {
  spec: UsagiSpec;
  workdir: string;
  model: string;
  dryRun: boolean;
  ui: Ui;
}): Promise<{ report: string }> {
  const { spec, workdir, model, dryRun, ui } = opts;

  ui.section(`うさぎさん株式会社: 実行開始 / project=${spec.project}`);
  ui.log(`workdir: ${workdir}`);
  ui.log(`model: ${model}`);
  ui.log(`dry-run: ${dryRun}`);

  const planSpin = ui.step('社長うさぎが計画を作成中...');
  const plan = await makePlan({ spec, model });
  planSpin.succeed('計画ができました');

  if (dryRun) {
    return { report: renderReport({ spec, workdir, plan, actions: [], notes: ['dry-runのため実行はしていません'] }) };
  }

  const actions: string[] = [];

  // If tasks include "init" patterns, create a folder.
  const initSpin = ui.step('作業ディレクトリを準備中...');
  await fs.mkdir(workdir, { recursive: true });
  initSpin.succeed('準備OK');

  // Implementation: generate files from plan (very small MVP)
  const implSpin = ui.step('実装うさぎが生成/編集案を作成中...');
  const patch = await makePatch({ spec, plan, model });
  implSpin.succeed('変更案ができました');

  const applySpin = ui.step('変更を適用中...');
  const applied = await applyPatch({ workdir, patch });
  actions.push(...applied.actions);
  applySpin.succeed('適用しました');

  const testSpin = ui.step('監査うさぎが簡易チェック中...');
  const checks = await runChecks({ workdir });
  actions.push(...checks.actions);
  testSpin.succeed('チェック完了');

  return { report: renderReport({ spec, workdir, plan, actions, notes: [checks.summary] }) };
}

async function makePlan(opts: { spec: UsagiSpec; model: string }): Promise<string> {
  const client = getOpenAIClient();
  const prompt = `あなたは「うさぎさん株式会社」の社長うさぎです。\n\n目的:\n${opts.spec.objective}\n\n背景:\n${opts.spec.context}\n\nやること(箇条書き):\n${opts.spec.tasks.map((t) => `- ${t}`).join('\n')}\n\n制約:\n${opts.spec.constraints.map((c) => `- ${c}`).join('\n')}\n\n出力: 実行計画をMarkdownで。セクション: 方針 / 作業ステップ / リスク / 完了条件。`;

  const resp = await client.responses.create({
    model: opts.model,
    input: prompt,
  });
  return resp.output_text ?? '';
}

async function makePatch(opts: { spec: UsagiSpec; plan: string; model: string }): Promise<string> {
  const client = getOpenAIClient();
  const prompt = `あなたは「うさぎさん株式会社」の実装うさぎです。\n\n次の計画に沿って、最小構成の成果物を作ってください。\n\n計画:\n${opts.plan}\n\n要件:\n- 変更は "Unified diff" 形式で出力してください（git diffと同様）。\n- ルートに README.md を必ず作る。\n- 可能なら動くサンプル(簡単なCLIやスクリプト)も含める。\n- 文章は日本語。\n\nプロジェクト名: ${opts.spec.project}\n`;

  const resp = await client.responses.create({
    model: opts.model,
    input: prompt,
  });
  return resp.output_text ?? '';
}

async function applyPatch(opts: { workdir: string; patch: string }): Promise<{ actions: string[] }> {
  const actions: string[] = [];
  const patchPath = path.join(opts.workdir, '.usagi.patch');
  await fs.writeFile(patchPath, opts.patch, 'utf8');
  actions.push(`write ${patchPath}`);

  // apply with `git apply` if possible; otherwise fallback to no-op.
  try {
    await execa('git', ['init'], { cwd: opts.workdir });
    await execa('git', ['apply', '--whitespace=nowarn', patchPath], { cwd: opts.workdir });
    actions.push('git apply .usagi.patch');
  } catch (e: any) {
    actions.push(`patch apply failed: ${String(e?.message ?? e)}`);
  }
  return { actions };
}

async function runChecks(opts: { workdir: string }): Promise<{ actions: string[]; summary: string }> {
  const actions: string[] = [];
  // basic: list files
  const { stdout } = await execa('bash', ['-lc', 'ls -la'], { cwd: opts.workdir });
  actions.push('ls -la');
  return { actions, summary: `作業ディレクトリの一覧:\n\n\n\`\`\`\n${stdout}\n\`\`\`\n` };
}

function renderReport(opts: {
  spec: UsagiSpec;
  workdir: string;
  plan: string;
  actions: string[];
  notes: string[];
}): string {
  const startedAt = new Date().toISOString();
  return `# うさぎさん株式会社レポート\n\n- 開始: ${startedAt}\n- project: ${opts.spec.project}\n- workdir: ${opts.workdir}\n\n## 目的\n\n${opts.spec.objective || '(未記載)'}\n\n## 依頼内容(抽出)\n\n${opts.spec.tasks.map((t) => `- ${t}`).join('\n') || '(なし)'}\n\n## 社長うさぎの計画\n\n${opts.plan || '(空)'}\n\n## 実行ログ\n\n${opts.actions.map((a) => `- ${a}`).join('\n') || '(なし)'}\n\n## メモ\n\n${opts.notes.join('\n\n')}\n`;
}
