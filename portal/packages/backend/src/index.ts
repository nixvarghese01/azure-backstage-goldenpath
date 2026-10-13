import { createBackend } from '@backstage/backend-defaults';
import { idpScaffolderModule } from '@internal/plugin-idp-platform-backend';
import { idpPermissionPolicyModule } from './permissionPolicy';

const backend = createBackend();

// Portal built-ins
backend.add(import('@backstage/plugin-app-backend'));
backend.add(import('@backstage/plugin-auth-backend'));
backend.add(import('@backstage/plugin-auth-backend-module-github-provider'));
// Guest tokens are available only in the explicitly selected local container profile.
if (process.env.IDP_LOCAL_GUEST_AUTH === 'true') {
  backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));
}
backend.add(import('@backstage/plugin-catalog-backend'));
backend.add(import('@backstage/plugin-catalog-backend-module-scaffolder-entity-model'));
backend.add(import('@backstage/plugin-scaffolder-backend'));
backend.add(import('@backstage/plugin-scaffolder-backend-module-github'));
backend.add(import('@backstage/plugin-techdocs-backend'));
backend.add(import('@backstage/plugin-notifications-backend'));
backend.add(import('@backstage/plugin-signals-backend'));

// Permissions with the IDP policy (approve permission restricted to platform-approvers)
backend.add(import('@backstage/plugin-permission-backend'));
backend.add(idpPermissionPolicyModule);

// IDP thin bridge + scaffolder actions
backend.add(import('@internal/plugin-idp-platform-backend'));
backend.add(idpScaffolderModule);

backend.start();
