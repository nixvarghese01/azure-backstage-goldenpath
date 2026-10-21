import { InfoCard, Link, Progress, StatusAborted, StatusError, StatusOK, StatusPending, StatusWarning, Table } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import { useEntity } from '@backstage/plugin-catalog-react';
import type { OperationalHealth, OperationsView } from '@internal/plugin-idp-platform-common';
import { Box, Chip, Grid, Typography } from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React from 'react';
import useAsyncRetry from 'react-use/esm/useAsyncRetry';
import useInterval from 'react-use/esm/useInterval';
import { idpApiRef } from '../api';

/** Refresh while the tab is open; slower after a failure so an outage isn't hammered. */
export const REFRESH_MS = 30_000;
export const BACKOFF_MS = 120_000;

type Pod = NonNullable<OperationsView['pods']>[number];

const LINK_LABELS: Record<string, string> = {
  application: 'Application',
  repository: 'Repository',
  deployment: 'Last deployment run',
  runbook: 'Runbook',
  dashboard: 'Dashboard',
  logs: 'Logs',
  traces: 'Traces',
};

/** How each health reads to an owner. Unknown and stale are never shown as healthy. */
export function healthDisplay(view: Pick<OperationsView, 'health' | 'stale' | 'last_known_health'>): {
  label: string;
  tone: 'ok' | 'warning' | 'error' | 'pending' | 'aborted';
} {
  const labels: Record<OperationalHealth, string> = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    down: 'Down',
    stopped: 'Stopped (0 replicas)',
    missing: 'Missing from the cluster',
    unknown: 'Unknown',
    not_deployed: 'Not deployed yet',
    removed: 'Removed (cleaned up)',
  };
  const tones: Record<OperationalHealth, 'ok' | 'warning' | 'error' | 'pending' | 'aborted'> = {
    healthy: 'ok',
    degraded: 'warning',
    down: 'error',
    stopped: 'aborted',
    missing: 'error',
    unknown: 'pending',
    not_deployed: 'pending',
    removed: 'aborted',
  };
  if (view.health === 'unknown' && view.last_known_health) {
    return { label: `Unknown (last seen ${labels[view.last_known_health].toLowerCase()})`, tone: 'pending' };
  }
  if (view.stale && view.health === 'healthy') return { label: 'Unknown (stale)', tone: 'pending' };
  return { label: labels[view.health] ?? view.health, tone: tones[view.health] ?? 'pending' };
}

/** "observed 12 s ago" from the observation time, or why there is none. */
export function freshness(view: Pick<OperationsView, 'observed_at' | 'stale' | 'unavailable'>, now: Date): string {
  if (!view.observed_at) return view.unavailable ? `no observation (${view.unavailable.replace(/_/g, ' ')})` : 'not observed';
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(view.observed_at).getTime()) / 1000));
  const age = seconds < 120 ? `${seconds} s` : `${Math.round(seconds / 60)} min`;
  return `observed ${age} ago${view.stale ? ', stale' : ''}`;
}

const Status = ({ tone, children }: { tone: string; children: React.ReactNode }) => {
  switch (tone) {
    case 'ok': return <StatusOK>{children}</StatusOK>;
    case 'warning': return <StatusWarning>{children}</StatusWarning>;
    case 'error': return <StatusError>{children}</StatusError>;
    case 'aborted': return <StatusAborted>{children}</StatusAborted>;
    default: return <StatusPending>{children}</StatusPending>;
  }
};

/** Operations tab: what runs now (observed in the cluster), separate from how it was provisioned. */
export const OperationsContent = () => {
  const { entity } = useEntity();
  const api = useApi(idpApiRef);
  const { value, loading, error, retry } = useAsyncRetry(async () => {
    const [request] = await api.requestsFor(entity.metadata.name);
    return request ? api.operations(request.id) : undefined;
  }, [api, entity.metadata.name]);
  const failing = !!error || value?.health === 'unknown';
  let refresh: number | null = failing ? BACKOFF_MS : REFRESH_MS;
  if (document.hidden) refresh = null;
  useInterval(retry, refresh);

  if (loading && !value) return <Progress />;
  if (error && !value) return <Alert severity="error">Operations data is unavailable: {error.message}</Alert>;
  if (!value) return <Alert severity="info">No platform request found for this component.</Alert>;

  const shown = healthDisplay(value);
  const running = value.running?.[0];
  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <InfoCard title="Current health" subheader={`${value.environment} · ${value.namespace} · owner ${value.owner}`}>
          <Box display="flex" alignItems="center" gridGap={8} mb={1}>
            <Status tone={shown.tone}>{shown.label}</Status>
            {value.replicas && <Chip size="small" label={`${value.replicas.ready}/${value.replicas.desired} ready`} />}
          </Box>
          <Typography>{value.summary}</Typography>
          <Typography variant="caption" color="textSecondary">
            Source: {value.source ?? 'orchestrator'} · {freshness(value, new Date())}
          </Typography>
          {error && <Alert severity="warning" style={{ marginTop: 8 }}>Refresh failed: {error.message}</Alert>}
          {value.stale && value.observed_at && (
            <Alert severity="warning" style={{ marginTop: 8 }}>
              The cluster can't be read right now; the details below are from the last observation.
            </Alert>
          )}
          <Typography variant="body2" style={{ marginTop: 8 }}>
            Provisioning outcome (history): {value.provisioning_state}
          </Typography>
        </InfoCard>
      </Grid>
      <Grid item xs={12} md={6}>
        <InfoCard title="Running version">
          <Typography>{running ? <code>{running.image}</code> : 'Nothing observed.'}</Typography>
          {running?.digests.map(d => <Typography key={d} variant="caption" display="block"><code>{d}</code></Typography>)}
          {value.matches_last_deployment === false && (
            <Alert severity="warning" style={{ marginTop: 8 }}>
              The cluster runs a different image than the last successful deployment ({value.last_deployment?.image_tag}).
            </Alert>
          )}
          <Typography variant="body2" style={{ marginTop: 8 }}>
            Last successful deployment:{' '}
            {value.last_deployment?.at
              ? `${new Date(value.last_deployment.at).toLocaleString()}${value.last_deployment.revision ? ` · Helm revision ${value.last_deployment.revision}` : ''}`
              : 'none recorded'}
          </Typography>
        </InfoCard>
      </Grid>
      <Grid item xs={12} md={6}>
        <InfoCard title="Links">
          {Object.entries(value.links).map(([kind, link]) => (
            <Typography key={kind} variant="body2">
              {LINK_LABELS[kind] ?? kind}:{' '}
              {link.available && link.url ? <Link to={link.url}>{link.url}</Link> : <em>unavailable ({link.reason ?? 'not available'})</em>}
            </Typography>
          ))}
        </InfoCard>
      </Grid>
      <Grid item xs={12} md={6}>
        <Table<Pod>
          title="Pods"
          options={{ search: false, paging: false, padding: 'dense' }}
          columns={[
            { title: 'Pod', field: 'name' },
            { title: 'Ready', render: p => (p.ready ? 'yes' : 'no') },
            { title: 'Restarts', field: 'restarts' },
            { title: 'Reason', render: p => p.reason ?? '' },
          ]}
          data={value.pods ?? []}
          emptyContent={<Box p={2}>No pods observed.</Box>}
        />
      </Grid>
    </Grid>
  );
};
