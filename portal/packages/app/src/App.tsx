import { createApp } from '@backstage/app-defaults';
import { AppRouter, FlatRoutes } from '@backstage/core-app-api';
import { AlertDisplay, OAuthRequestDialog, SignInPage } from '@backstage/core-components';
import { type SignInPageProps, configApiRef, githubAuthApiRef, useApi } from '@backstage/core-plugin-api';
import { CatalogEntityPage, CatalogIndexPage, catalogPlugin } from '@backstage/plugin-catalog';
import { NotificationsPage } from '@backstage/plugin-notifications';
import { ScaffolderPage, scaffolderPlugin } from '@backstage/plugin-scaffolder';
import { ScaffolderFieldExtensions } from '@backstage/plugin-scaffolder-react';
import { SignalsDisplay } from '@backstage/plugin-signals';
import { TechDocsIndexPage, TechDocsReaderPage, techdocsPlugin } from '@backstage/plugin-techdocs';
import { UserSettingsPage } from '@backstage/plugin-user-settings';
import { UnifiedThemeProvider } from '@backstage/theme';
import DarkIcon from '@material-ui/icons/Brightness2';
import LightIcon from '@material-ui/icons/WbSunny';
import {
  IdpApprovalsPage,
  IdpAvailabilityPickerExtension,
  IdpAzureResourcePickerExtension,
  IdpStackPickerExtension,
  IdpEndpointHostPickerExtension,
  IdpGithubAccessExtension,
} from '@internal/plugin-idp-platform';
import React from 'react';
import { Route } from 'react-router-dom';
import { apis } from './apis';
import { entityPage } from './components/catalog/EntityPage';
import { HomePage } from './components/home/HomePage';
import { Root } from './components/Root';
import { darkTheme, lightTheme } from './theme/theme';

function PlatformSignInPage(props: SignInPageProps) {
  const config = useApi(configApiRef);
  if (config.getString('auth.environment') === 'local-docker') {
    return <SignInPage {...props} providers={['guest']} title="powered by Backstage" align="center" />;
  }
  return (
    <SignInPage {...props} auto
      provider={{ id: 'github-auth-provider', title: 'GitHub', message: 'Sign in with GitHub', apiRef: githubAuthApiRef }}
    />
  );
}

const app = createApp({
  apis,
  bindRoutes({ bind }) {
    bind(catalogPlugin.externalRoutes, { createComponent: scaffolderPlugin.routes.root });
    bind(scaffolderPlugin.externalRoutes, { registerComponent: catalogPlugin.routes.catalogIndex });
  },
  components: {
    SignInPage: PlatformSignInPage,
  },
  // Dark first: it is the default unless the browser asks for light.
  themes: [
    {
      id: 'idp-dark',
      title: 'Dark',
      variant: 'dark',
      icon: <DarkIcon />,
      Provider: ({ children }) => <UnifiedThemeProvider theme={darkTheme} children={children} />,
    },
    {
      id: 'idp-light',
      title: 'Light',
      variant: 'light',
      icon: <LightIcon />,
      Provider: ({ children }) => <UnifiedThemeProvider theme={lightTheme} children={children} />,
    },
  ],
});

const routes = (
  <FlatRoutes>
    <Route path="/" element={<HomePage />} />
    <Route path="/catalog" element={<CatalogIndexPage />} />
    <Route path="/catalog/:namespace/:kind/:name" element={<CatalogEntityPage />}>
      {entityPage}
    </Route>
    <Route path="/create" element={<ScaffolderPage />}>
      <ScaffolderFieldExtensions>
        <IdpAzureResourcePickerExtension />
        <IdpAvailabilityPickerExtension />
        <IdpStackPickerExtension />
        <IdpEndpointHostPickerExtension />
        <IdpGithubAccessExtension />
      </ScaffolderFieldExtensions>
    </Route>
    <Route path="/docs" element={<TechDocsIndexPage />} />
    <Route path="/docs/:namespace/:kind/:name/*" element={<TechDocsReaderPage />} />
    <Route path="/idp/approvals" element={<IdpApprovalsPage />} />
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
