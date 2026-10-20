import { InfoCard, Link, Progress, StatusError, StatusOK, StatusPending, StatusAborted, Table } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import { useEntity } from '@backstage/plugin-catalog-react';
import type { RequestView } from '@internal/plugin-idp-platform-common';
import { Box, Button, Chip, Grid, Typography } from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React, { useState } from 'react';
import useAsyncRetry from 'react-use/esm/useAsyncRetry';
import useInterval from 'react-use/esm/useInterval';
import { idpApiRef } from '../api';

const STATUS = {
  succeeded: <StatusOK />,
  failed: <StatusError />,
  pending: <StatusPending />,
  skipped: <StatusAborted />,
};

const URL_LABELS: Record<string, string> = {
  application: 'Application endpoint',
  api_docs: 'API docs (Swagger)',
  health: 'Health',
  repository: 'Repository',
  workflow_runs: 'Workflow runs',
  application_pr: 'Application pull request',
  platform_pr: 'Platform pull request',
  image: 'Container image',
  azure_resource_group: 'Azure resource group',
  backstage: 'Backstage entity',
};

/** How far a plan is through its environment's distinct approvals, while more are needed. */
export function approvalProgress(approval?: RequestView['approval']): string | undefined {
  if (!approval || approval.decision !== 'pending' || !approval.required) return undefined;
  const approvals = approval.approvals ?? [];
  const who = approvals.map(a => a.by).join(', ');
  return `${approvals.length} of ${approval.required} approvals${who ? ` (${who})` : ''}`;
}

/** What a cleanup is doing, by the orchestrator's cleanup stage. */
export function cleanupMessage(stage?: string): { severity: 'info' | 'warning' | 'error'; text: string } {
  switch (stage) {
    case 'awaiting_approval':
      return { severity: 'warning', text: 'The destroy plan is waiting for approval in Backstage (IDP → Approvals).' };
    case 'rejected':
      return { severity: 'warning', text: 'The destroy was rejected; the resources are kept.' };
    case 'uninstalling':
      return { severity: 'info', text: 'Uninstalling the application from the cluster.' };
    case 'uninstalled':
    case 'planning_destroy':
      return { severity: 'info', text: 'Planning the destroy of the infrastructure.' };
    case 'destroy_planned':
      return { severity: 'info', text: 'Destroy planned; GitHub holds it until it is approved.' };
    case 'destroying':
      return { severity: 'info', text: 'Approved: destroying the infrastructure.' };
    default:
      return stage?.endsWith('_failed')
        ? { severity: 'error', text: `Cleanup failed at ${stage.replace(/_failed$/, '')}; open the workflow run, then Retry clean up.` }
        : { severity: 'info', text: 'Cleaning up.' };
  }
}

