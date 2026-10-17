import type {
  HttpAuthService,
  LoggerService,
  PermissionsService,
  UserInfoService,
} from '@backstage/backend-plugin-api';
import type { Config } from '@backstage/config';
import { InputError, NotAllowedError } from '@backstage/errors';
import { AuthorizeResult } from '@backstage/plugin-permission-common';
import { idpRequestApprovePermission } from '@internal/plugin-idp-platform-common';
import express, { type Request } from 'express';
import Router from 'express-promise-router';
import { PlatformClient, type UserContext } from './client';

const SAFE_ID = /^[A-Za-z0-9-]{1,64}$/;
// Management group and resource group names also allow '.', '_' and parentheses (Azure naming rules).
const SAFE_NAME = /^[A-Za-z0-9._()-]{1,90}$/;

export async function createRouter(deps: {
  config: Config;
  logger: LoggerService;
  httpAuth: HttpAuthService;
  userInfo: UserInfoService;
  permissions: PermissionsService;
  client?: PlatformClient;
}): Promise<express.Router> {
  const { config, httpAuth, userInfo, permissions } = deps;
  const client = deps.client ?? PlatformClient.fromConfig(config);
  const router = Router();
  router.use(express.json({ limit: '100kb' }));

  /** User context comes ONLY from the verified Backstage token, never from the browser's payload. */
  async function user(req: Request): Promise<UserContext> {
    const credentials = await httpAuth.credentials(req, { allow: ['user'] });
    const info = await userInfo.getUserInfo(credentials);
    return {
      userRef: info.userEntityRef,
      groupRefs: info.ownershipEntityRefs.filter(r => r.startsWith('group:')),
    };
  }

  function id(value: string): string {
    if (!SAFE_ID.test(value)) throw new InputError('invalid id');
    return value;
  }

  const q = (req: Request, key: string) => (typeof req.query[key] === 'string' ? (req.query[key] as string) : undefined);
  const qName = (req: Request, key: string) => {
    const value = q(req, key);
    if (value !== undefined && !SAFE_NAME.test(value)) throw new InputError(`invalid ${key}`);
    return value;
  };

  // ---------------- discovery (read-only), for the scaffolder pickers ----------------
  // Cloud Adoption Framework order: tenant -> management group -> subscription -> resource group.
  router.get('/discovery/tenants', async (req, res) => {
    await user(req);
    res.json(await client.discovery('/v1/tenants', { environment: q(req, 'environment') }));
  });

  router.get('/discovery/management-groups', async (req, res) => {
    await user(req);
    res.json(await client.discovery('/v1/management-groups', {
      tenant_id: qName(req, 'tenant_id'),
      environment: q(req, 'environment'),
    }));
  });

  router.get('/discovery/subscriptions', async (req, res) => {
    await user(req);
    res.json(await client.discovery('/v1/subscriptions', {
      environment: q(req, 'environment'),
      tenant_id: qName(req, 'tenant_id'),
      management_group: qName(req, 'management_group'),
    }));
  });

  router.get('/discovery/subscriptions/:sub/capabilities', async (req, res) => {
    await user(req);
    res.json(await client.discovery(`/v1/subscriptions/${id(req.params.sub)}/capabilities`, { region: q(req, 'region') }));
  });

  for (const kind of ['resource-groups', 'aks-clusters', 'container-registries', 'resources']) {
    router.get(`/discovery/subscriptions/:sub/${kind}`, async (req, res) => {
      await user(req);
      res.json(await client.discovery(`/v1/subscriptions/${id(req.params.sub)}/${kind}`, {
        environment: q(req, 'environment'),
        type: q(req, 'type'),
        resource_group: qName(req, 'resource_group'),
      }));
    });
  }

  router.get('/stacks', async (_req, res) => {
    const stacks = config.getOptionalConfigArray('idp.stacks') ?? [];
    res.json(stacks.map(s => ({ id: s.getString('id'), name: s.getString('name'), enabled: s.getBoolean('enabled') })));
  });

  // ---------------- requests / status ----------------
  router.get('/requests', async (req, res) => {
    await user(req);
    res.json(await client.orchestrator('GET', '/v1/requests', { query: { application: q(req, 'application') } }));
  });

  router.get('/requests/:id', async (req, res) => {
    await user(req);
    res.json(await client.orchestrator('GET', `/v1/requests/${id(req.params.id)}`));
  });

  // ---------------- approvals (permission checked here, re-checked by the orchestrator) ----------------
  router.get('/approvals', async (req, res) => {
    res.json(await client.orchestrator('GET', '/v1/approvals', { user: await user(req) }));
  });

  router.post('/requests/:id/approval', async (req, res) => {
    const credentials = await httpAuth.credentials(req, { allow: ['user'] });
    const [decision] = await permissions.authorize([{ permission: idpRequestApprovePermission }], { credentials });
    if (decision.result !== AuthorizeResult.ALLOW) {
      throw new NotAllowedError('You are not allowed to approve infrastructure changes.');
    }
    const { decision: choice, plan_hash, comment } = req.body ?? {};
    if (!['approve', 'reject'].includes(choice) || typeof plan_hash !== 'string') {
      throw new InputError('decision and plan_hash are required');
    }
    res.json(await client.orchestrator('POST', `/v1/requests/${id(req.params.id)}/approval`, {
      user: await user(req),
      body: { decision: choice, plan_hash, comment: typeof comment === 'string' ? comment.slice(0, 1000) : '' },
    }));
  });

  router.post('/requests/:id/cancel', async (req, res) => {
    res.json(await client.orchestrator('POST', `/v1/requests/${id(req.params.id)}/cancel`, { user: await user(req) }));
  });

  router.post('/requests/:id/retry', async (req, res) => {
    res.json(await client.orchestrator('POST', `/v1/requests/${id(req.params.id)}/retry`, { user: await user(req) }));
  });

  router.post('/requests/:id/cleanup', async (req, res) => {
    res.json(await client.orchestrator('POST', `/v1/requests/${id(req.params.id)}/cleanup`, { user: await user(req) }));
  });

  return router;
}
