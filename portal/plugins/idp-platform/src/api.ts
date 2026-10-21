import { createApiRef, type DiscoveryApi, type FetchApi } from '@backstage/core-plugin-api';
import { ResponseError } from '@backstage/errors';
import type { Capabilities, ManagementGroup, OperationsView, RequestView, Tenant } from '@internal/plugin-idp-platform-common';

export interface NamedResource {
  id: string;
  name: string;
  location?: string;
  resource_group?: string;
  sku?: string;
  zones?: number;
  ha_eligible?: boolean;
  login_server?: string;
  /** AKS clusters only: gateway domain from the allowlist. */
  base_domain?: string | null;
}

export interface Stack {
  id: string;
  name: string;
  enabled: boolean;
}

export interface SubscriptionFilter {
  environment?: string;
  tenantId?: string;
  managementGroup?: string;
}

export interface IdpApi {
  tenants(environment?: string): Promise<Tenant[]>;
  managementGroups(tenantId: string, environment?: string): Promise<ManagementGroup[]>;
  subscriptions(filter?: SubscriptionFilter): Promise<{ id: string; name: string; quota_id?: string }[]>;
  capabilities(subscriptionId: string, region: string): Promise<Capabilities>;
  list(subscriptionId: string, kind: 'resource-groups' | 'aks-clusters' | 'container-registries',
    environment?: string): Promise<NamedResource[]>;
  dataResources(subscriptionId: string, type: 'storage' | 'keyvault', environment?: string,
    resourceGroup?: string): Promise<NamedResource[]>;
  stacks(): Promise<Stack[]>;
  requestsFor(application: string): Promise<RequestView[]>;
  approvals(): Promise<RequestView[]>;
  decide(requestId: string, decision: 'approve' | 'reject', planHash: string, comment: string): Promise<RequestView>;
  cancel(requestId: string): Promise<RequestView>;
  cleanup(requestId: string): Promise<RequestView>;
  retry(requestId: string): Promise<RequestView>;
  operations(requestId: string): Promise<OperationsView>;
}

export const idpApiRef = createApiRef<IdpApi>({ id: 'plugin.idp.service' });

/** Talks only to the Backstage bridge (/api/idp); the browser never calls the Python services. */
export class IdpClient implements IdpApi {
  constructor(private readonly deps: { discoveryApi: DiscoveryApi; fetchApi: FetchApi }) {}

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const base = await this.deps.discoveryApi.getBaseUrl('idp');
    const res = await this.deps.fetchApi.fetch(`${base}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
    if (!res.ok) throw await ResponseError.fromResponse(res);
    return (await res.json()) as T;
  }

  private qs(params: Record<string, string | undefined>): string {
    const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
    return s ? `?${s}` : '';
  }

  tenants(environment?: string) {
    return this.req<Tenant[]>(`/discovery/tenants${this.qs({ environment })}`);
  }
  managementGroups(tenantId: string, environment?: string) {
    return this.req<ManagementGroup[]>(`/discovery/management-groups${this.qs({ tenant_id: tenantId, environment })}`);
  }
  subscriptions(filter: SubscriptionFilter = {}) {
    return this.req<{ id: string; name: string; quota_id?: string }[]>(`/discovery/subscriptions${this.qs({
      environment: filter.environment,
      tenant_id: filter.tenantId,
      management_group: filter.managementGroup,
    })}`);
  }
  capabilities(subscriptionId: string, region: string) {
    return this.req<Capabilities>(`/discovery/subscriptions/${encodeURIComponent(subscriptionId)}/capabilities${this.qs({ region })}`);
  }
  list(subscriptionId: string, kind: 'resource-groups' | 'aks-clusters' | 'container-registries', environment?: string) {
    return this.req<NamedResource[]>(`/discovery/subscriptions/${encodeURIComponent(subscriptionId)}/${kind}${this.qs({ environment })}`);
  }
  dataResources(subscriptionId: string, type: 'storage' | 'keyvault', environment?: string, resourceGroup?: string) {
    return this.req<NamedResource[]>(`/discovery/subscriptions/${encodeURIComponent(subscriptionId)}/resources${this.qs({
      type, environment, resource_group: resourceGroup })}`);
  }
  stacks() {
    return this.req<Stack[]>('/stacks');
  }
  requestsFor(application: string) {
    return this.req<RequestView[]>(`/requests${this.qs({ application })}`);
  }
  approvals() {
    return this.req<RequestView[]>('/approvals');
  }
  decide(requestId: string, decision: 'approve' | 'reject', planHash: string, comment: string) {
    return this.req<RequestView>(`/requests/${encodeURIComponent(requestId)}/approval`, {
      method: 'POST',
      body: JSON.stringify({ decision, plan_hash: planHash, comment }),
    });
  }
  cancel(requestId: string) {
    return this.req<RequestView>(`/requests/${encodeURIComponent(requestId)}/cancel`, { method: 'POST' });
  }
  cleanup(requestId: string) {
    return this.req<RequestView>(`/requests/${encodeURIComponent(requestId)}/cleanup`, { method: 'POST' });
  }
  retry(requestId: string) {
    return this.req<RequestView>(`/requests/${encodeURIComponent(requestId)}/retry`, { method: 'POST' });
  }
  operations(requestId: string) {
    return this.req<OperationsView>(`/requests/${encodeURIComponent(requestId)}/operations`);
  }
}