/** Provisioning tab: separate outcomes, current state, shared URLs, diagnostics and run history. */
export const ProvisioningContent = () => {
  const { entity } = useEntity();
  const api = useApi(idpApiRef);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const { value, loading, error, retry } = useAsyncRetry(
    async () => (await api.requestsFor(entity.metadata.name))[0] as RequestView | undefined,
    [api, entity.metadata.name],
  );
  const active = value && !['SUCCEEDED', 'FAILED', 'CANCELLED', 'CLEANED_UP'].includes(value.state);
  useInterval(retry, active ? 10_000 : null);

  if (loading && !value) return <Progress />;
  if (error) return <Alert severity="error">{error.message}</Alert>;
  if (!value) return <Alert severity="info">No platform request found for this component.</Alert>;

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(undefined);
    try {
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      retry();
    }
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <InfoCard title="Status" subheader={`Request ${value.id}`}>
          <Box display="flex" alignItems="center" mb={2} gridGap={8}>
            <Chip label={value.state} color={value.state === 'FAILED' ? 'secondary' : 'primary'} />
            {value.availability?.tier === 'ha' && <Chip label="HA" variant="outlined" />}
          </Box>
          {value.outcomes.map(o => (
            <Box key={o.name} display="flex" alignItems="center" gridGap={8}>
              {STATUS[o.status]} <Typography>{o.name}</Typography>
            </Box>
          ))}
          {value.plan?.summary && (
            <Typography variant="body2" style={{ marginTop: 16 }}>
              {value.plan.mode === 'destroy' ? 'Destroy plan' : 'Plan'} {value.plan.hash?.slice(0, 12)}: +{value.plan.summary.add ?? 0} ~{value.plan.summary.change ?? 0} -{value.plan.summary.destroy ?? 0}
              {value.approval?.by && value.approval.decision !== 'pending' && ` · ${value.approval.decision} by ${value.approval.by}`}
            </Typography>
          )}
          {value.state === 'AWAITING_APPROVAL' && (
            <Alert severity="warning" style={{ marginTop: 16 }}>
              Waiting for approval in Backstage (IDP → Approvals).
              {approvalProgress(value.approval) && ` ${approvalProgress(value.approval)}.`}
            </Alert>
          )}
          {value.state === 'CLEANUP_PENDING' && (
            <Alert severity={cleanupMessage(value.cleanup?.stage).severity} style={{ marginTop: 16 }}>
              {cleanupMessage(value.cleanup?.stage).text}
              {value.cleanup?.stage === 'awaiting_approval' && <> <Link to="/idp/approvals">Open Approvals</Link></>}
            </Alert>
          )}
          {actionError && <Alert severity="error" style={{ marginTop: 16 }}>{actionError}</Alert>}
          <Box mt={2} display="flex" gridGap={8}>
            {['REQUESTED', 'VALIDATING', 'PLATFORM_PROVISIONING', 'REPOSITORY_CREATED', 'INFRASTRUCTURE_PLANNED', 'AWAITING_APPROVAL'].includes(value.state) && (
              <Button variant="outlined" disabled={busy} onClick={() => act(() => api.cancel(value.id))}>Cancel</Button>
            )}
            {value.state === 'FAILED' && (
              <Button variant="contained" color="primary" disabled={busy} onClick={() => act(() => api.retry(value.id))}>
                Retry
              </Button>
            )}
            {['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(value.state) && (
              <Button variant="outlined" color="secondary" disabled={busy} onClick={() => act(() => api.cleanup(value.id))}>
                Clean up
              </Button>
            )}
            {value.state === 'CLEANUP_PENDING' && value.cleanup?.stage?.endsWith('_failed') && (
              <Button variant="outlined" color="secondary" disabled={busy} onClick={() => act(() => api.cleanup(value.id))}>
                Retry clean up
              </Button>
            )}
          </Box>
        </InfoCard>
      </Grid>

      <Grid item xs={12} md={6}>
        <InfoCard title="URLs">
          {Object.entries(value.urls).map(([k, url]) => (
            <Box key={k} mb={1}>
              <Typography variant="caption">{URL_LABELS[k] ?? k}</Typography>
              <Typography>{url.startsWith('http') ? <Link to={url}>{url}</Link> : url}</Typography>
            </Box>
          ))}
        </InfoCard>
      </Grid>

      {value.state === 'FAILED' && (
        <Grid item xs={12}>
          <Alert severity="error">
            <Typography variant="subtitle2">Failed at {value.error.stage}</Typography>
            <Typography>{value.error.message}</Typography>
            {value.error.run_url && <Link to={value.error.run_url}>Open the workflow run</Link>}
            {value.error.diagnostics && (
              <Typography variant="body2">Diagnostics: the run's <code>{value.error.diagnostics}</code> artifact.</Typography>
            )}
            <Typography variant="body2">Fix the cause, then Retry: it continues from this step.</Typography>
            {!!value.error.created?.length && (
              <Typography variant="body2">Resources that exist: {value.error.created.join(', ')}. Use Clean up to remove them.</Typography>
            )}
            {(value.validation.errors ?? []).map(e => <Typography key={e.code + e.field}>• {e.field}: {e.message}</Typography>)}
          </Alert>
        </Grid>
      )}

      <Grid item xs={12}>
        <Table
          title="Workflow history"
          options={{ search: false, paging: false, padding: 'dense' }}
          data={[...value.runs].reverse()}
          columns={[
            { title: 'When', field: 'at' },
            { title: 'Stage', field: 'stage' },
            { title: 'Status', field: 'status' },
            { title: 'Run', render: r => (r.url ? <Link to={r.url}>open</Link> : '') },
          ]}
        />
      </Grid>
    </Grid>
  );
};
