import { Content, InfoCard, Link, LinkButton, Page } from '@backstage/core-components';
import { configApiRef, identityApiRef, useApi } from '@backstage/core-plugin-api';
import { catalogApiRef } from '@backstage/plugin-catalog-react';
import type { Entity } from '@backstage/catalog-model';
import type { OperationalHealth, RequestView } from '@internal/plugin-idp-platform-common';
import { idpApiRef } from '@internal/plugin-idp-platform';
import { Box, Chip, Grid, makeStyles, Tooltip, Typography, useTheme } from '@material-ui/core';
import AddCircleOutline from '@material-ui/icons/AddCircleOutline';
import AssignmentTurnedIn from '@material-ui/icons/AssignmentTurnedIn';
import BugReport from '@material-ui/icons/BugReport';
import Category from '@material-ui/icons/Category';
import CloudDone from '@material-ui/icons/CloudDone';
import Code from '@material-ui/icons/Code';
import Extension from '@material-ui/icons/Extension';
import GroupAdd from '@material-ui/icons/GroupAdd';
import LibraryBooks from '@material-ui/icons/LibraryBooks';
import PlaylistAddCheck from '@material-ui/icons/PlaylistAddCheck';
import React from 'react';
import useAsync from 'react-use/esm/useAsync';

// ---------------------------------------------------------------------------------------------------
// Pure helpers (tested)
// ---------------------------------------------------------------------------------------------------

type Tone = 'ok' | 'error' | 'warning' | 'running' | 'aborted' | 'pending';

/** Request state -> status color of the theme. */
export function stateTone(state: string): Tone {
  if (state === 'SUCCEEDED') return 'ok';
  if (state === 'FAILED') return 'error';
  if (state === 'AWAITING_APPROVAL') return 'warning';
  if (['CANCELLED', 'CLEANED_UP', 'CLEANUP_PENDING'].includes(state)) return 'aborted';
  return 'running';
}

/** Observed health -> status color; unknown is never green. */
export function healthTone(health?: OperationalHealth): Tone {
  if (health === 'healthy') return 'ok';
  if (health === 'degraded') return 'warning';
  if (health === 'down' || health === 'missing') return 'error';
  if (health === 'stopped' || health === 'removed') return 'aborted';
  return 'pending';
}

/** Requests in the last 7 days and the success rate of the finished ones (null when none finished). */
export function summarize(requests: Pick<RequestView, 'state' | 'created_at'>[], now: Date) {
  const weekAgo = now.getTime() - 7 * 24 * 3600 * 1000;
  const lastWeek = requests.filter(r => new Date(r.created_at).getTime() >= weekAgo).length;
  const finished = requests.filter(r => ['SUCCEEDED', 'FAILED'].includes(r.state));
  const succeeded = finished.filter(r => r.state === 'SUCCEEDED').length;
  return { lastWeek, successRate: finished.length ? Math.round((100 * succeeded) / finished.length) : null };
}

/** "5 min ago", "3 h ago", "2 d ago". */
export function relativeTime(iso: string, now: Date): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
}

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

// ---------------------------------------------------------------------------------------------------
// Styles. Every tile is border-box and fills its grid column, so nothing makes the page wider than the
// window (which scrolled the content under the fixed sidebar).
// ---------------------------------------------------------------------------------------------------

