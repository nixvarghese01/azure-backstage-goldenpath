import { coreServices, createBackendPlugin } from '@backstage/backend-plugin-api';
import { createRouter } from './router';

/** Bridge plugin: /api/sportify/* -> azure-discovery and provisioning-orchestrator. */
export const sportifyPlatformPlugin = createBackendPlugin({
  pluginId: 'sportify',
  register(env) {
    env.registerInit({
      deps: {
        config: coreServices.rootConfig,
        logger: coreServices.logger,
        httpRouter: coreServices.httpRouter,
        httpAuth: coreServices.httpAuth,
        userInfo: coreServices.userInfo,
        permissions: coreServices.permissions,
      },
      async init({ config, logger, httpRouter, httpAuth, userInfo, permissions }) {
        httpRouter.use(await createRouter({ config, logger, httpAuth, userInfo, permissions }));
      },
    });
  },
});
