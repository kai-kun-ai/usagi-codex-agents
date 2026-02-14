import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import ora from 'ora';
import chalk from 'chalk';
import { z } from 'zod';
import { parseSpecMarkdown } from './spec.js';
import { runPipeline } from './usagiPipeline.js';

const Args = z.object({
  specPath: z.string(),
  outPath: z.string().optional(),
  workdir: z.string().optional(),
  model: z.string().default('codex'),
  dryRun: z.boolean().default(false),
  offline: z.boolean().default(false),
});

export async function runUsagi(argsInput: z.input<typeof Args>) {
  const args = Args.parse(argsInput);

  const spinner = ora({ text: '指示書を読み込み中...', spinner: 'dots' }).start();
  const absSpec = path.resolve(process.cwd(), args.specPath);
  const specMd = await fs.readFile(absSpec, 'utf8');
  const spec = parseSpecMarkdown(specMd);
  spinner.succeed('指示書を読み込みました');

  const workdir = path.resolve(process.cwd(), args.workdir ?? '.');

  const result = await runPipeline({
    spec,
    workdir,
    model: args.model,
    dryRun: args.dryRun,
    offline: args.offline,
    ui: {
      log: (line) => console.log(line),
      section: (title) => console.log(`\n${chalk.bold.cyan('==')} ${chalk.bold(title)}\n`),
      step: (title) => ora({ text: title, spinner: 'dots' }).start(),
    },
  });

  const report = result.report;
  if (args.outPath) {
    const outAbs = path.resolve(process.cwd(), args.outPath);
    await fs.mkdir(path.dirname(outAbs), { recursive: true });
    await fs.writeFile(outAbs, report, 'utf8');
    console.log(chalk.green(`\nレポートを書き出しました: ${outAbs}`));
  } else {
    console.log('\n' + report);
  }
}
