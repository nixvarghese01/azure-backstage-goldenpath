import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { PlatformClient } from '../client';

/** Write rendered files under `root`; refuses paths that would land outside it. Returns the paths written. */
export async function writeFiles(root: string, files: Record<string, string>): Promise<string[]> {
  const base = path.resolve(root);
  const written: string[] = [];
  for (const [rel, content] of Object.entries(files)) {
    const target = path.resolve(base, rel);
    if (path.isAbsolute(rel) || !target.startsWith(base + path.sep)) {
      throw new Error(`starter file outside the workspace: ${rel}`);
    }
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, content);
    written.push(rel);
  }
  return written.sort();
}

/**
 * Add the stack's starter application (source, tests, Dockerfile, Compose, README) to the workspace, so
 * it is in the repository's first commit. The orchestrator renders it from the same stack templates as
 * the application PR, which later adds the CI/CD workflows and the Helm values filled with the
 * infrastructure outputs.
 */
export function createStarterAction(opts: { client: PlatformClient }) {
  const { client } = opts;
  return createTemplateAction({
    id: 'idp:request:starter',
    description: "Add the stack's starter application to the new repository's first commit.",
    schema: {
      input: { requestId: z => z.string() },
      output: { files: z => z.array(z.string()) },
    },
    async handler(ctx) {
      const { files } = await client.orchestrator<{ files: Record<string, string> }>(
        'GET',
        `/v1/requests/${encodeURIComponent(ctx.input.requestId)}/starter`,
      );
      const written = await writeFiles(ctx.workspacePath, files);
      ctx.logger.info(`Starter application added: ${written.length} files`);
      ctx.output('files', written);
    },
  });
}
