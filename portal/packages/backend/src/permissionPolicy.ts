import { coreServices, createBackendModule } from '@backstage/backend-plugin-api';
import type { BackstageIdentityResponse } from '@backstage/plugin-auth-node';
import { AuthorizeResult, type PolicyDecision, isPermission } from '@backstage/plugin-permission-common';
import type { PermissionPolicy, PolicyQuery } from '@backstage/plugin-permission-node';
import { policyExtensionPoint } from '@backstage/plugin-permission-node/alpha';
import { sportifyRequestApprovePermission } from '@internal/plugin-sportify-platform-common';

/**
 * Model-project policy: everything is allowed except approving infrastructure changes, which requires
 * membership of the approver group. The orchestrator re-checks group membership and separation of
 * duties (approver != requester) on its side.
 */
class SportifyPermissionPolicy implements PermissionPolicy {
  constructor(private readonly approverGroup: string) {}

  async handle(request: PolicyQuery, user?: BackstageIdentityResponse): Promise<PolicyDecision> {
    if (isPermission(request.permission, sportifyRequestApprovePermission)) {
      const groups = user?.identity.ownershipEntityRefs ?? [];
      return { result: groups.includes(this.approverGroup) ? AuthorizeResult.ALLOW : AuthorizeResult.DENY };
    }
    return { result: AuthorizeResult.ALLOW };
  }
}

export const sportifyPermissionPolicyModule = createBackendModule({
  pluginId: 'permission',
  moduleId: 'sportify-policy',
  register(reg) {
    reg.registerInit({
      deps: { policy: policyExtensionPoint, config: coreServices.rootConfig },
      async init({ policy, config }) {
        policy.setPolicy(
          new SportifyPermissionPolicy(
            config.getOptionalString('sportify.approverGroup') ?? 'group:default/platform-approvers',
          ),
        );
      },
    });
  },
});
