import { coreServices, createBackendModule, type UserInfoService } from '@backstage/backend-plugin-api';
import { AuthorizeResult, type PolicyDecision, isPermission } from '@backstage/plugin-permission-common';
import type { PermissionPolicy, PolicyQuery, PolicyQueryUser } from '@backstage/plugin-permission-node';
import { policyExtensionPoint } from '@backstage/plugin-permission-node/alpha';
import { kubernetesProxyPermission } from '@backstage/plugin-kubernetes-common';
import { idpRequestApprovePermission } from '@internal/plugin-idp-platform-common';

/**
 * Model-project policy: everything is allowed except approving infrastructure changes and the Kubernetes
 * proxy, which require membership of the approver group. The proxy calls the cluster with Backstage's own
 * (read-only) credentials for any path, including pod logs and events, and can't be scoped to an entity. The orchestrator re-checks group membership and separation of
 * duties (approver != requester) on its side.
 */
export class IdpPermissionPolicy implements PermissionPolicy {
  constructor(
    private readonly approverGroup: string,
    private readonly userInfo: UserInfoService,
  ) {}

  async handle(request: PolicyQuery, user?: PolicyQueryUser): Promise<PolicyDecision> {
    if (
      isPermission(request.permission, idpRequestApprovePermission) ||
      isPermission(request.permission, kubernetesProxyPermission)
    ) {
      const groups = user ? (await this.userInfo.getUserInfo(user.credentials)).ownershipEntityRefs : [];
      return { result: groups.includes(this.approverGroup) ? AuthorizeResult.ALLOW : AuthorizeResult.DENY };
    }
    return { result: AuthorizeResult.ALLOW };
  }
}

export const idpPermissionPolicyModule = createBackendModule({
  pluginId: 'permission',
  moduleId: 'idp-policy',
  register(reg) {
    reg.registerInit({
      deps: { policy: policyExtensionPoint, config: coreServices.rootConfig, userInfo: coreServices.userInfo },
      async init({ policy, config, userInfo }) {
        policy.setPolicy(
          new IdpPermissionPolicy(
            config.getOptionalString('idp.approverGroup') ?? 'group:default/platform-approvers',
            userInfo,
          ),
        );
      },
    });
  },
});
