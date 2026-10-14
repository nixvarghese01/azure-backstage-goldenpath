import { toOrchestratorRequest } from './submit';

describe('toOrchestratorRequest', () => {
  it('maps the form value to the orchestrator contract', () => {
    const body = toOrchestratorRequest({
      idempotencyKey: 'scaffolder-1',
      name: 'orders-api',
      owner: 'group:default/team-orders',
      environment: 'dev',
      stack: 'nestjs',
      endpointHost: 'orders-api.dev.xycorp.local',
      repoVisibility: 'public',
      availability: { tier: 'standard' },
      infrastructure: {
        tenantId: 'tenant',
        managementGroup: 'xycorp-corp',
        region: 'uksouth',
        subscription: { mode: 'existing', id: 'sub' },
        resourceGroup: { mode: 'existing', name: 'rg-idp-apps-dev' },
        aksCluster: { mode: 'existing', name: 'aks', resourceGroup: 'rg-p' },
        containerRegistry: { mode: 'existing', name: 'acr', resourceGroup: 'rg-p' },
        namespace: { mode: 'new', name: 'orders-api' },
        runtimeCapability: { type: 'storage', mode: 'existing', name: 'st' },
      },
    });
    expect(body.application_name).toBe('orders-api');
    expect(body.tenant_id).toBe('tenant');
    expect(body.management_group).toBe('xycorp-corp');
    expect(body.resource_group).toEqual({ mode: 'existing', id: undefined, name: 'rg-idp-apps-dev' });
    expect(body.runtime_capability.type).toBe('storage');
    expect(body.availability.tier).toBe('standard');
  });
});

describe('toOrchestratorRequest endpoint host', () => {
  it('sends an empty host so the server applies the gateway default', () => {
    const body = toOrchestratorRequest({
      idempotencyKey: 'scaffolder-2',
      name: 'orders-api',
      owner: 'group:default/team-orders',
      environment: 'dev',
      stack: 'nestjs',
      repoVisibility: 'public',
      availability: { tier: 'standard' },
      infrastructure: {
        region: 'uksouth',
        subscription: { mode: 'existing', id: 'sub' },
        resourceGroup: { mode: 'existing', name: 'rg-idp-apps-dev' },
        aksCluster: { mode: 'existing', name: 'aks', resourceGroup: 'rg-p' },
        containerRegistry: { mode: 'existing', name: 'acr', resourceGroup: 'rg-p' },
        namespace: { mode: 'new', name: 'orders-api' },
        runtimeCapability: { type: 'none', mode: 'existing' },
      },
    });
    expect(body.endpoint_host).toBe('');
  });
});
