import type { Config } from '@backstage/config';
import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import { promises as fs } from 'node:fs';
import path from 'node:path';

/** A git ref GitHub accepts in `uses: owner/repo/.github/workflows/x.yml@<ref>` (branch, tag or SHA). */
const REF = /^[A-Za-z0-9._/-]{1,100}$/;
/** Calls of the platform repository's reusable workflows, with their ref. */
const USES = /(azure-backstage-goldenpath\/\.github\/workflows\/[\w.-]+\.ya?ml)@[A-Za-z0-9._/-]+/g;

/** Point the platform's reusable-workflow calls in the given file texts at `ref`. */
export function pinWorkflowRefs(text: string, ref: string): string {
  if (!REF.test(ref)) throw new Error(`invalid platform ref: ${ref}`);
  return text.replace(USES, `$1@${ref}`);
}

/**
 * The skeleton's workflows are copied without templating (they are full of ${{ }} GitHub expressions),
 * so their calls of the platform's reusable workflows are pinned here, to idp.platformRef: the branch
 * that deployed this portal (develop for the dev platform, main for releases).
 */
export function createWorkflowRefsAction(opts: { config: Config }) {
  const { config } = opts;
  return createTemplateAction({
    id: 'idp:workflow-refs',
    description: "Pin the generated workflows' calls of the platform's reusable workflows to the platform ref.",
    schema: {
      output: { ref: z => z.string() },
    },
    async handler(ctx) {
      const ref = config.getOptionalString('idp.platformRef') || 'main';
      const dir = path.join(ctx.workspacePath, '.github', 'workflows');
      const files = await fs.readdir(dir).catch(() => [] as string[]);
      for (const file of files.filter(f => /\.ya?ml$/.test(f))) {
        const p = path.join(dir, file);
        const before = await fs.readFile(p, 'utf8');
        const after = pinWorkflowRefs(before, ref);
        if (after !== before) {
          await fs.writeFile(p, after);
          ctx.logger.info(`${file}: platform workflows pinned to @${ref}`);
        }
      }
      ctx.output('ref', ref);
    },
  });
}
