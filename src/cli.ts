#!/usr/bin/env node
import yargs, { type Argv } from 'yargs';
import { hideBin } from 'yargs/helpers';
import { runUsagi } from './run.js';

await yargs(hideBin(process.argv))
  .scriptName('usagi')
  .command(
    'run <spec>',
    'Markdownの指示書(spec)を読んで、うさぎさん会社のマルチエージェントで実行してレポートを出します',
    (y: Argv) =>
      y
        .positional('spec', {
          type: 'string',
          describe: '指示書Markdownへのパス (例: specs/todo.md)',
          demandOption: true,
        })
        .option('out', {
          type: 'string',
          describe: '出力レポートMarkdownのパス (省略時は標準出力)',
        })
        .option('workdir', {
          type: 'string',
          describe: '作業ディレクトリ (省略時はカレント)',
        })
        .option('model', {
          type: 'string',
          describe: '利用モデル (例: codex / gpt-4.1 / gpt-5.2 など)',
          default: 'codex',
        })
        .option('dry-run', {
          type: 'boolean',
          describe: '実行せずに計画だけ出す',
          default: false,
        })
        .option('offline', {
          type: 'boolean',
          describe: 'OpenAI APIを呼ばずにオフラインのダミー出力で動作確認する',
          default: false,
        }),
    async (argv: any) => {
      await runUsagi({
        specPath: argv.spec,
        outPath: argv.out,
        workdir: argv.workdir,
        model: argv.model,
        dryRun: argv['dry-run'],
        offline: argv.offline,
      });
    }
  )
  .demandCommand(1)
  .help()
  .strict()
  .parse();
