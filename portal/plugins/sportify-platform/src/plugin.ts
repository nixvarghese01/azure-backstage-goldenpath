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
import { SportifyClient, sportifyApiRef } from './api';
import { AvailabilityPicker, validateAvailability } from './components/AvailabilityPicker';
import { AzureResourcePicker, validateInfrastructure } from './components/AzureResourcePicker';
import { EndpointHostPicker, validateEndpointHost } from './components/EndpointHostPicker';
import { StackPicker } from './components/StackPicker';

export const approvalsRouteRef = createRouteRef({ id: 'sportify-approvals' });

export const sportifyPlugin = createPlugin({
  id: 'sportify',
  apis: [
    createApiFactory({
      api: sportifyApiRef,
      deps: { discoveryApi: discoveryApiRef, fetchApi: fetchApiRef },
      factory: deps => new SportifyClient(deps),
    }),
  ],
  routes: { approvals: approvalsRouteRef },
});

export const SportifyApprovalsPage = sportifyPlugin.provide(
  createRoutableExtension({
    name: 'SportifyApprovalsPage',
    component: () => import('./components/ApprovalsPage').then(m => m.ApprovalsPage),
    mountPoint: approvalsRouteRef,
  }),
);

export const EntitySportifyProvisioningContent = sportifyPlugin.provide(
  createComponentExtension({
    name: 'EntitySportifyProvisioningContent',
    component: { lazy: () => import('./components/ProvisioningContent').then(m => m.ProvisioningContent) },
  }),
);

export const SportifyAzureResourcePickerExtension = sportifyPlugin.provide(
  createScaffolderFieldExtension({
    name: 'SportifyAzureResourcePicker',
    component: AzureResourcePicker,
    validation: validateInfrastructure,
  }),
);

export const SportifyAvailabilityPickerExtension = sportifyPlugin.provide(
  createScaffolderFieldExtension({
    name: 'SportifyAvailabilityPicker',
    component: AvailabilityPicker,
    validation: validateAvailability,
  }),
);

export const SportifyStackPickerExtension = sportifyPlugin.provide(
  createScaffolderFieldExtension({
    name: 'SportifyStackPicker',
    component: StackPicker,
  }),
);

export const SportifyEndpointHostPickerExtension = sportifyPlugin.provide(
  createScaffolderFieldExtension({
    name: 'SportifyEndpointHostPicker',
    component: EndpointHostPicker,
    validation: validateEndpointHost,
  }),
);
