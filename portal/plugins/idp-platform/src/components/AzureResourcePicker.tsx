import { Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import type {
  Capabilities,
  InfrastructureSelection,
  ManagementGroup,
  RuntimeCapability,
  Selection,
} from '@internal/plugin-idp-platform-common';
import { Box, Breadcrumbs, FormHelperText, MenuItem, Paper, TextField, Typography } from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React, { useEffect, useMemo } from 'react';
import useAsync from 'react-use/esm/useAsync';
import { type NamedResource, idpApiRef } from '../api';
import { CUSTOM, DefaultOrCustomSelect } from './DefaultOrCustomSelect';

type Key = 'subscription' | 'resourceGroup' | 'aksCluster' | 'containerRegistry' | 'namespace' | 'runtimeCapability';
const CAP_KEY: Record<Key, string> = {
  subscription: 'subscription',
  resourceGroup: 'resource_group',
  aksCluster: 'aks_cluster',
  containerRegistry: 'container_registry',
  namespace: 'namespace',
  runtimeCapability: 'storage_account',
};

function defaults(appName: string): InfrastructureSelection {
  return {
    region: '',
    subscription: { mode: 'existing' },
    resourceGroup: { mode: 'existing' },
    aksCluster: { mode: 'existing' },
    containerRegistry: { mode: 'existing' },
    namespace: { mode: 'new', name: appName },
    runtimeCapability: { type: 'storage', mode: 'existing' },
  };
}

/** Everything below the subscription, reset when a level above it changes (the CAF cascade). */
function belowSubscription(value: InfrastructureSelection): Partial<InfrastructureSelection> {
  return {
    subscription: { mode: 'existing' },
    resourceGroup: { mode: 'existing' },
    aksCluster: { mode: 'existing' },
    containerRegistry: { mode: 'existing' },
    runtimeCapability: { type: value.runtimeCapability.type, mode: 'existing' },
    region: '',
  };
}

/** The first approved resource is the platform default for an empty "existing" selection. */
function firstApproved(s: Selection, list?: NamedResource[]): Selection | undefined {
  if (s.mode !== 'existing' || s.name || !list?.length) return undefined;
  const r = list[0];
  return { mode: 'existing', name: r.name, id: r.id, resourceGroup: r.resource_group };
}

/** Default landing zone: the deepest group that holds an approved subscription (e.g. Corp). */
function defaultManagementGroup(groups?: ManagementGroup[]): ManagementGroup | undefined {
  return groups?.reduce<ManagementGroup | undefined>((best, g) => (!best || g.depth > best.depth ? g : best), undefined);
}

/** An outlined, titled panel: one level of the hierarchy. */
const Section = ({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) => (
  <Paper variant="outlined">
    <Box p={2} mb={2}>
      <Typography variant="subtitle1"><strong>{title}</strong></Typography>
      <Typography variant="body2" color="textSecondary" gutterBottom>{subtitle}</Typography>
      <Box mt={2}>{children}</Box>
    </Box>
  </Paper>
);

interface ResourceProps {
  label: string;
  value: Selection;
  onChange: (s: Selection) => void;
  options?: NamedResource[];
  capability?: { available: boolean; reason?: string | null };
  suggestedName: string;
  newHelp?: string;
  describe?: (r: NamedResource) => string;
  existingDisabledReason?: string;
  example?: string;
}

/** One resource: a dropdown of approved resources (first = default) plus "Create new…". */
const ResourceSelect = ({ label, value, onChange, options, capability, suggestedName, newHelp, describe,
  existingDisabledReason, example }: ResourceProps) => {
  const approved = existingDisabledReason ? [] : options ?? [];
  const noneApproved = approved.length === 0 && value.mode !== 'new';
  return (
    <DefaultOrCustomSelect
      label={label}
      options={approved.map((o, i) => ({
        value: o.name,
        label: `${o.name}${describe ? ` - ${describe(o)}` : ''}${i === 0 ? ' (default)' : ''}`,
      }))}
      selected={value.mode === 'new' ? CUSTOM : value.name ?? ''}
      onSelect={v => {
        if (v === CUSTOM) {
          onChange({ mode: 'new', name: suggestedName });
          return;
        }
        const r = approved.find(o => o.name === v);
        onChange({ mode: 'existing', name: r?.name, id: r?.id, resourceGroup: r?.resource_group });
      }}
      customLabel="Create new…"
      customDisabledReason={capability && !capability.available ? capability.reason ?? 'not offered' : undefined}
      customValue={value.name}
      onCustomChange={name => onChange({ mode: 'new', name })}
      customFieldLabel="New name"
      customPlaceholder={suggestedName}
      customHelp={newHelp}
      helperText={noneApproved ? existingDisabledReason ??
        'Nothing approved was found; choose Create new… (or check the allowlist and the discovery identity\'s Reader access).'
        : undefined}
      example={example}
    />
  );
};

/**
 * Azure placement, walked in Cloud Adoption Framework order: tenant -> management group (landing
 * zone) -> subscription -> resource group -> the application's resources. Shared platform runtime
 * (AKS, ACR) comes from the same subscription. Works the same for a full Azure landing zones tenant
 * and for a single subscription under the Tenant Root Group.
 */
export const AzureResourcePicker = (props: FieldExtensionComponentProps<InfrastructureSelection>) => {
  const { formData, onChange, formContext, rawErrors } = props;
  const ctx = (formContext as any)?.formData ?? {};
  const environment: string = ctx.environment ?? 'dev';
  const appName: string = ctx.name ?? '';
  const app = appName || 'orders-api';
  const demoOnly = ['fastapi', 'go', 'dotnet', 'springboot', 'nextjs', 'react', 'vue'].includes(ctx.stack);
  const api = useApi(idpApiRef);
  // The form starts an object field as {} (not undefined), so the defaults fill whatever is missing.
  const value = useMemo<InfrastructureSelection>(() => ({
    ...defaults(appName),
    ...(demoOnly ? { runtimeCapability: { type: 'none' as const, mode: 'existing' as const } } : {}),
    ...formData,
  }), [formData, appName, demoOnly]);
  const set = (key: Key, s: Selection | RuntimeCapability) => onChange({ ...value, [key]: s });

  // ---- tenant -> management group -> subscription ----
  const tenants = useAsync(() => api.tenants(environment), [api, environment]);
  const tenantId = value.tenantId ?? tenants.value?.[0]?.id;
  const groups = useAsync(async () => (tenantId ? api.managementGroups(tenantId, environment) : []),
    [api, tenantId, environment]);
  const managementGroup = value.managementGroup ?? defaultManagementGroup(groups.value)?.id;
  const subs = useAsync(async () => (tenantId && managementGroup
    ? api.subscriptions({ environment, tenantId, managementGroup }) : []), [api, environment, tenantId, managementGroup]);
  const subId = value.subscription.mode === 'existing' ? value.subscription.id : undefined;

  // ---- resource group and what's inside it; shared runtime from the same subscription ----
  const rgs = useAsync(async () => (subId ? api.list(subId, 'resource-groups', environment) : []), [api, subId, environment]);
  const clusters = useAsync(async () => (subId ? api.list(subId, 'aks-clusters', environment) : []), [api, subId, environment]);
  const registries = useAsync(async () => (subId ? api.list(subId, 'container-registries', environment) : []), [api, subId, environment]);
  const rgName = value.resourceGroup.mode === 'existing' ? value.resourceGroup.name : undefined;
  const dataType = value.runtimeCapability.type === 'keyvault' ? 'keyvault' : 'storage';
  const data = useAsync(async () => (subId && rgName && value.runtimeCapability.type !== 'none'
    ? api.dataResources(subId, dataType, environment, rgName) : []), [api, subId, rgName, dataType, environment]);

  // Region follows the selected resource group (or the first approved one).
  const region = useMemo(() => {
    const rg = rgs.value?.find(g => g.name === value.resourceGroup.name) ?? rgs.value?.[0];
    return rg?.location ?? value.region ?? '';
  }, [rgs.value, value.resourceGroup.name, value.region]);

  // Prefill the platform defaults as each level's approved list arrives; never overrides a user's
  // choice, and never uses a list that is still loading for the previous parent.
  useEffect(() => {
    const next: InfrastructureSelection = { ...value };
    let changed = false;
    if (!next.tenantId && tenantId) {
      next.tenantId = tenantId;
      changed = true;
    }
    if (!next.managementGroup && managementGroup && !groups.loading) {
      next.managementGroup = managementGroup;
      changed = true;
    }
    const apply = (key: 'subscription' | 'resourceGroup' | 'aksCluster' | 'containerRegistry',
      list: NamedResource[] | undefined, loading: boolean) => {
      const picked = loading ? undefined : firstApproved(next[key], list);
      if (picked) {
        next[key] = picked;
        changed = true;
      }
    };
    apply('subscription', subs.value?.map(s => ({ id: s.id, name: s.name })), subs.loading);
    apply('resourceGroup', rgs.value, rgs.loading);
    apply('aksCluster', clusters.value, clusters.loading);
    apply('containerRegistry', registries.value, registries.loading);
    if (next.runtimeCapability.type !== 'none' && !data.loading) {
      const picked = firstApproved(next.runtimeCapability, data.value);
      if (picked) {
        next.runtimeCapability = { ...picked, type: next.runtimeCapability.type };
        changed = true;
      }
    }
    if (next.namespace.mode === 'new' && !next.namespace.name && appName) {
      next.namespace = { mode: 'new', name: appName };
      changed = true;
    }
    if (region && region !== next.region) {
      next.region = region;
      changed = true;
    }
    const cluster = clusters.value?.find(k => k.name === next.aksCluster.name);
    const baseDomain = (next.aksCluster.mode === 'existing' && cluster?.base_domain) || undefined;
    if (baseDomain !== next.baseDomain) {
      next.baseDomain = baseDomain;
      changed = true;
    }
    if (changed) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId, managementGroup, groups.loading, subs.value, subs.loading, rgs.value, rgs.loading, clusters.value,
    clusters.loading, registries.value, registries.loading, data.value, data.loading, appName, region, value]);

  const caps = useAsync(async (): Promise<Capabilities | undefined> =>
    (subId && region ? api.capabilities(subId, region) : undefined), [api, subId, region]);
  const cap = (key: Key) => caps.value?.create_new[CAP_KEY[key]];
  const newSub = value.subscription.mode === 'new';
  const mustBeNew = newSub ? 'A new subscription has no existing resources.' : undefined;
  const newRg = value.resourceGroup.mode === 'new' ? 'A new resource group has no existing resources yet.' : undefined;

  if (tenants.loading) return <Progress />;
  if (tenants.error) return <Alert severity="error">Could not load Azure tenants: {tenants.error.message}</Alert>;
  if (!tenants.value?.length) {
    return <Alert severity="warning">No approved Azure tenant was found. Ask the platform team to check the allowlist.</Alert>;
  }

  const tenant = tenants.value.find(t => t.id === tenantId);
  const group = groups.value?.find(g => g.id === managementGroup);
  const runtime = value.runtimeCapability.type;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Azure resources</Typography>
      <Typography variant="body2" gutterBottom>
        Choose where the application lives, top-down as in the Azure Cloud Adoption Framework. Approved platform
        defaults are preselected; change a dropdown only if this application needs something else.
      </Typography>
      <Box mb={2}>
        <Breadcrumbs aria-label="Selected Azure location">
          <Typography variant="caption">{tenant?.name ?? 'Tenant'}</Typography>
          {(group?.path.slice(1) ?? []).map(p => <Typography key={p} variant="caption">{p}</Typography>)}
          <Typography variant="caption">{value.subscription.name ?? 'Subscription'}</Typography>
          <Typography variant="caption" color="textPrimary">{value.resourceGroup.name ?? 'Resource group'}</Typography>
        </Breadcrumbs>
      </Box>
      {rawErrors?.map(e => <Alert key={e} severity="error">{e}</Alert>)}

      <Section title="1. Azure location" subtitle="Tenant, landing zone, subscription and resource group.">
        <DefaultOrCustomSelect
          label="Tenant (Microsoft Entra ID)"
          options={tenants.value.map(t => ({ value: t.id, label: `${t.name}${t.default_domain ? ` (${t.default_domain})` : ''}` }))}
          selected={tenantId ?? ''}
          onSelect={v => onChange({ ...value, ...belowSubscription(value), tenantId: v, managementGroup: undefined })}
          example="The directory the subscriptions belong to, e.g. XY Corp (xycorp.onmicrosoft.com). Preselected when there is only one."
        />
        {groups.error && <Alert severity="error">Could not load management groups: {groups.error.message}</Alert>}
        <DefaultOrCustomSelect
          label="Management group (landing zone)"
          options={(groups.value ?? []).map(g => ({ value: g.id, label: `${'   '.repeat(g.depth)}${g.depth ? '└ ' : ''}${g.name}` }))}
          selected={managementGroup ?? ''}
          onSelect={v => onChange({ ...value, ...belowSubscription(value), managementGroup: v })}
          example={'Landing zone for this application, e.g. Landing zones / Corp for internal apps or Online for '
            + 'internet-facing ones. Groups are owned by the platform team; only groups with approved subscriptions are shown.'}
        />
        {subs.error && <Alert severity="error">Could not load subscriptions: {subs.error.message}</Alert>}
        <ResourceSelect
          label="Subscription"
          value={value.subscription}
          onChange={s => onChange({
            ...value,
            ...belowSubscription(value),
            subscription: s,
            // A new subscription forces new resources below.
            ...(s.mode === 'new' ? { resourceGroup: { mode: 'new' }, aksCluster: { mode: 'new' }, containerRegistry: { mode: 'new' } } : {}),
          })}
          options={(subs.value ?? []).map(s => ({ id: s.id, name: s.name }))}
          capability={caps.value ? cap('subscription') : { available: false, reason: 'select an existing subscription first to check billing capabilities.' }}
          suggestedName={`sub-${app}-${environment}`}
          example={`Application landing zone subscription under ${group?.name ?? 'the selected group'}, e.g. sub-idp-${environment}.`}
        />
        <ResourceSelect label="Resource group" value={value.resourceGroup}
          onChange={s => onChange({ ...value, resourceGroup: s, runtimeCapability: { type: runtime, mode: 'existing' } })}
          options={rgs.value} capability={cap('resourceGroup')} suggestedName={`rg-${app}-${environment}`}
          newHelp="Must look like rg-<name>." describe={r => r.location ?? ''} existingDisabledReason={mustBeNew}
          example={`Holds this application's Azure resources. CAF naming rg-<workload>-<environment>, e.g. rg-${app}-${environment}.`} />
        <Typography variant="caption">Region: {region || 'follows the resource group'}</Typography>
      </Section>

      <Section title="2. Application resources" subtitle={`Created in or reused from ${value.resourceGroup.name ?? 'the resource group'}; reached with the application's own identity.`}>
        <DefaultOrCustomSelect
          label="Kubernetes namespace"
          options={appName ? [{ value: appName, label: `${appName} (default: application name)` }] : []}
          selected={value.namespace.name && value.namespace.name === appName ? appName : CUSTOM}
          onSelect={v => set('namespace', { mode: 'new', name: v === CUSTOM ? value.namespace.name : appName })}
          customLabel="Custom…"
          customDisabledReason={cap('namespace') && !cap('namespace')?.available ? cap('namespace')?.reason ?? 'not offered' : undefined}
          customValue={value.namespace.name}
          onCustomChange={name => set('namespace', { mode: 'new', name })}
          customFieldLabel="Namespace"
          customPlaceholder={app}
          customHelp="A DNS label; existing namespaces have their ownership checked at plan time."
          example={`One namespace per application, e.g. ${app}.`}
        />
        <Box mb={2}>
          <TextField select fullWidth size="small" variant="outlined" label="Runtime capability" value={runtime}
            onChange={e => set('runtimeCapability', { type: e.target.value as RuntimeCapability['type'], mode: 'existing' })}>
            <MenuItem value="storage" disabled={demoOnly}>Azure Storage (blob read/write){demoOnly ? '' : ' (default)'}</MenuItem>
            <MenuItem value="keyvault" disabled={demoOnly}>Key Vault (read secrets)</MenuItem>
            <MenuItem value="none">None{demoOnly ? ' (default)' : ''}</MenuItem>
          </TextField>
          <FormHelperText>
            {demoOnly ? 'This demo starter supports None; Azure data integrations are not implemented.'
              : 'Storage for files such as order documents; Key Vault for secrets the app reads at runtime.'}
          </FormHelperText>
        </Box>
        {runtime !== 'none' && (
          <ResourceSelect
            label={runtime === 'storage' ? 'Storage account' : 'Key Vault'}
            value={value.runtimeCapability}
            onChange={s => set('runtimeCapability', { ...s, type: runtime })}
            options={data.value}
            capability={caps.value?.create_new[runtime === 'storage' ? 'storage_account' : 'key_vault']}
            suggestedName={runtime === 'storage' ? `st${app.replace(/-/g, '')}${environment}`.slice(0, 24) : `kv-${app}-${environment}`.slice(0, 24)}
            describe={r => r.sku ?? ''}
            existingDisabledReason={mustBeNew ?? newRg}
            example={runtime === 'storage'
              ? `3-24 lowercase letters and digits, CAF prefix st, e.g. st${app.replace(/-/g, '')}${environment}`.slice(0, 80)
              : `3-24 characters, CAF prefix kv, e.g. kv-${app}-${environment}`}
          />
        )}
      </Section>

      <Section title="3. Shared runtime" subtitle={`Run by the platform team in ${value.subscription.name ?? 'the subscription'}; shown as resource group / name.`}>
        <ResourceSelect label="AKS cluster (shared)" value={value.aksCluster} onChange={s => set('aksCluster', s)}
          options={clusters.value} capability={cap('aksCluster')} suggestedName={`aks-idp-${environment}-2`}
          newHelp="A new cluster is a shared platform resource: it is added through a platform pull request and approved by the platform team."
          describe={r => `in ${r.resource_group ?? '?'}, ${r.zones ?? 0} zone(s)${r.ha_eligible ? ', HA-eligible' : ''}`}
          existingDisabledReason={mustBeNew}
          example={`Most applications use the shared cluster, e.g. aks-idp-shared-${environment} in rg-idp-aks-${environment}.`} />
        <ResourceSelect label="Container registry (shared)" value={value.containerRegistry} onChange={s => set('containerRegistry', s)}
          options={registries.value} capability={cap('containerRegistry')} suggestedName={`acridp${environment}2`}
          newHelp="5-50 letters or digits. Added through a platform pull request."
          describe={r => `in ${r.resource_group ?? '?'}, ${r.sku ?? ''}`} existingDisabledReason={mustBeNew}
          example={`Where CI pushes the image, CAF prefix acr, letters and digits only, e.g. acridp${environment}.`} />
      </Section>
      <FormHelperText>
        Every selection is re-validated on the server before anything is created. Access is granted to the
        application's own identity (Workload Identity) - no keys or connection strings.
      </FormHelperText>
    </Box>
  );
};

const RG = /^rg-[a-z0-9-]{2,80}$/;
const NS = /^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$/;

export const validateInfrastructure = (input: InfrastructureSelection, validation: FieldValidation) => {
  // Validation can run before the picker's first change (the form's {}): judge it with the same defaults.
  const value: InfrastructureSelection = { ...defaults(''), ...input };
  const need = (s: Selection, label: string) => {
    if (s.mode === 'existing' && !s.name) validation.addError(`${label}: select an approved resource.`);
    if (s.mode === 'new' && !s.name) validation.addError(`${label}: enter a name.`);
  };
  if (!value.tenantId) validation.addError('Tenant: select one.');
  if (!value.managementGroup) validation.addError('Management group: select the landing zone.');
  if (value.subscription.mode === 'existing' && !value.subscription.id) validation.addError('Subscription: select one.');
  need(value.resourceGroup, 'Resource group');
  need(value.aksCluster, 'AKS cluster');
  need(value.containerRegistry, 'Container registry');
  need(value.namespace, 'Namespace');
  if (value.resourceGroup.mode === 'new' && value.resourceGroup.name && !RG.test(value.resourceGroup.name)) {
    validation.addError('Resource group names must look like rg-<name>.');
  }
  if (value.namespace.name && (!NS.test(value.namespace.name) || value.namespace.name.startsWith('kube-'))) {
    validation.addError('Namespace must be a DNS label and not start with kube-.');
  }
  if (value.runtimeCapability.type !== 'none') need(value.runtimeCapability, 'Runtime capability');
  if (!value.region) validation.addError('Region could not be determined; select a resource group.');
};
