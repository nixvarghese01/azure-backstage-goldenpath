import { Link, sidebarConfig, useSidebarOpenState } from '@backstage/core-components';
import { makeStyles, Typography } from '@material-ui/core';
import React from 'react';

const useStyles = makeStyles(theme => ({
  root: {
    boxSizing: 'border-box',
    width: sidebarConfig.drawerWidthClosed,
    overflow: 'hidden',
    gap: theme.spacing(1.5),
    height: 3 * sidebarConfig.logoHeight,
    display: 'flex',
    alignItems: 'center',
    marginBottom: -14,
    paddingLeft: theme.spacing(3),
    '&[data-open="true"]': { width: sidebarConfig.drawerWidthOpen },
  },
  link: {
    color: theme.palette.navigation.color,
    textDecoration: 'none',
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(1.5),
    '&:hover': { textDecoration: 'none', color: theme.palette.navigation.selectedColor },
  },
  title: {
    ...theme.typography.subtitle1,
    display: 'block',
    whiteSpace: 'nowrap',
    fontWeight: theme.typography.fontWeightBold as number,
    lineHeight: 1.2,
    letterSpacing: '0.01em',
    color: theme.palette.navigation.selectedColor,
  },
  subtitle: {
    ...theme.typography.caption,
    display: 'block',
    marginTop: theme.spacing(0.5),
    letterSpacing: '0.04em',
    opacity: 0.75,
  },
}));

/** The portal's mark: a rounded tile with the accent gradient and a stylised path (the golden path). */
const Mark = () => (
  <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" style={{ flexShrink: 0 }}>
    <defs>
      <linearGradient id="idp-mark" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#8B7CF6" />
        <stop offset="1" stopColor="#22D3EE" />
      </linearGradient>
    </defs>
    <rect width="28" height="28" rx="8" fill="url(#idp-mark)" />
    <path d="M8 19c3-0 3-10 6-10s3 10 6 10" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
);

/** Sidebar brand: the mark with the portal name and "powered by Backstage"; the mark alone when collapsed. */
export const SidebarLogo = () => {
  const classes = useStyles();
  const { isOpen } = useSidebarOpenState();
  return (
    <div className={classes.root} data-open={isOpen}>
      <Link to="/" underline="none" className={classes.link} aria-label="Internal Developer Portal home">
        <Mark />
        {isOpen ? (
          <span>
            <Typography component="span" className={classes.title}>
              Developer Portal
            </Typography>
            <Typography component="span" className={classes.subtitle}>
              powered by Backstage
            </Typography>
          </span>
        ) : null}
      </Link>
    </div>
  );
};
