import type { Config } from '@backstage/config';
import { createTemplateAction } from '@backstage/plugin-scaffolder-node';
import type { InfrastructureSelection, RequestView } from '@internal/plugin-idp-platform-common';
import { randomUUID } from 'node:crypto';
import type { PlatformClient, UserContext } from '../client';

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

/** Map the camelCase form value to the orchestrator's snake_case contract (pure plumbing). */
export function toOrchestratorRequest(input: {
  idempotencyKey: string;
  name: string;
  description?: string;
  owner: string;
  environment: string;
  stack: string;
  infrastructure: InfrastructureSelection;
  availability: { tier: string; reason?: string; justification?: string; sloTarget?: string };
  endpointHost?: string;
  repoVisibility: string;
}) {
  const i = input.infrastructure;
  const sel = (s: { mode: string; id?: string; name?: string }) => ({ mode: s.mode, id: s.id, name: s.name });
  return {
    idempotency_key: input.idempotencyKey,
    application_name: input.name,
    description: input.description ?? '',
    owner: input.owner,
    environment: input.environment,
    region: i.region,
    tenant_id: i.tenantId,
    management_group: i.managementGroup,
    stack: input.stack,
    subscription: sel(i.subscription),
    resource_group: sel(i.resourceGroup),
    aks_cluster: sel(i.aksCluster),
    container_registry: sel(i.containerRegistry),
    namespace: sel(i.namespace),
    runtime_capability: { type: i.runtimeCapability.type, ...sel(i.runtimeCapability) },
    availability: {
      tier: input.availability.tier,
      reason: input.availability.reason,
      justification: input.availability.justification,
      slo_target: input.availability.sloTarget,
    },
    // Empty: the server uses <name>.<gateway domain> of the selected cluster.
    endpoint_host: input.endpointHost ?? '',
    repository_visibility: input.repoVisibility,
  };
}

export function createSubmitAction(opts: { client: PlatformClient; config: Config }) {
  const { client, config } = opts;
  const timeoutMs = (config.getOptionalNumber('idp.submitTimeoutMinutes') ?? 360) * 60_000;

  return createTemplateAction({
    id: 'idp:request:submit',
    description:
      'Submit a golden-path request to the orchestrator and wait until it is validated (and any platform ' +
      'resources exist). Fails - before anything is created - if validation rejects the request.',
    schema: {
      input: {
        name: z => z.string(),
        description: z => z.string().optional(),
        owner: z => z.string(),
        environment: z => z.string(),
        stack: z => z.string(),
        infrastructure: z => z.any(),
        availability: z => z.any(),
        endpointHost: z => z.string().optional(),
        repoVisibility: z => z.string(),
      },
      output: {
        requestId: z => z.string(),
        githubOrg: z => z.string(),
        githubOwnerType: z => z.enum(['user', 'organization']),
        subscriptionId: z => z.string(),
        acrName: z => z.string(),
        aksName: z => z.string(),
        aksResourceGroup: z => z.string(),
        endpointHost: z => z.string(),
      },
    },
    async handler(ctx) {
      const userRef = ctx.user?.ref;
      if (!userRef) throw new Error('A signed-in user is required');
      const groupRefs = (ctx.user?.entity?.relations ?? [])
        .filter(r => r.type === 'memberOf')
        .map(r => r.targetRef);
      const user: UserContext = { userRef, groupRefs };
      const infra = ctx.input.infrastructure as InfrastructureSelection;

      // Checkpointed: a retried or resumed task reuses the same request (idempotency key).
      const requestId = await ctx.checkpoint({
        key: 'idp-submit',
        fn: async () => {
          const body = toOrchestratorRequest({ ...ctx.input, idempotencyKey: `scaffolder-${randomUUID()}`,
            infrastructure: infra, availability: ctx.input.availability as any });
          const created = await client.orchestrator<RequestView>('POST', '/v1/requests', { user, body });
          return created.id;
        },
      });
      ctx.logger.info(`Request ${requestId} submitted; waiting for server-side validation`);

      const deadline = Date.now() + timeoutMs;
      let last = '';
      let endpointHost = ctx.input.endpointHost ?? '';
      for (;;) {
        const r = await client.orchestrator<RequestView>('GET', `/v1/requests/${requestId}`);
        endpointHost = r.endpoint_host || endpointHost;
        if (r.state !== last) {
          ctx.logger.info(`Request ${requestId}: ${r.state}`);
          last = r.state;
        }
        if (r.state === 'FAILED' || r.state === 'CANCELLED') {
          const errs = (r.validation.errors ?? []).map(e => `- ${e.field}: ${e.message}`).join('\n');
          throw new Error(`Request ${r.state.toLowerCase()}: ${r.error.message ?? ''}\n${errs}`);
        }
        for (const w of r.validation.warnings ?? []) ctx.logger.warn(`${w.field}: ${w.message}`);
        if (r.ready_for_repository) break;
        if (r.state === 'PLATFORM_PROVISIONING' && r.platform.pr_url) {
          ctx.logger.info(`Waiting for platform resources: ${r.platform.pr_url}`);
        }
        if (Date.now() > deadline) throw new Error(`Timed out waiting for request ${requestId}`);
        await sleep(r.state === 'PLATFORM_PROVISIONING' ? 30_000 : 3_000);
      }

      ctx.output('requestId', requestId);
      ctx.output('githubOrg', config.getString('idp.githubOrg'));
      ctx.output('githubOwnerType', config.getOptionalString('idp.githubOwnerType') === 'user' ? 'user' : 'organization');
      ctx.output('subscriptionId', infra.subscription.id ?? '');
      ctx.output('acrName', infra.containerRegistry.name ?? '');
      ctx.output('aksName', infra.aksCluster.name ?? '');
      ctx.output('aksResourceGroup', infra.aksCluster.resourceGroup ?? '');
      ctx.output('endpointHost', endpointHost);
    },
  });
}
