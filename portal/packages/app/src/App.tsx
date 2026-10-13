import { createApp } from '@backstage/app-defaults';
import { AppRouter, FlatRoutes } from '@backstage/core-app-api';
import { AlertDisplay, OAuthRequestDialog, SignInPage } from '@backstage/core-components';
import { githubAuthApiRef } from '@backstage/core-plugin-api';
import { CatalogEntityPage, CatalogIndexPage, catalogPlugin } from '@backstage/plugin-catalog';
import { NotificationsPage } from '@backstage/plugin-notifications';
import { ScaffolderPage, scaffolderPlugin } from '@backstage/plugin-scaffolder';
import { ScaffolderFieldExtensions } from '@backstage/plugin-scaffolder-react';
import { SignalsDisplay } from '@backstage/plugin-signals';
import { TechDocsIndexPage, TechDocsReaderPage, techdocsPlugin } from '@backstage/plugin-techdocs';
import { UserSettingsPage } from '@backstage/plugin-user-settings';
import {
  SportifyApprovalsPage,
  SportifyAvailabilityPickerExtension,
  SportifyAzureResourcePickerExtension,
  SportifyStackPickerExtension,
} from '@internal/plugin-sportify-platform';
import React from 'react';
import { Navigate, Route } from 'react-router-dom';
import { apis } from './apis';
import { entityPage } from './components/catalog/EntityPage';
import { Root } from './components/Root';

const app = createApp({
  apis,
  bindRoutes({ bind }) {
    bind(catalogPlugin.externalRoutes, { createComponent: scaffolderPlugin.routes.root });
    bind(scaffolderPlugin.externalRoutes, { registerComponent: catalogPlugin.routes.catalogIndex });
  },
  components: {
    SignInPage: props => (
      <SignInPage
        {...props}
        auto
        provider={{ id: 'github-auth-provider', title: 'GitHub', message: 'Sign in with GitHub', apiRef: githubAuthApiRef }}
      />
    ),
  },
});

const routes = (
  <FlatRoutes>
    <Route path="/" element={<Navigate to="catalog" />} />
    <Route path="/catalog" element={<CatalogIndexPage />} />
    <Route path="/catalog/:namespace/:kind/:name" element={<CatalogEntityPage />}>
      {entityPage}
    </Route>
    <Route path="/create" element={<ScaffolderPage />}>
      <ScaffolderFieldExtensions>
        <SportifyAzureResourcePickerExtension />
        <SportifyAvailabilityPickerExtension />
        <SportifyStackPickerExtension />
      </ScaffolderFieldExtensions>
    </Route>
    <Route path="/docs" element={<TechDocsIndexPage />} />
    <Route path="/docs/:namespace/:kind/:name/*" element={<TechDocsReaderPage />} />
    <Route path="/sportify/approvals" element={<SportifyApprovalsPage />} />
    <Route path="/notifications" element={<NotificationsPage />} />
    <Route path="/settings" element={<UserSettingsPage />} />
  </FlatRoutes>
);

export default app.createRoot(
  <>
    <AlertDisplay />
    <OAuthRequestDialog />
    <SignalsDisplay />
    <AppRouter>
      <Root>{routes}</Root>
    </AppRouter>
  </>,
);

// Referenced so the plugin is registered even if no route uses it directly.
void techdocsPlugin;
