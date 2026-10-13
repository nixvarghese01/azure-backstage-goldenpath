import { Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import type {
  Capabilities,
  InfrastructureSelection,
  RuntimeCapability,
  Selection,
} from '@internal/plugin-sportify-platform-common';
import { Box, FormHelperText, MenuItem, TextField, Typography } from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React, { useEffect, useMemo } from 'react';
import useAsync from 'react-use/esm/useAsync';
import { type NamedResource, sportifyApiRef } from '../api';
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

/** The first approved resource is the platform default for an empty "existing" selection. */
function firstApproved(s: Selection, list?: NamedResource[]): Selection | undefined {
  if (s.mode !== 'existing' || s.name || !list?.length) return undefined;
  const r = list[0];
  return { mode: 'existing', name: r.name, id: r.id, resourceGroup: r.resource_group };
}

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
}

/** One resource: a dropdown of approved resources (first = default) plus "Create new…". */
const ResourceSelect = ({ label, value, onChange, options, capability, suggestedName, newHelp, describe,
  existingDisabledReason }: ResourceProps) => {
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
    />
  );
};

export const AzureResourcePicker = (props: FieldExtensionComponentProps<InfrastructureSelection>) => {
  const { formData, onChange, formContext, rawErrors } = props;
  const ctx = (formContext as any)?.formData ?? {};
  const environment: string = ctx.environment ?? 'dev';
  const appName: string = ctx.name ?? '';
  const demoOnly = ['fastapi', 'go', 'dotnet', 'springboot', 'nextjs', 'react', 'vue'].includes(ctx.stack);
  const api = useApi(sportifyApiRef);
  const value = useMemo<InfrastructureSelection>(() => formData ?? {
    ...defaults(appName),
    ...(demoOnly ? { runtimeCapability: { type: 'none' as const, mode: 'existing' as const } } : {}),
  }, [formData, appName, demoOnly]);
  const set = (key: Key, s: Selection | RuntimeCapability) => onChange({ ...value, [key]: s });

  const subs = useAsync(() => api.subscriptions(environment), [api, environment]);
  const subId = value.subscription.mode === 'existing' ? value.subscription.id : undefined;

  const groups = useAsync(async () => (subId ? api.list(subId, 'resource-groups', environment) : []), [api, subId, environment]);
  const clusters = useAsync(async () => (subId ? api.list(subId, 'aks-clusters', environment) : []), [api, subId, environment]);
  const registries = useAsync(async () => (subId ? api.list(subId, 'container-registries', environment) : []), [api, subId, environment]);
  const dataType = value.runtimeCapability.type === 'keyvault' ? 'keyvault' : 'storage';
  const data = useAsync(async () => (subId && value.runtimeCapability.type !== 'none' ? api.dataResources(subId, dataType, environment) : []),
    [api, subId, dataType, environment]);

  // Region follows the selected resource group (or the first approved one).
  const region = useMemo(() => {
    const rg = groups.value?.find(g => g.name === value.resourceGroup.name) ?? groups.value?.[0];
    return rg?.location ?? value.region ?? '';
  }, [groups.value, value.resourceGroup.name, value.region]);

  // Prefill the platform defaults as the approved lists arrive; never overrides a user's choice.
  useEffect(() => {
    const next: InfrastructureSelection = { ...value };
    let changed = false;
    const apply = (key: 'subscription' | 'resourceGroup' | 'aksCluster' | 'containerRegistry', list?: NamedResource[]) => {
      const picked = firstApproved(next[key], list);
      if (picked) {
        next[key] = picked;
        changed = true;
      }
    };
    apply('subscription', subs.value?.map(s => ({ id: s.id, name: s.name })));
    apply('resourceGroup', groups.value);
    apply('aksCluster', clusters.value);
    apply('containerRegistry', registries.value);
    if (next.runtimeCapability.type !== 'none') {
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
  }, [subs.value, groups.value, clusters.value, registries.value, data.value, appName, region, value]); // eslint-disable-line react-hooks/exhaustive-deps

  const caps = useAsync(async (): Promise<Capabilities | undefined> =>
    (subId && region ? api.capabilities(subId, region) : undefined), [api, subId, region]);
  const cap = (key: Key) => caps.value?.create_new[CAP_KEY[key]];
  const newSub = value.subscription.mode === 'new';
  const mustBeNew = newSub ? 'A new subscription has no existing resources.' : undefined;

  if (subs.loading) return <Progress />;
  if (subs.error) return <Alert severity="error">Couldn't load subscriptions: {subs.error.message}</Alert>;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Azure resources</Typography>
      <Typography variant="body2" gutterBottom>
        Approved platform defaults are preselected. Change a dropdown only if this application needs something else.
      </Typography>
      {rawErrors?.map(e => <Alert key={e} severity="error">{e}</Alert>)}

      <ResourceSelect
        label="Subscription"
        value={value.subscription}
        onChange={s => onChange({
          ...value,
          subscription: s,
          // A new subscription forces new resources below.
          ...(s.mode === 'new' ? { resourceGroup: { mode: 'new' }, aksCluster: { mode: 'new' }, containerRegistry: { mode: 'new' } } : {}),
        })}
        options={(subs.value ?? []).map(s => ({ id: s.id, name: s.name }))}
        capability={caps.value ? cap('subscription') : { available: false, reason: 'select an existing subscription first to check billing capabilities.' }}
        suggestedName={`sub-${appName || 'app'}-${environment}`}
      />
      {value.subscription.mode === 'existing' && value.subscription.name && (
        <Box mb={2}>
          <Typography variant="caption">Region: {region || 'n/a'}</Typography>
        </Box>
      )}

      <ResourceSelect label="Resource group" value={value.resourceGroup} onChange={s => set('resourceGroup', s)}
        options={groups.value} capability={cap('resourceGroup')} suggestedName={`rg-${appName || 'app'}-${environment}`}
        newHelp="Must look like rg-<name>." describe={r => r.location ?? ''} existingDisabledReason={mustBeNew} />

      <ResourceSelect label="AKS cluster (shared)" value={value.aksCluster} onChange={s => set('aksCluster', s)}
        options={clusters.value} capability={cap('aksCluster')} suggestedName={`aks-sportify-${environment}-2`}
        newHelp="A new cluster is a shared platform resource: it is added through a platform pull request and approved by the platform team."
        describe={r => `${r.zones ?? 0} zone(s)${r.ha_eligible ? ', HA-eligible' : ''}`} existingDisabledReason={mustBeNew} />

      <ResourceSelect label="Container registry (shared)" value={value.containerRegistry} onChange={s => set('containerRegistry', s)}
        options={registries.value} capability={cap('containerRegistry')} suggestedName={`acrsportify${environment}2`}
        newHelp="5-50 letters or digits. Added through a platform pull request." describe={r => r.sku ?? ''}
        existingDisabledReason={mustBeNew} />

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
        customPlaceholder={appName || 'my-app'}
        customHelp="A DNS label; existing namespaces have their ownership checked at plan time."
      />

      <Box mb={2}>
        <TextField select fullWidth size="small" label="Runtime capability" value={value.runtimeCapability.type}
          onChange={e => set('runtimeCapability', { type: e.target.value as RuntimeCapability['type'], mode: 'existing' })}>
          <MenuItem value="storage" disabled={demoOnly}>Azure Storage (blob read/write){demoOnly ? '' : ' (default)'}</MenuItem>
          <MenuItem value="keyvault" disabled={demoOnly}>Key Vault (read secrets)</MenuItem>
          <MenuItem value="none">None{demoOnly ? ' (default)' : ''}</MenuItem>
        </TextField>
        {demoOnly && <FormHelperText>This demo starter supports None; Azure data integrations are not implemented.</FormHelperText>}
      </Box>
      {value.runtimeCapability.type !== 'none' && (
        <ResourceSelect
          label={value.runtimeCapability.type === 'storage' ? 'Storage account' : 'Key Vault'}
          value={value.runtimeCapability}
          onChange={s => set('runtimeCapability', { ...s, type: value.runtimeCapability.type })}
          options={data.value}
          capability={caps.value?.create_new[value.runtimeCapability.type === 'storage' ? 'storage_account' : 'key_vault']}
          suggestedName={value.runtimeCapability.type === 'storage' ? `st${appName.replace(/-/g, '')}${environment}` : `kv-${appName}-${environment}`}
          describe={r => r.sku ?? ''}
          existingDisabledReason={mustBeNew}
        />
      )}
      <FormHelperText>
        Every selection is re-validated on the server before anything is created. Access is granted to the
        application's own identity (Workload Identity) - no keys or connection strings.
      </FormHelperText>
    </Box>
  );
};

const RG = /^rg-[a-z0-9-]{2,80}$/;
const NS = /^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$/;

export const validateInfrastructure = (value: InfrastructureSelection, validation: FieldValidation) => {
  if (!value) {
    validation.addError('Choose the Azure resources.');
    return;
  }
  const need = (s: Selection, label: string) => {
    if (s.mode === 'existing' && !s.name) validation.addError(`${label}: select an approved resource.`);
    if (s.mode === 'new' && !s.name) validation.addError(`${label}: enter a name.`);
  };
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
