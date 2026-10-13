# Terraform modules

Reusable, versioned modules consumed by the platform stacks (`iac/platform/`) and by generated application repositories (by Git tag, for example `?ref=app-identity/v1.0.0`). See [ADR-0002](../../docs/adr/0002-terraform-structure.md).

| Module | Purpose | Used by |
|---|---|---|
| `naming` | Names and standard tags (no resources) | everything |
| `resource-group` | Resource group with tags | apps (create new), platform |
| `app-identity` | Runtime user-assigned identity + Workload Identity federation | apps |
| `app-namespace` | Namespace, quota, limit range, deployer RoleBinding | apps |
| `storage-account` | Entra-only storage, LRS or ZRS by availability tier | apps (create new) |
| `key-vault` | RBAC-mode vault with purge protection | apps (create new), platform |
| `role-assignment` | Role assignment restricted to an allowlist | apps |
| `aks-cluster` | Shared AKS cluster with Workload Identity and Gateway API | platform |
| `container-registry` | ACR without admin user or anonymous pull | platform |
| `postgresql-flexible` | Entra-only PostgreSQL 17 for platform state | platform |
| `subscription-vending` | Subscription alias (EA/MCA billing only) | platform |
| `github-oidc-identity` | Identity federated to GitHub Actions | platform |

Run module tests with `terraform test` inside a module directory (mock providers, no Azure access needed).

Versioning: tags `<module>/vX.Y.Z`. A breaking change is a major version; generated repositories upgrade through a normal pull request.
