import {
  EntityAboutCard,
  EntityLayout,
  EntityLinksCard,
  EntitySwitch,
  isKind,
} from '@backstage/plugin-catalog';
import { EntityMembersListCard, EntityOwnershipCard } from '@backstage/plugin-org';
import { EntityTechdocsContent } from '@backstage/plugin-techdocs';
import { EntitySportifyProvisioningContent } from '@internal/plugin-sportify-platform';
import { Grid } from '@material-ui/core';
import React from 'react';

const componentPage = (
  <EntityLayout>
    <EntityLayout.Route path="/" title="Overview">
      <Grid container spacing={3}>
        <Grid item md={6}>
          <EntityAboutCard variant="gridItem" />
        </Grid>
        <Grid item md={6}>
          <EntityLinksCard />
        </Grid>
      </Grid>
    </EntityLayout.Route>
    <EntityLayout.Route path="/provisioning" title="Provisioning">
      <EntitySportifyProvisioningContent />
    </EntityLayout.Route>
    <EntityLayout.Route path="/docs" title="Docs">
      <EntityTechdocsContent />
    </EntityLayout.Route>
  </EntityLayout>
);

const groupPage = (
  <EntityLayout>
    <EntityLayout.Route path="/" title="Overview">
      <Grid container spacing={3}>
        <Grid item md={6}>
          <EntityOwnershipCard variant="gridItem" />
        </Grid>
        <Grid item md={6}>
          <EntityMembersListCard />
        </Grid>
      </Grid>
    </EntityLayout.Route>
  </EntityLayout>
);

const defaultPage = (
  <EntityLayout>
    <EntityLayout.Route path="/" title="Overview">
      <EntityAboutCard variant="gridItem" />
    </EntityLayout.Route>
  </EntityLayout>
);

export const entityPage = (
  <EntitySwitch>
    <EntitySwitch.Case if={isKind('component')} children={componentPage} />
    <EntitySwitch.Case if={isKind('group')} children={groupPage} />
    <EntitySwitch.Case>{defaultPage}</EntitySwitch.Case>
  </EntitySwitch>
);
