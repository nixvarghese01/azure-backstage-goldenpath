import { Content, Header, InfoCard, Link, Page } from '@backstage/core-components';
import { configApiRef, identityApiRef, useApi } from '@backstage/core-plugin-api';
import type { RequestView } from '@internal/plugin-idp-platform-common';
import { idpApiRef } from '@internal/plugin-idp-platform';
import { Box, Chip, Grid, makeStyles, Typography, useTheme } from '@material-ui/core';
import AddCircleOutline from '@material-ui/icons/AddCircleOutline';
import AssignmentTurnedIn from '@material-ui/icons/AssignmentTurnedIn';
import Category from '@material-ui/icons/Category';
import BugReport from '@material-ui/icons/BugReport';
import Code from '@material-ui/icons/Code';
import Extension from '@material-ui/icons/Extension';
import GroupAdd from '@material-ui/icons/GroupAdd';
import LibraryBooks from '@material-ui/icons/LibraryBooks';
import React from 'react';
import useAsync from 'react-use/esm/useAsync';

const useStyles = makeStyles(theme => ({
  action: {
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(2),
    padding: theme.spacing(2.5),
    borderRadius: 12,
    border: `1px solid ${theme.palette.border}`,
    background: theme.palette.background.paper,
    color: theme.palette.text.primary,
    textDecoration: 'none',
    transition: 'border-color 120ms ease, transform 120ms ease',
    '&:hover': { borderColor: theme.palette.primary.main, transform: 'translateY(-1px)', textDecoration: 'none' },
  },
  icon: {
    display: 'grid',
    placeItems: 'center',
    width: 40,
    height: 40,
    borderRadius: 10,
    color: theme.palette.primary.main,
    background: theme.palette.type === 'dark' ? 'rgba(139,124,246,0.12)' : 'rgba(91,75,219,0.08)',
  },
  tool: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: theme.spacing(1),
    width: 96,
    color: theme.palette.text.primary,
    '&:hover': { color: theme.palette.primary.main, textDecoration: 'none' },
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: theme.spacing(1.25, 0),
    borderBottom: `1px solid ${theme.palette.border}`,
    '&:last-child': { borderBottom: 'none' },
  },
}));

/** Request state -> chip tone, shared with the status colors of the theme. */
export function stateTone(state: string): 'ok' | 'error' | 'warning' | 'running' | 'aborted' {
  if (state === 'SUCCEEDED') return 'ok';
  if (state === 'FAILED') return 'error';
  if (state === 'AWAITING_APPROVAL') return 'warning';
  if (['CANCELLED', 'CLEANED_UP', 'CLEANUP_PENDING'].includes(state)) return 'aborted';
  return 'running';
}

const StateChip = ({ state }: { state: string }) => {
  const theme = useTheme();
  const color = theme.palette.status[stateTone(state)];
  return (
    <Chip
      size="small"
      variant="outlined"
      label={state.replace(/_/g, ' ').toLowerCase()}
      style={{ textTransform: 'capitalize', color, borderColor: color }}
    />
  );
};

const actions = [
  { to: '/create', title: 'Create a service', text: 'Repository, infrastructure and deployment from one form', icon: AddCircleOutline },
  { to: '/catalog', title: 'Catalog', text: 'Services, teams and their health', icon: Category },
  { to: '/idp/approvals', title: 'Approvals', text: 'Infrastructure plans waiting for review', icon: AssignmentTurnedIn },
  { to: '/docs', title: 'Docs', text: 'Platform guides and each service’s runbook', icon: LibraryBooks },
];

/** Toolkit: the links people need around the portal itself. */
export function toolkit(githubOrg: string, repository: string) {
  const repo = `https://github.com/${githubOrg}/${repository}`;
  return [
    { title: 'Docs', url: '/docs', icon: LibraryBooks },
    { title: 'GitHub', url: repo, icon: Code },
    { title: 'Contributing', url: `${repo}/blob/develop/CONTRIBUTING.md`, icon: GroupAdd },
    { title: 'Plugins Directory', url: 'https://backstage.io/plugins', icon: Extension },
    { title: 'Submit New Issue', url: `${repo}/issues/new/choose`, icon: BugReport },
  ];
}

