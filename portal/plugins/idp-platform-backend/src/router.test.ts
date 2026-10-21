import { mockCredentials, mockServices } from '@backstage/backend-test-utils';
import { ConfigReader } from '@backstage/config';
import { AuthorizeResult } from '@backstage/plugin-permission-common';
import express from 'express';
import request from 'supertest';
import type { PlatformClient } from './client';
import { createRouter } from './router';

const USER = 'user:default/nixon';

function setup(opts: { allowApproval?: boolean } = {}) {
  const client = {
    discovery: jest.fn().mockResolvedValue([]),
    orchestrator: jest.fn().mockResolvedValue({ ok: true }),
  };
  const permissions = mockServices.permissions.mock({
    authorize: async () => [{ result: opts.allowApproval ? AuthorizeResult.ALLOW : AuthorizeResult.DENY }],
  });
  const userInfo = mockServices.userInfo.mock({
    getUserInfo: async () => ({
      userEntityRef: USER,
      ownershipEntityRefs: [USER, 'group:default/platform-approvers', 'component:default/x'],
    }),
  });
  return { client, permissions, userInfo };
}

async function app(opts: { allowApproval?: boolean } = {}) {
  const deps = setup(opts);
  const router = await createRouter({
    config: new ConfigReader({ idp: { stacks: [{ id: 'nestjs', name: 'NestJS', enabled: true }] } }),
    logger: mockServices.logger.mock(),
    httpAuth: mockServices.httpAuth({ defaultCredentials: mockCredentials.user(USER) }),
    userInfo: deps.userInfo,
    permissions: deps.permissions,
    client: deps.client as unknown as PlatformClient,
  });
  const server = express().use(router);
  // The Backstage error middleware maps these errors in the real backend.
  server.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    const status = { InputError: 400, NotAllowedError: 403 }[err.name] ?? 500;
    res.status(status).json({ error: err.name });
  });
  return { server, ...deps };
}

describe('discovery routes', () => {
  it('forwards the CAF hierarchy filters to discovery', async () => {
    const { server, client } = await app();
    await request(server)
      .get('/discovery/subscriptions')
      .query({ environment: 'dev', tenant_id: 'tenant-1', management_group: 'xycorp-landingzones' })
      .expect(200);
    expect(client.discovery).toHaveBeenCalledWith('/v1/subscriptions', {
      environment: 'dev',
      tenant_id: 'tenant-1',
      management_group: 'xycorp-landingzones',
    });
  });

  it('rejects a subscription id that could change the upstream path', async () => {
    const { server, client } = await app();
    await request(server).get('/discovery/subscriptions/..%2Fadmin/resource-groups').expect(400);
    expect(client.discovery).not.toHaveBeenCalled();
  });

  it('rejects unsafe resource group names in the query', async () => {
    const { server, client } = await app();
    await request(server)
      .get('/discovery/subscriptions/sub-1/resources')
      .query({ resource_group: 'rg/../../other' })
      .expect(400);
    expect(client.discovery).not.toHaveBeenCalled();
  });

  it('accepts Azure resource group names with dots, underscores and parentheses', async () => {
    const { server, client } = await app();
    await request(server)
      .get('/discovery/subscriptions/sub-1/resources')
      .query({ resource_group: 'rg_idp.apps(dev)' })
      .expect(200);
    expect(client.discovery).toHaveBeenCalledWith('/v1/subscriptions/sub-1/resources', {
      environment: undefined,
      type: undefined,
      resource_group: 'rg_idp.apps(dev)',
    });
  });

  it('lists the configured stacks', async () => {
    const { server } = await app();
    const res = await request(server).get('/stacks').expect(200);
    expect(res.body).toEqual([{ id: 'nestjs', name: 'NestJS', enabled: true }]);
  });
});

describe('operations', () => {
  it('asks the orchestrator as the verified user, who decides what they may see', async () => {
    const { server, client } = await app();
    await request(server).get('/requests/req-1/operations').expect(200);
    expect(client.orchestrator).toHaveBeenCalledWith('GET', '/v1/requests/req-1/operations', {
      user: { userRef: USER, groupRefs: ['group:default/platform-approvers'] },
    });
  });

  it('rejects an id that could change the upstream path', async () => {
    const { server, client } = await app();
    await request(server).get('/requests/..%2Fapprovals/operations').expect(400);
    expect(client.orchestrator).not.toHaveBeenCalled();
  });
});

describe('approvals', () => {
  it('refuses an approval without the approve permission', async () => {
    const { server, client } = await app({ allowApproval: false });
    await request(server)
      .post('/requests/req-1/approval')
      .send({ decision: 'approve', plan_hash: 'abc' })
      .expect(403);
    expect(client.orchestrator).not.toHaveBeenCalled();
  });

  it('requires a decision and the plan hash', async () => {
    const { server, client } = await app({ allowApproval: true });
    await request(server).post('/requests/req-1/approval').send({ decision: 'maybe', plan_hash: 'abc' }).expect(400);
    await request(server).post('/requests/req-1/approval').send({ decision: 'approve' }).expect(400);
    expect(client.orchestrator).not.toHaveBeenCalled();
  });

  it('sends the verified user, never one from the request body', async () => {
    const { server, client } = await app({ allowApproval: true });
    await request(server)
      .post('/requests/req-1/approval')
      .send({ decision: 'approve', plan_hash: 'abc', comment: 'x'.repeat(2000), user: 'user:default/someone-else' })
      .expect(200);
    expect(client.orchestrator).toHaveBeenCalledWith('POST', '/v1/requests/req-1/approval', {
      user: { userRef: USER, groupRefs: ['group:default/platform-approvers'] },
      body: { decision: 'approve', plan_hash: 'abc', comment: 'x'.repeat(1000) },
    });
  });
});
