import { type AnyApiFactory, configApiRef, createApiFactory } from '@backstage/core-plugin-api';
import { ScmAuth, ScmIntegrationsApi, scmIntegrationsApiRef } from '@backstage/integration-react';
import { searchApiRef } from '@backstage/plugin-search-react';

export const apis: AnyApiFactory[] = [
  createApiFactory({
    api: scmIntegrationsApiRef,
    deps: { configApi: configApiRef },
    factory: ({ configApi }) => ScmIntegrationsApi.fromConfig(configApi),
  }),
  ScmAuth.createDefaultApiFactory(),
  // The TechDocs reader's "search this site" box needs a search API. The portal has no search backend
  // (one 4-vCPU cluster: no indexer), so it answers with no results instead of breaking the page.
  createApiFactory({
    api: searchApiRef,
    deps: {},
    factory: () => ({ query: async () => ({ results: [], numberOfResults: 0 }) }),
  }),
];
