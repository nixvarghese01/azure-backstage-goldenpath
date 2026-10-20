import { createPermission } from '@backstage/plugin-permission-common';

/** Approve or reject an infrastructure plan in Backstage (ADR approval-in-Backstage, README). */
export const idpRequestApprovePermission = createPermission({
  name: 'idp.request.approve',
  attributes: { action: 'update' },
});

export const idpPermissions = [idpRequestApprovePermission];

export type Mode = 'new' | 'existing';

export interface Selection {
  mode: Mode;
  id?: string;
  name?: string;
  resourceGroup?: string;
}

export interface RuntimeCapability extends Selection {
  type: 'storage' | 'keyvault' | 'none';
}

/** Value produced by the IdpAzureResourcePicker field. */
export interface InfrastructureSelection {
  /** Entra tenant and management group the subscription was picked under (CAF landing zones). */
  tenantId?: string;
  managementGroup?: string;
  region: string;
  subscription: Selection;
  resourceGroup: Selection;
  aksCluster: Selection;
  containerRegistry: Selection;
  namespace: Selection;
  runtimeCapability: RuntimeCapability;
  /** Gateway domain of the selected cluster; the endpoint host defaults to <name>.<baseDomain>. */
  baseDomain?: string;
}

/** Value produced by the IdpAvailabilityPicker field (ADR-0004). */
export interface AvailabilitySelection {
  tier: 'standard' | 'ha';
  reason?: string;
  justification?: string;
  sloTarget?: string;
}

export interface Tenant {
  id: string;
  name: string;
  default_domain?: string | null;
}

/** A management group; `path` runs from the Tenant Root Group down to this group. */
export interface ManagementGroup {
  id: string;
  name: string;
  tenant_id: string;
  parent_id?: string | null;
  path: string[];
  depth: number;
}

export interface CapabilityOption {
  available: boolean;
  reason?: string | null;
}

export interface Capabilities {
  subscription_id: string;
  quota_id?: string | null;
  create_new: Record<string, CapabilityOption>;
  regional_vcpus?: { used: number; limit: number } | null;
}

export interface Outcome {
  name: string;
  status: 'pending' | 'succeeded' | 'failed' | 'skipped';
}

export interface RequestView {
  id: string;
  state: string;
  application_name: string;
  environment: string;
  owner: string;
  stack: string;
  requested_by: string;
  ready_for_repository: boolean;
  /** The requested host, or the platform default (<name>.<gateway domain>) once validated. */
  endpoint_host: string;
  validation: { valid?: boolean; errors?: Finding[]; warnings?: Finding[]; platform_changes?: string[] };
  repository: { owner?: string; name?: string; url?: string };
  platform: { pr_url?: string; changes?: string[] };
  plan: { hash?: string; summary?: PlanSummary; mode?: string };
  approval: {
    decision?: string; // 'pending' while an environment needs more distinct approvers
    by?: string;
    comment?: string;
    required?: number;
    approvals?: { by: string; at: string; comment?: string; self_approved?: boolean }[];
  };
  application: { pr_url?: string; image?: string };
  deployment: { endpoint?: string; pods?: string; run_url?: string };
  cleanup: { stage?: string };
  availability: { tier?: string; reason?: string; justification?: string; slo_target?: string };
  error: { stage?: string; message?: string; run_url?: string; created?: string[] };
  runs: { stage: string; run_id?: string; url?: string; status: string; at: string }[];
  outcomes: Outcome[];
  urls: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  field: string;
  code: string;
  message: string;
}

export interface PlanSummary {
  add?: number;
  change?: number;
  destroy?: number;
  reused?: number;
  resources?: { address: string; type: string; actions: string[] }[];
}
