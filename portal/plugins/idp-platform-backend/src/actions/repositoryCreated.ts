import type { Config } from '@backstage/config';
import { DefaultGithubCredentialsProvider, type ScmIntegrations } from '@backstage/integration';
import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import { Octokit } from '@octokit/rest';
import type { PlatformClient } from '../client';

/** Workflow files GitHub hasn't registered (it can skip them on a new repository's first push). */
export function unregisteredWorkflows(files: string[], registered: string[]): string[] {
  const known = new Set(registered);
  return files.filter(f => /\.ya?ml$/.test(f) && !known.has(f));
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Attach the orchestrator's custom deployment protection rule to the approval environment (so GitHub
 * holds terraform-apply until approval in Backstage), then report the repository to the orchestrator,
 * which starts validate -> plan asynchronously.
 */
export function createRepositoryCreatedAction(opts: {
  client: PlatformClient;
  config: Config;
  integrations: ScmIntegrations;
}) {
  const { client, config, integrations } = opts;
  const credentials = DefaultGithubCredentialsProvider.fromIntegrations(integrations);

  return createTemplateAction({
    id: 'idp:request:repository-created',
    description: 'Protect the approval environment and hand the repository over to the orchestrator.',
    schema: {
      input: {
        requestId: z => z.string(),
        repoUrl: z => z.string(),
        owner: z => z.string(),
        name: z => z.string(),
        approvalEnvironment: z => z.string(),
        // The requester's GitHub token (personal accounts): may commit to the protected main as its admin.
        token: z => z.string().optional(),
      },
    },
    async handler(ctx) {
      const { requestId, repoUrl, owner, name, approvalEnvironment } = ctx.input;

      await ctx.checkpoint({
        key: `protection-rule-${approvalEnvironment}`,
        fn: async () => {
          const { token } = await credentials.getCredentials({ url: `https://github.com/${owner}/${name}` });
          const octokit = new Octokit({ auth: token });
          const integrationId = config.getNumber('idp.orchestratorGithubAppId');
          const existing = await octokit.request(
            'GET /repos/{owner}/{repo}/environments/{environment_name}/deployment_protection_rules',
            { owner, repo: name, environment_name: approvalEnvironment },
          );
          const rules = (existing.data as { custom_deployment_protection_rules?: { app: { integration_url?: string; id: number } }[] })
            .custom_deployment_protection_rules ?? [];
          if (!rules.some(r => r.app.id === integrationId)) {
            await octokit.request(
              'POST /repos/{owner}/{repo}/environments/{environment_name}/deployment_protection_rules',
              { owner, repo: name, environment_name: approvalEnvironment, integration_id: integrationId },
            );
          }
          return true;
        },
      });
      ctx.logger.info(`Approval rule attached to environment ${approvalEnvironment}`);

      // GitHub sometimes doesn't register the workflows of a new repository's first push (the dispatch
      // then fails with 404). A commit that touches the missing workflow files registers them.
      await ctx.checkpoint({
        key: 'register-workflows',
        fn: async () => {
          const auth = ctx.input.token
            || (await credentials.getCredentials({ url: `https://github.com/${owner}/${name}` })).token;
          const octokit = new Octokit({ auth });
          const listing = await octokit.request('GET /repos/{owner}/{repo}/contents/{path}',
            { owner, repo: name, path: '.github/workflows' });
          const files = (listing.data as { path: string }[]).map(f => f.path);
          let missing = files;
          for (let attempt = 0; attempt < 6 && missing.length; attempt++) {
            if (attempt) await sleep(5_000);
            const reg = await octokit.request('GET /repos/{owner}/{repo}/actions/workflows', { owner, repo: name });
            missing = unregisteredWorkflows(files, reg.data.workflows.map(w => w.path));
          }
          for (const path of missing) {
            const file = await octokit.request('GET /repos/{owner}/{repo}/contents/{path}', { owner, repo: name, path });
            const { sha, content } = file.data as { sha: string; content: string };
            // A trailing blank line: a real change, so the push registers the file; YAML is unaffected.
            const text = `${Buffer.from(content, 'base64').toString('utf8').trimEnd()}\n\n`;
            await octokit.request('PUT /repos/{owner}/{repo}/contents/{path}', {
              owner, repo: name, path, sha,
              message: 'ci: register workflows (GitHub skipped them on the first push)',
              content: Buffer.from(text).toString('base64'),
            });
            ctx.logger.info(`${path}: re-committed so GitHub registers it`);
          }
          return missing;
        },
      });

      await client.orchestrator('POST', `/v1/requests/${requestId}/repository`, {
        body: { owner, name, url: repoUrl },
      });
      ctx.logger.info(`Request ${requestId} handed to the orchestrator; follow it on the Provisioning tab`);
    },
  });
}