const useStyles = makeStyles(theme => {
  const tint = theme.palette.type === 'dark' ? 'rgba(139,124,246,0.12)' : 'rgba(91,75,219,0.08)';
  const tile = {
    boxSizing: 'border-box' as const,
    height: '100%',
    borderRadius: 12,
    border: `1px solid ${theme.palette.border}`,
    background: theme.palette.background.paper,
  };
  return {
    hero: {
      boxSizing: 'border-box',
      borderRadius: 16,
      padding: theme.spacing(4),
      color: '#fff',
      background: 'linear-gradient(120deg, #4F46E5 0%, #7C3AED 45%, #0891B2 100%)',
      position: 'relative',
      overflow: 'hidden',
      '&::after': {
        content: '""',
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(600px 200px at 90% 0%, rgba(255,255,255,0.25), transparent 70%)',
        pointerEvents: 'none',
      },
    },
    heroTitle: { fontWeight: 700, letterSpacing: '-0.02em', fontSize: 30, lineHeight: 1.2 },
    heroText: { opacity: 0.9, marginTop: theme.spacing(1), maxWidth: 640 },
    heroActions: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: theme.spacing(1.5),
      marginTop: theme.spacing(3),
      position: 'relative',
      zIndex: 1,
    },
    heroPrimary: { background: '#fff', color: '#4338CA', '&:hover': { background: '#EEF2FF' } },
    heroSecondary: {
      color: '#fff',
      borderColor: 'rgba(255,255,255,0.6)',
      '&:hover': { borderColor: '#fff', background: 'rgba(255,255,255,0.1)' },
    },
    stat: { ...tile, padding: theme.spacing(2.5) },
    statValue: { fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1 },
    statLabel: { color: theme.palette.text.secondary, marginTop: theme.spacing(0.5) },
    action: {
      ...tile,
      width: '100%',
      minWidth: 0,
      display: 'flex',
      alignItems: 'center',
      gap: theme.spacing(2),
      padding: theme.spacing(2.5),
      color: theme.palette.text.primary,
      textDecoration: 'none',
      transition: 'border-color 120ms ease, transform 120ms ease',
      '&:hover': { borderColor: theme.palette.primary.main, transform: 'translateY(-1px)', textDecoration: 'none' },
    },
    minWidth0: { minWidth: 0 },
    icon: {
      flexShrink: 0,
      display: 'grid',
      placeItems: 'center',
      width: 40,
      height: 40,
      borderRadius: 10,
      color: theme.palette.primary.main,
      background: tint,
    },
    step: { ...tile, padding: theme.spacing(2), display: 'flex', gap: theme.spacing(1.5), alignItems: 'flex-start' },
    stepNumber: {
      flexShrink: 0,
      display: 'grid',
      placeItems: 'center',
      width: 28,
      height: 28,
      borderRadius: 999,
      fontWeight: 700,
      fontSize: 13,
      color: theme.palette.primary.main,
      background: tint,
    },
    tool: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: theme.spacing(1),
      width: 88,
      textAlign: 'center',
      color: theme.palette.text.primary,
      '&:hover': { color: theme.palette.primary.main, textDecoration: 'none' },
    },
    row: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: theme.spacing(2),
      padding: theme.spacing(1.25, 0),
      borderBottom: `1px solid ${theme.palette.border}`,
      '&:last-child': { borderBottom: 'none' },
    },
    dot: { display: 'inline-block', flexShrink: 0, width: 10, height: 10, borderRadius: 999 },
  };
});

// ---------------------------------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------------------------------

const StateChip = ({ state }: { state: string }) => {
  const theme = useTheme();
  const color = theme.palette.status[stateTone(state)];
  return (
    <Chip
      size="small"
      variant="outlined"
      label={state.replace(/_/g, ' ').toLowerCase()}
      style={{ textTransform: 'capitalize', color, borderColor: color, flexShrink: 0 }}
    />
  );
};

const Stat = ({ value, label, hint }: { value: React.ReactNode; label: string; hint?: string }) => {
  const classes = useStyles();
  return (
    <div className={classes.stat}>
      <div className={classes.statValue}>{value}</div>
      <Typography variant="body2" className={classes.statLabel}>{label}</Typography>
      {hint && <Typography variant="caption" color="textSecondary">{hint}</Typography>}
    </div>
  );
};

const steps = [
  { title: 'Request', text: 'One form: stack, Azure resources and availability.' },
  { title: 'Approve', text: 'Reviewers approve the exact Terraform plan.' },
  { title: 'Provision', text: 'Infrastructure, repository and pipelines are created.' },
  { title: 'Run', text: 'Built, scanned and deployed; health stays visible.' },
];

const actions = [
  { to: '/create', title: 'Create a service', text: 'Repository, infrastructure and deployment', icon: AddCircleOutline },
  { to: '/catalog', title: 'Catalog', text: 'Services, teams and APIs', icon: Category },
  { to: '/idp/approvals', title: 'Approvals', text: 'Plans waiting for review', icon: AssignmentTurnedIn },
  { to: '/docs', title: 'Docs', text: 'Guides and each service’s runbook', icon: LibraryBooks },
];

type ServiceHealth = { entity: Entity; health?: OperationalHealth; summary?: string };

