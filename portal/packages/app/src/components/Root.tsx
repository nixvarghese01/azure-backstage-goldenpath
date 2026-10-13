import { Sidebar, SidebarDivider, SidebarItem, SidebarPage, SidebarSpace } from '@backstage/core-components';
import { NotificationsSidebarItem } from '@backstage/plugin-notifications';
import { Settings as SidebarSettings } from '@backstage/plugin-user-settings';
import AddCircleOutline from '@material-ui/icons/AddCircleOutline';
import AssignmentTurnedIn from '@material-ui/icons/AssignmentTurnedIn';
import Category from '@material-ui/icons/Category';
import LibraryBooks from '@material-ui/icons/LibraryBooks';
import React, { type PropsWithChildren } from 'react';

export const Root = ({ children }: PropsWithChildren<{}>) => (
  <SidebarPage>
    <Sidebar>
      <SidebarItem icon={Category} to="catalog" text="Catalog" />
      <SidebarItem icon={AddCircleOutline} to="create" text="Create" />
      <SidebarItem icon={AssignmentTurnedIn} to="sportify/approvals" text="Approvals" />
      <SidebarItem icon={LibraryBooks} to="docs" text="Docs" />
      <SidebarDivider />
      <SidebarSpace />
      <NotificationsSidebarItem />
      <SidebarSettings />
    </Sidebar>
    {children}
  </SidebarPage>
);
