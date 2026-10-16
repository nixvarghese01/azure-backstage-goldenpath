import { coreServices, createBackendModule } from '@backstage/backend-plugin-api';
import { ScmIntegrations } from '@backstage/integration';
import { scaffolderActionsExtensionPoint } from '@backstage/plugin-scaffolder-node';
import { PlatformClient } from './client';
import { createRepositoryCreatedAction } from './actions/repositoryCreated';
import { createSubmitAction } from './actions/submit';
import { createWorkflowRefsAction } from './actions/workflowRefs';

/** Scaffolder module adding the IDP actions. */
export const idpScaffolderModule = createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'idp-actions',
  register(env) {
    env.registerInit({
      deps: {
        scaffolder: scaffolderActionsExtensionPoint,
        config: coreServices.rootConfig,
      },
      async init({ scaffolder, config }) {
        const client = PlatformClient.fromConfig(config);
        const integrations = ScmIntegrations.fromConfig(config);
        scaffolder.addActions(
          createSubmitAction({ client, config }),
          createRepositoryCreatedAction({ client, config, integrations }),
          createWorkflowRefsAction({ config }),
        );
      },
    });
  },
});