/** The user's services (by ownership), or the newest components when they own none; with live health. */
function useServices() {
  const catalog = useApi(catalogApiRef);
  const identity = useApi(identityApiRef);
  const idp = useApi(idpApiRef);
  return useAsync(async (): Promise<{ mine: boolean; services: ServiceHealth[] }> => {
    const { ownershipEntityRefs } = await identity.getBackstageIdentity();
    const fields = ['kind', 'metadata.name', 'metadata.namespace', 'metadata.description', 'spec.owner', 'metadata.annotations'];
    let { items } = await catalog.getEntities({
      filter: { kind: 'Component', 'relations.ownedBy': ownershipEntityRefs },
      fields,
    });
    const mine = items.length > 0;
    if (!mine) items = (await catalog.getEntities({ filter: { kind: 'Component' }, fields })).items;
    // Health only for services the platform created; the orchestrator caches each cluster read.
    const services = await Promise.all(
      items.slice(0, 6).map(async (entity): Promise<ServiceHealth> => {
        if (!entity.metadata.annotations?.['idp.io/request-id']) return { entity };
        try {
          const [request] = await idp.requestsFor(entity.metadata.name);
          if (!request) return { entity };
          const ops = await idp.operations(request.id);
          return { entity, health: ops.health, summary: ops.summary };
        } catch {
          return { entity, health: 'unknown', summary: 'Health unavailable' };
        }
      }),
    );
    return { mine, services };
  }, [catalog, identity, idp]);
}

// ---------------------------------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------------------------------

