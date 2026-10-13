import { Link, sidebarConfig, useSidebarOpenState } from '@backstage/core-components';
import { makeStyles, Typography } from '@material-ui/core';
import React from 'react';

const useStyles = makeStyles(theme => ({
  root: {
    width: sidebarConfig.drawerWidthClosed,
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
    '&:hover': { textDecoration: 'none', color: theme.palette.navigation.selectedColor },
  },
  title: {
    ...theme.typography.h6,
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
  mark: {
    ...theme.typography.subtitle1,
    fontWeight: theme.typography.fontWeightBold as number,
    letterSpacing: '0.08em',
    color: theme.palette.navigation.selectedColor,
  },
}));

/** Sidebar brand: the portal name with "powered by Backstage", or an "IDP" mark when collapsed. */
export const SidebarLogo = () => {
  const classes = useStyles();
  const { isOpen } = useSidebarOpenState();
  return (
    <div className={classes.root} data-open={isOpen}>
      <Link to="/" underline="none" className={classes.link} aria-label="Internal Developer Portal home">
        {isOpen ? (
          <>
            <Typography component="span" className={classes.title}>
              Internal Developer Portal
            </Typography>
            <Typography component="span" className={classes.subtitle}>
              powered by Backstage
            </Typography>
          </>
        ) : (
          <Typography component="span" className={classes.mark}>
            IDP
          </Typography>
        )}
      </Link>
    </div>
  );
};
