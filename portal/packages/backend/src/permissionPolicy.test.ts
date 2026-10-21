import { mockCredentials, mockServices } from '@backstage/backend-test-utils';
import { kubernetesProxyPermission, kubernetesResourcesReadPermission } from '@backstage/plugin-kubernetes-common';
import { AuthorizeResult } from '@backstage/plugin-permission-common';
import { idpRequestApprovePermission } from '@internal/plugin-idp-platform-common';
import { IdpPermissionPolicy } from './permissionPolicy';

const APPROVERS = 'group:default/platform-approvers';

function policyFor(groups: string[]) {
  const userInfo = mockServices.userInfo.mock({
    getUserInfo: async () => ({ userEntityRef: 'user:default/alex', ownershipEntityRefs: groups }),
  });
  return new IdpPermissionPolicy(APPROVERS, userInfo);
}

const user = { credentials: mockCredentials.user('user:default/alex') } as any;

describe('IdpPermissionPolicy', () => {
  it('lets only approvers use the Kubernetes proxy (logs, events, any path)', async () => {
    const query = { permission: kubernetesProxyPermission };
    expect((await policyFor(['group:default/team-orders']).handle(query, user)).result).toBe(AuthorizeResult.DENY);
    expect((await policyFor([APPROVERS]).handle(query, user)).result).toBe(AuthorizeResult.ALLOW);
  });

  it('lets everyone signed in see workloads', async () => {
    const query = { permission: kubernetesResourcesReadPermission };
    expect((await policyFor([]).handle(query, user)).result).toBe(AuthorizeResult.ALLOW);
  });

  it('keeps approving infrastructure to approvers', async () => {
    const query = { permission: idpRequestApprovePermission };
    expect((await policyFor([]).handle(query, user)).result).toBe(AuthorizeResult.DENY);
  });
});
