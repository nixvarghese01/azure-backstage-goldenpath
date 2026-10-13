import { Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { FieldExtensionComponentProps, FieldValidation } from '@backstage/plugin-scaffolder-react';
import type {
  Capabilities,
  InfrastructureSelection,
  Mode,
  RuntimeCapability,
  Selection,
} from '@internal/plugin-sportify-platform-common';
import {
  Box,
  FormControlLabel,
  FormHelperText,
  MenuItem,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React, { useEffect, useMemo } from 'react';
import useAsync from 'react-use/esm/useAsync';
import { type NamedResource, sportifyApiRef } from '../api';

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

interface RowProps {
  label: string;
  value: Selection;
  onChange: (s: Selection) => void;
  options?: NamedResource[];
  capability?: { available: boolean; reason?: string | null };
  newPlaceholder: string;
  newHelp?: string;
  describe?: (r: NamedResource) => string;
  existingDisabledReason?: string;
}

/** One resource: (•) Create new  ( ) Select existing, with the reason when an option is unavailable. */
const ResourceRow = ({ label, value, onChange, options, capability, newPlaceholder, newHelp, describe,
  existingDisabledReason }: RowProps) => {
  const newDisabled = capability ? !capability.available : false;
  const existingDisabled = !!existingDisabledReason || (options !== undefined && options.length === 0);
  return (
    <Box mb={3}>
      <Typography variant="subtitle2">{label}</Typography>
      <RadioGroup row value={value.mode} onChange={e => onChange({ mode: e.target.value as Mode })}>
        <FormControlLabel value="new" control={<Radio />} label="Create new" disabled={newDisabled} />
        <FormControlLabel value="existing" control={<Radio />} label="Select existing" disabled={existingDisabled} />
      </RadioGroup>
      {newDisabled && capability?.reason && <FormHelperText>Create new unavailable: {capability.reason}</FormHelperText>}
      {existingDisabled && (
        <FormHelperText>
          Select existing unavailable: {existingDisabledReason ?? 'nothing approved was found (check the allowlist and the discovery identity\'s Reader access).'}
        </FormHelperText>
      )}
      {value.mode === 'new' ? (
        <TextField
          fullWidth
          size="small"
          label="Name"
          placeholder={newPlaceholder}
          helperText={newHelp}
          value={value.name ?? ''}
          onChange={e => onChange({ ...value, name: e.target.value.trim() })}
        />
      ) : (
        <TextField
          select
          fullWidth
          size="small"
          label="Approved resource"
          value={value.name ?? ''}
          onChange={e => {
            const r = options?.find(o => o.name === e.target.value);
            onChange({ mode: 'existing', name: r?.name, id: r?.id, resourceGroup: r?.resource_group });
          }}
        >
          {(options ?? []).map(o => (
            <MenuItem key={o.id} value={o.name}>
              {o.name}{describe ? ` - ${describe(o)}` : ''}
            </MenuItem>
          ))}
        </TextField>
      )}
    </Box>
  );
};

export const AzureResourcePicker = (props: FieldExtensionComponentProps<InfrastructureSelection>) => {
  const { formData, onChange, formContext, rawErrors } = props;
  const ctx = (formContext as any)?.formData ?? {};
  const environment: string = ctx.environment ?? 'dev';
  const appName: string = ctx.name ?? '';
  const api = useApi(sportifyApiRef);
  const value = useMemo(() => formData ?? defaults(appName), [formData, appName]);
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
  useEffect(() => {
    if (region && region !== value.region) onChange({ ...value, region });
  }, [region]); // eslint-disable-line react-hooks/exhaustive-deps

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
      {rawErrors?.map(e => <Alert key={e} severity="error">{e}</Alert>)}

      <ResourceRow
        label="Subscription"
        value={value.subscription}
        onChange={s => onChange({
          ...value,
          subscription: s,
          // A new subscription forces new resources below.
          ...(s.mode === 'new' ? { resourceGroup: { mode: 'new' }, aksCluster: { mode: 'new' }, containerRegistry: { mode: 'new' } } : {}),
        })}
        options={(subs.value ?? []).map(s => ({ id: s.id, name: s.name }))}
        capability={caps.value ? cap('subscription') : { available: false, reason: 'Select an existing subscription first to check billing capabilities.' }}
        newPlaceholder="sub-orders-dev"
      />
      {value.subscription.mode === 'existing' && value.subscription.name && (
        <Box mb={2}>
          <Typography variant="caption">Region: {region || 'n/a'}</Typography>
        </Box>
      )}

      <ResourceRow label="Resource group" value={value.resourceGroup} onChange={s => set('resourceGroup', s)}
        options={groups.value} capability={cap('resourceGroup')} newPlaceholder={`rg-${appName || 'app'}-${environment}`}
        newHelp="Must look like rg-<name>." describe={r => r.location ?? ''} existingDisabledReason={mustBeNew} />

      <ResourceRow label="AKS cluster (shared)" value={value.aksCluster} onChange={s => set('aksCluster', s)}
        options={clusters.value} capability={cap('aksCluster')} newPlaceholder={`aks-sportify-${environment}-2`}
        newHelp="A new cluster is a shared platform resource: it is added through a platform pull request and approved by the platform team."
        describe={r => `${r.zones ?? 0} zone(s)${r.ha_eligible ? ', HA-eligible' : ''}`} existingDisabledReason={mustBeNew} />

      <ResourceRow label="Container registry (shared)" value={value.containerRegistry} onChange={s => set('containerRegistry', s)}
        options={registries.value} capability={cap('containerRegistry')} newPlaceholder={`acrsportify${environment}2`}
        newHelp="5-50 letters or digits. Added through a platform pull request." describe={r => r.sku ?? ''}
        existingDisabledReason={mustBeNew} />

      <ResourceRow label="Kubernetes namespace" value={value.namespace} onChange={s => set('namespace', s)}
        capability={cap('namespace')} newPlaceholder={appName || 'my-app'}
        newHelp="Defaults to the application name." existingDisabledReason="Existing namespaces are entered by name and their ownership is checked at plan time."
      />

      <Box mb={1}>
        <TextField select size="small" label="Runtime capability" value={value.runtimeCapability.type}
          onChange={e => set('runtimeCapability', { type: e.target.value as RuntimeCapability['type'], mode: 'existing' })}>
          <MenuItem value="storage">Azure Storage (blob read/write)</MenuItem>
          <MenuItem value="keyvault">Key Vault (read secrets)</MenuItem>
          <MenuItem value="none">None</MenuItem>
        </TextField>
      </Box>
      {value.runtimeCapability.type !== 'none' && (
        <ResourceRow
          label={value.runtimeCapability.type === 'storage' ? 'Storage account' : 'Key Vault'}
          value={value.runtimeCapability}
          onChange={s => set('runtimeCapability', { ...s, type: value.runtimeCapability.type })}
          options={data.value}
          capability={caps.value?.create_new[value.runtimeCapability.type === 'storage' ? 'storage_account' : 'key_vault']}
          newPlaceholder={value.runtimeCapability.type === 'storage' ? `st${appName.replace(/-/g, '')}${environment}` : `kv-${appName}-${environment}`}
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
