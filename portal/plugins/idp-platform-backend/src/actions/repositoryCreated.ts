import type { Config } from '@backstage/config';
import { DefaultGithubCredentialsProvider, type ScmIntegrations } from '@backstage/integration';
import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import { Octokit } from '@octokit/rest';
import type { PlatformClient } from '../client';

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

      await client.orchestrator('POST', `/v1/requests/${requestId}/repository`, {
        body: { owner, name, url: repoUrl },
      });
      ctx.logger.info(`Request ${requestId} handed to the orchestrator; follow it on the Provisioning tab`);
    },
  });
}
