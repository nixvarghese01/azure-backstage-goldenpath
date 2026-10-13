import { toOrchestratorRequest } from './submit';

describe('toOrchestratorRequest', () => {
  it('maps the form value to the orchestrator contract', () => {
    const body = toOrchestratorRequest({
      idempotencyKey: 'scaffolder-1',
      name: 'orders-api',
      owner: 'group:default/team-orders',
      environment: 'dev',
      stack: 'nestjs',
      endpointHost: 'orders-api.dev.sportify.example',
      repoVisibility: 'public',
      availability: { tier: 'standard' },
      infrastructure: {
        region: 'uksouth',
        subscription: { mode: 'existing', id: 'sub' },
        resourceGroup: { mode: 'existing', name: 'rg-sportify-apps-dev' },
        aksCluster: { mode: 'existing', name: 'aks', resourceGroup: 'rg-p' },
        containerRegistry: { mode: 'existing', name: 'acr', resourceGroup: 'rg-p' },
        namespace: { mode: 'new', name: 'orders-api' },
        runtimeCapability: { type: 'storage', mode: 'existing', name: 'st' },
      },
    });
    expect(body.application_name).toBe('orders-api');
    expect(body.resource_group).toEqual({ mode: 'existing', id: undefined, name: 'rg-sportify-apps-dev' });
    expect(body.runtime_capability.type).toBe('storage');
    expect(body.availability.tier).toBe('standard');
  });
});
