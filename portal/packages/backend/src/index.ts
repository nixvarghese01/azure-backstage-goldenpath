import { createBackend } from '@backstage/backend-defaults';
import { sportifyScaffolderModule } from '@internal/plugin-sportify-platform-backend';
import { sportifyPermissionPolicyModule } from './permissionPolicy';

const backend = createBackend();

// Portal built-ins
backend.add(import('@backstage/plugin-app-backend'));
backend.add(import('@backstage/plugin-auth-backend'));
backend.add(import('@backstage/plugin-auth-backend-module-github-provider'));
// Guest tokens are available only in the explicitly selected local container profile.
if (process.env.SPORTIFY_LOCAL_GUEST_AUTH === 'true') {
  backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));
}
backend.add(import('@backstage/plugin-catalog-backend'));
backend.add(import('@backstage/plugin-catalog-backend-module-scaffolder-entity-model'));
backend.add(import('@backstage/plugin-scaffolder-backend'));
backend.add(import('@backstage/plugin-scaffolder-backend-module-github'));
backend.add(import('@backstage/plugin-techdocs-backend'));
backend.add(import('@backstage/plugin-notifications-backend'));
backend.add(import('@backstage/plugin-signals-backend'));

// Permissions with the Sportify policy (approve permission restricted to platform-approvers)
backend.add(import('@backstage/plugin-permission-backend'));
backend.add(sportifyPermissionPolicyModule);

// Sportify thin bridge + scaffolder actions
backend.add(import('@internal/plugin-sportify-platform-backend'));
backend.add(sportifyScaffolderModule);

backend.start();