function greeting(now: Date): string {
  const hour = now.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

const RequestRow = ({ r }: { r: RequestView }) => {
  const classes = useStyles();
  return (
    <div className={classes.row}>
      <Box>
        <Link to={`/catalog/default/component/${r.application_name}/provisioning`}>{r.application_name}</Link>
        <Typography variant="caption" color="textSecondary" display="block">
          {r.environment} · {r.requested_by.replace('user:default/', '')} · {new Date(r.updated_at).toLocaleString()}
        </Typography>
      </Box>
      <StateChip state={r.state} />
    </div>
  );
};

/** Home: what needs attention now, and the shortest way to the common tasks. */
export const HomePage = () => {
  const classes = useStyles();
  const identity = useApi(identityApiRef);
  const config = useApi(configApiRef);
  const links = toolkit(
    config.getOptionalString('idp.githubOrg') ?? 'nixvarghese01',
    config.getOptionalString('idp.platformRepository') ?? 'azure-backstage-goldenpath',
  );
  const idp = useApi(idpApiRef);
  const profile = useAsync(() => identity.getProfileInfo(), [identity]);
  const approvals = useAsync(() => idp.approvals(), [idp]);
  const recent = useAsync(() => idp.recentRequests(), [idp]);
  const name = profile.value?.displayName?.split(' ')[0];

  return (
    <Page themeId="home">
      <Header title={`${greeting(new Date())}${name ? `, ${name}` : ''}`} subtitle="Internal Developer Portal" />
      <Content>
        <Grid container spacing={3}>
          {actions.map(a => (
            <Grid item xs={12} sm={6} lg={3} key={a.to}>
              <Link to={a.to} className={classes.action} underline="none">
                <span className={classes.icon}><a.icon fontSize="small" /></span>
                <Box>
                  <Typography variant="subtitle2">{a.title}</Typography>
                  <Typography variant="caption" color="textSecondary">{a.text}</Typography>
                </Box>
              </Link>
            </Grid>
          ))}
          <Grid item xs={12}>
            <InfoCard title="Toolkit">
              <Box display="flex" flexWrap="wrap" gridGap={24}>
                {links.map(t => (
                  <Link key={t.title} to={t.url} className={classes.tool} underline="none">
                    <span className={classes.icon}><t.icon fontSize="small" /></span>
                    <Typography variant="caption">{t.title}</Typography>
                  </Link>
                ))}
              </Box>
            </InfoCard>
          </Grid>
          <Grid item xs={12} md={5}>
            <InfoCard title="Waiting for approval">
              {approvals.loading && <Typography color="textSecondary">Loading…</Typography>}
              {approvals.error && <Typography color="textSecondary">Unavailable: {approvals.error.message}</Typography>}
              {approvals.value?.length === 0 && <Typography color="textSecondary">Nothing is waiting for you.</Typography>}
              {approvals.value?.map(r => <RequestRow key={r.id} r={r} />)}
              {!!approvals.value?.length && <Box mt={1}><Link to="/idp/approvals">Review in Approvals</Link></Box>}
            </InfoCard>
          </Grid>
          <Grid item xs={12} md={7}>
            <InfoCard title="Recent requests">
              {recent.loading && <Typography color="textSecondary">Loading…</Typography>}
              {recent.error && <Typography color="textSecondary">Unavailable: {recent.error.message}</Typography>}
              {recent.value?.length === 0 && (
                <Typography color="textSecondary">
                  No requests yet. <Link to="/create">Create the first service</Link>.
                </Typography>
              )}
              {recent.value?.slice(0, 8).map(r => <RequestRow key={r.id} r={r} />)}
            </InfoCard>
          </Grid>
        </Grid>
      </Content>
    </Page>
  );
};
