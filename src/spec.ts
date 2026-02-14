import yaml from 'js-yaml';
import { z } from 'zod';

// Spec format: Markdown with optional YAML frontmatter.
// Frontmatter example:
// ---
// project: my-app
// agents:
//   - name: 社長うさぎ
//     role: planner
//   - name: 実装うさぎ
//     role: coder
// ---

const Agent = z.object({
  name: z.string(),
  role: z.enum(['planner', 'coder', 'reviewer']).default('coder'),
});

export const Spec = z.object({
  project: z.string().default('usagi-project'),
  objective: z.string().default(''),
  context: z.string().default(''),
  tasks: z.array(z.string()).default([]),
  constraints: z.array(z.string()).default([]),
  agents: z.array(Agent).default([
    { name: '社長うさぎ', role: 'planner' },
    { name: '実装うさぎ', role: 'coder' },
    { name: '監査うさぎ', role: 'reviewer' },
  ]),
});

export type UsagiSpec = z.infer<typeof Spec>;

export function parseSpecMarkdown(md: string): UsagiSpec {
  const fm = extractFrontmatter(md);
  const body = fm.body;
  const front = fm.frontmatter ? (yaml.load(fm.frontmatter) as any) : {};

  const objective = pickSection(body, ['目的', 'Objective']);
  const context = pickSection(body, ['背景', 'Context']);
  const tasks = pickBullets(body, ['やること', 'Tasks']);
  const constraints = pickBullets(body, ['制約', 'Constraints']);

  return Spec.parse({
    ...front,
    objective,
    context,
    tasks,
    constraints,
  });
}

function extractFrontmatter(md: string): { frontmatter?: string; body: string } {
  const m = md.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return { body: md };
  return { frontmatter: m[1]!, body: m[2]! };
}

function pickSection(body: string, names: string[]): string {
  const lines = body.split(/\r?\n/);
  const hRe = new RegExp(`^#{1,6}\\s*(${names.map(escapeRe).join('|')})\\s*$`, 'i');
  let start = -1;
  let level = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    const m = line.match(/^(#{1,6})\s*(.+)$/);
    if (!m) continue;
    const lvl = m[1]!.length;
    const title = m[2]!.trim();
    if (hRe.test(line)) {
      start = i + 1;
      level = lvl;
      break;
    }
    // allow '## 目的' with extra spaces handled by regex above
    if (names.some((n) => title.toLowerCase() === n.toLowerCase())) {
      start = i + 1;
      level = lvl;
      break;
    }
  }
  if (start === -1) return '';
  const out: string[] = [];
  for (let i = start; i < lines.length; i++) {
    const line = lines[i]!;
    const m = line.match(/^(#{1,6})\s*(.+)$/);
    if (m && m[1]!.length <= level) break;
    out.push(line);
  }
  return out.join('\n').trim();
}

function pickBullets(body: string, sectionNames: string[]): string[] {
  const section = pickSection(body, sectionNames);
  if (!section) return [];
  return section
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => /^[-*]\s+/.test(l))
    .map((l) => l.replace(/^[-*]\s+/, '').trim());
}

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