/** Home: the platform at a glance, what needs attention now, and the shortest way to common tasks. */
export const HomePage = () => {
  const classes = useStyles();
  const theme = useTheme();
  const identity = useApi(identityApiRef);
  const config = useApi(configApiRef);
  const idp = useApi(idpApiRef);
  const catalog = useApi(catalogApiRef);
  const now = new Date();

  const profile = useAsync(() => identity.getProfileInfo(), [identity]);
  const approvals = useAsync(() => idp.approvals(), [idp]);
  const recent = useAsync(() => idp.recentRequests(), [idp]);
  const components = useAsync(() => catalog.queryEntities({ filter: { kind: 'Component' }, limit: 1 }), [catalog]);
  const services = useServices();

  const name = profile.value?.displayName?.split(' ')[0];
  const stats = recent.value ? summarize(recent.value, now) : undefined;
  const links = toolkit(
    config.getOptionalString('idp.githubOrg') ?? 'nixvarghese01',
    config.getOptionalString('idp.platformRepository') ?? 'azure-backstage-goldenpath',
  );
  const dash = '–';
  let successRate: string = dash;
  if (stats && stats.successRate !== null) successRate = `${stats.successRate}%`;

  return (
    <Page themeId="home">
      <Content>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <div className={classes.hero}>
              <Typography className={classes.heroTitle}>
                {greeting(now)}{name ? `, ${name}` : ''}
              </Typography>
              <Typography className={classes.heroText}>
                From one form to a running service on AKS: a repository, Azure infrastructure behind an approved
                plan, CI/CD and live health, all in one place.
              </Typography>
              <div className={classes.heroActions}>
                <LinkButton
                  variant="contained"
                  className={classes.heroPrimary}
                  to="/create"
                  startIcon={<AddCircleOutline />}
                >
                  Create a service
                </LinkButton>
                <LinkButton variant="outlined" className={classes.heroSecondary} to="/catalog">
                  Browse the catalog
                </LinkButton>
              </div>
            </div>
          </Grid>

          <Grid item xs={6} md={3}>
            <Stat value={components.value?.totalItems ?? dash} label="Services in the catalog" />
          </Grid>
          <Grid item xs={6} md={3}>
            <Stat value={stats?.lastWeek ?? dash} label="Requests in the last 7 days" />
          </Grid>
          <Grid item xs={6} md={3}>
            <Stat value={successRate} label="Success rate" hint="Of finished requests" />
          </Grid>
          <Grid item xs={6} md={3}>
            <Stat value={approvals.value?.length ?? dash} label="Waiting for approval" />
          </Grid>

          {actions.map(a => (
            <Grid item xs={12} sm={6} lg={3} key={a.to}>
              <Link to={a.to} className={classes.action} underline="none">
                <span className={classes.icon}><a.icon fontSize="small" /></span>
                <Box className={classes.minWidth0}>
                  <Typography variant="subtitle2">{a.title}</Typography>
                  <Typography variant="caption" color="textSecondary">{a.text}</Typography>
                </Box>
              </Link>
            </Grid>
          ))}

          <Grid item xs={12} md={7}>
            <InfoCard
              title={services.value?.mine ? 'Your services' : 'Services'}
              subheader="Live health from the cluster"
            >
              {services.loading && <Typography color="textSecondary">Loading…</Typography>}
              {services.error && <Typography color="textSecondary">Unavailable: {services.error.message}</Typography>}
              {services.value?.services.length === 0 && (
                <Typography color="textSecondary">
                  No services yet. <Link to="/create">Create the first one</Link>.
                </Typography>
              )}
              {services.value?.services.map(({ entity, health, summary }) => (
                <div className={classes.row} key={entity.metadata.name}>
                  <Box display="flex" alignItems="center" gridGap={12} className={classes.minWidth0}>
                    <Tooltip title={summary ?? 'Not created by the platform: no health data'}>
                      <span className={classes.dot} style={{ background: theme.palette.status[healthTone(health)] }} />
                    </Tooltip>
                    <Box className={classes.minWidth0}>
                      <Link
                        to={`/catalog/${entity.metadata.namespace ?? 'default'}/component/${entity.metadata.name}/operations`}
                      >
                        {entity.metadata.name}
                      </Link>
                      <Typography variant="caption" color="textSecondary" display="block" noWrap>
                        {entity.metadata.description ?? String(entity.spec?.owner ?? '')}
                      </Typography>
                    </Box>
                  </Box>
                  <Typography variant="caption" color="textSecondary">
                    {health ? health.replace('_', ' ') : 'no data'}
                  </Typography>
                </div>
              ))}
            </InfoCard>
          </Grid>

          <Grid item xs={12} md={5}>
            <InfoCard title="Waiting for approval">
              {approvals.loading && <Typography color="textSecondary">Loading…</Typography>}
              {approvals.error && <Typography color="textSecondary">Unavailable: {approvals.error.message}</Typography>}
              {approvals.value?.length === 0 && (
                <Box display="flex" alignItems="center" gridGap={8}>
                  <PlaylistAddCheck style={{ color: theme.palette.status.ok }} />
                  <Typography color="textSecondary">Nothing is waiting for you.</Typography>
                </Box>
              )}
              {approvals.value?.map(r => (
                <div className={classes.row} key={r.id}>
                  <Box className={classes.minWidth0}>
                    <Link to="/idp/approvals">{r.application_name}</Link>
                    <Typography variant="caption" color="textSecondary" display="block">
                      {r.environment} · {r.requested_by.replace('user:default/', '')} · {relativeTime(r.updated_at, now)}
                    </Typography>
                  </Box>
                  <StateChip state={r.state} />
                </div>
              ))}
            </InfoCard>
          </Grid>

          <Grid item xs={12}>
            <Typography variant="h6" style={{ marginBottom: theme.spacing(1.5) }}>
              How the golden path works
            </Typography>
            <Grid container spacing={2}>
              {steps.map((s, i) => (
                <Grid item xs={12} sm={6} md={3} key={s.title}>
                  <div className={classes.step}>
                    <span className={classes.stepNumber}>{i + 1}</span>
                    <Box className={classes.minWidth0}>
                      <Typography variant="subtitle2">{s.title}</Typography>
                      <Typography variant="caption" color="textSecondary">{s.text}</Typography>
                    </Box>
                  </div>
                </Grid>
              ))}
            </Grid>
          </Grid>

          <Grid item xs={12} md={7}>
            <InfoCard title="Recent activity">
              {recent.loading && <Typography color="textSecondary">Loading…</Typography>}
              {recent.error && <Typography color="textSecondary">Unavailable: {recent.error.message}</Typography>}
              {recent.value?.length === 0 && (
                <Box display="flex" alignItems="center" gridGap={8}>
                  <CloudDone style={{ color: theme.palette.text.secondary }} />
                  <Typography color="textSecondary">
                    No requests yet. <Link to="/create">Create the first service</Link>.
                  </Typography>
                </Box>
              )}
              {recent.value?.slice(0, 8).map(r => (
                <div className={classes.row} key={r.id}>
                  <Box className={classes.minWidth0}>
                    <Link to={`/catalog/default/component/${r.application_name}/provisioning`}>{r.application_name}</Link>
                    <Typography variant="caption" color="textSecondary" display="block" noWrap>
                      {r.environment} · {r.requested_by.replace('user:default/', '')} · {relativeTime(r.updated_at, now)}
                    </Typography>
                  </Box>
                  <StateChip state={r.state} />
                </div>
              ))}
            </InfoCard>
          </Grid>

          <Grid item xs={12} md={5}>
            <InfoCard title="Toolkit">
              <Box display="flex" flexWrap="wrap" gridGap={16}>
                {links.map(t => (
                  <Link key={t.title} to={t.url} className={classes.tool} underline="none">
                    <span className={classes.icon}><t.icon fontSize="small" /></span>
                    <Typography variant="caption">{t.title}</Typography>
                  </Link>
                ))}
              </Box>
            </InfoCard>
          </Grid>
        </Grid>
      </Content>
    </Page>
  );
};
