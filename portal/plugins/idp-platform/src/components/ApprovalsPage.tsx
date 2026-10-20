import { Content, Header, InfoCard, Page, Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { RequestView } from '@internal/plugin-idp-platform-common';
import { Box, Button, Chip, Grid, List, ListItem, TextField, Typography } from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React, { useState } from 'react';
import useAsyncRetry from 'react-use/esm/useAsyncRetry';
import { idpApiRef } from '../api';
import { approvalProgress } from './ProvisioningContent';

const ApprovalCard = ({ request, onDone }: { request: RequestView; onDone: () => void }) => {
  const api = useApi(idpApiRef);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const summary = request.plan.summary ?? {};
  const destroy = request.plan.mode === 'destroy';

  const decide = async (decision: 'approve' | 'reject') => {
    setBusy(true);
    setError(undefined);
    try {
      await api.decide(request.id, decision, request.plan.hash ?? '', comment);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <InfoCard
      title={`${destroy ? 'Destroy: ' : ''}${request.application_name} (${request.environment})`}
      subheader={`Requested by ${request.requested_by} · ${new Date(request.created_at).toLocaleString()}`}
    >
      <Box display="flex" gridGap={8} mb={2}>
        <Chip label={`Plan ${request.plan.hash?.slice(0, 12)}`} />
        <Chip label={`+${summary.add ?? 0} ~${summary.change ?? 0} -${summary.destroy ?? 0}`} color={summary.destroy ? 'secondary' : 'default'} />
        {summary.reused ? <Chip label={`${summary.reused} reused`} variant="outlined" /> : null}
        {request.availability?.tier === 'ha' && <Chip label="HA" color="primary" />}
        {approvalProgress(request.approval) && <Chip label={approvalProgress(request.approval)} variant="outlined" />}
      </Box>

      {request.availability?.tier === 'ha' && (
        <Alert severity="info">
          High availability requested ({request.availability.reason}, SLO {request.availability.slo_target ?? 'n/a'}):{' '}
          {request.availability.justification}
        </Alert>
      )}
      {(request.validation.warnings ?? []).map(w => (
        <Alert key={w.code} severity="warning">{w.message}</Alert>
      ))}

      <Typography variant="subtitle2" style={{ marginTop: 16 }}>Changes</Typography>
      <List dense>
        {(summary.resources ?? []).map(r => (
          <ListItem key={r.address}>
            <code>{r.actions.join(',')}</code>&nbsp;{r.address}
          </ListItem>
        ))}
      </List>
      <Typography variant="body2">
        {destroy ? 'Destroy plan: removes what is listed above; policy checks passed in the plan run.' : 'Policy checks and security scans passed in the plan run.'}{' '}
        {request.urls.workflow_runs && <a href={request.urls.workflow_runs} target="_blank" rel="noreferrer">View runs</a>}
      </Typography>

      <TextField fullWidth multiline minRows={2} label="Comment" value={comment} onChange={e => setComment(e.target.value)}
        inputProps={{ maxLength: 1000 }} style={{ marginTop: 16 }} />
      {error && <Alert severity="error">{error}</Alert>}
      <Box mt={2} display="flex" justifyContent="flex-end" gridGap={8}>
        <Button variant="outlined" disabled={busy} onClick={() => decide('reject')}>Reject</Button>
        <Button variant="contained" color="primary" disabled={busy || !request.plan.hash} onClick={() => decide('approve')}>Approve</Button>
      </Box>
    </InfoCard>
  );
};

/** IDP → Approvals: approve or reject infrastructure plans. GitHub enforces the decision. */
export const ApprovalsPage = () => {
  const api = useApi(idpApiRef);
  const { value, loading, error, retry } = useAsyncRetry(() => api.approvals(), [api]);

  return (
    <Page themeId="tool">
      <Header title="Approvals" subtitle="Infrastructure changes waiting for your decision" />
      <Content>
        {loading && <Progress />}
        {error && <Alert severity="error">{error.message}</Alert>}
        {value && value.length === 0 && <Alert severity="success">Nothing is waiting for approval.</Alert>}
        <Grid container spacing={3}>
          {(value ?? []).map(r => (
            <Grid item xs={12} lg={6} key={r.id}>
              <ApprovalCard request={r} onDone={retry} />
            </Grid>
          ))}
        </Grid>
      </Content>
    </Page>
  );
};
