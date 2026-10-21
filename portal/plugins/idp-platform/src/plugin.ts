import {
  createApiFactory,
  createComponentExtension,
  createPlugin,
  createRoutableExtension,
  createRouteRef,
  discoveryApiRef,
  fetchApiRef,
} from '@backstage/core-plugin-api';
import { createScaffolderFieldExtension } from '@backstage/plugin-scaffolder-react';
import { IdpClient, idpApiRef } from './api';
import { AvailabilityPicker, validateAvailability } from './components/AvailabilityPicker';
import { AzureResourcePicker, validateInfrastructure } from './components/AzureResourcePicker';
import { EndpointHostPicker, validateEndpointHost } from './components/EndpointHostPicker';
import { GithubAccess, validateGithubAccess } from './components/GithubAccess';
import { StackPicker } from './components/StackPicker';

export const approvalsRouteRef = createRouteRef({ id: 'idp-approvals' });

export const idpPlugin = createPlugin({
  id: 'idp',
  apis: [
    createApiFactory({
      api: idpApiRef,
      deps: { discoveryApi: discoveryApiRef, fetchApi: fetchApiRef },
      factory: deps => new IdpClient(deps),
    }),
  ],
  routes: { approvals: approvalsRouteRef },
});

export const IdpApprovalsPage = idpPlugin.provide(
  createRoutableExtension({
    name: 'IdpApprovalsPage',
    component: () => import('./components/ApprovalsPage').then(m => m.ApprovalsPage),
    mountPoint: approvalsRouteRef,
  }),
);

export const EntityIdpProvisioningContent = idpPlugin.provide(
  createComponentExtension({
    name: 'EntityIdpProvisioningContent',
    component: { lazy: () => import('./components/ProvisioningContent').then(m => m.ProvisioningContent) },
  }),
);

export const EntityIdpOperationsContent = idpPlugin.provide(
  createComponentExtension({
    name: 'EntityIdpOperationsContent',
    component: { lazy: () => import('./components/OperationsContent').then(m => m.OperationsContent) },
  }),
);

export const IdpAzureResourcePickerExtension = idpPlugin.provide(
  createScaffolderFieldExtension({
    name: 'IdpAzureResourcePicker',
    component: AzureResourcePicker,
    validation: validateInfrastructure,
  }),
);

export const IdpAvailabilityPickerExtension = idpPlugin.provide(
  createScaffolderFieldExtension({
    name: 'IdpAvailabilityPicker',
    component: AvailabilityPicker,
    validation: validateAvailability,
  }),
);

export const IdpStackPickerExtension = idpPlugin.provide(
  createScaffolderFieldExtension({
    name: 'IdpStackPicker',
    component: StackPicker,
  }),
);

export const IdpEndpointHostPickerExtension = idpPlugin.provide(
  createScaffolderFieldExtension({
    name: 'IdpEndpointHostPicker',
    component: EndpointHostPicker,
    validation: validateEndpointHost,
  }),
);

export const IdpGithubAccessExtension = idpPlugin.provide(
  createScaffolderFieldExtension({
    name: 'IdpGithubAccess',
    component: GithubAccess,
    validation: validateGithubAccess,
  }),
);
