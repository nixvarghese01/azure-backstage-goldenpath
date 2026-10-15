# Platform bootstrap: steps outside the pipeline

Everything below was done **once, from an admin's machine**, before the pipelines could run. After it,
infrastructure changes go only through GitHub Actions (`platform-plan`, `platform-provision`,
`platform-release`, `platform-ttl`). Each step says what it created, why it can't be a pipeline step,
and how to undo it.

First run: 2026-10-14/15, `dev` environment, Azure Free Trial (spending limit on), region
`swedencentral`. Subscription and tenant IDs are deliberately not recorded here (public repository);
they are in the git-ignored `terraform.tfvars` files and in GitHub **secrets** (masked in logs).

## Why these steps are outside the pipeline

The pipelines sign in to Azure with OIDC identities and keep Terraform state in a storage account.
Both have to exist before the first pipeline run, and creating identities, role definitions and Entra
app registrations needs rights that no pipeline identity is given. This is the usual bootstrap
boundary; see [terraform-state.md](terraform-state.md) for the state side.

## Steps

| # | Step | How | Created or changed | Can a pipeline do it later? |
|---|---|---|---|---|
| 1 | Sign in to Azure | `az login --tenant <tenant id>` in a private browser window | Local CLI session only | — |
| 2 | Preflight (read-only) | `scripts/bootstrap-platform.sh preflight --location swedencentral` | Nothing | — |
| 3 | Resource providers and the `EncryptionAtHost` feature | `scripts/bootstrap-platform.sh providers` | Subscription registrations (free) | No: subscription-wide setting |
| 4 | AKS admin group | `az ad group create --display-name idp-aks-admins-dev` and `az ad group member add` (yourself) | Entra group `idp-aks-admins-dev` with one member | No: Entra directory change |
| 5 | Stack inputs | Copied `terraform.tfvars.example` to `terraform.tfvars` in `10-identities` and `20-shared-dev`; set subscription, GitHub owner ID, region, globally unique names (`…nv01`), the admin group ID | Local, git-ignored files | They become the `PLATFORM_TFVARS_JSON` variable in step 8 |
| 6 | Terraform state (`00-bootstrap`) | `scripts/bootstrap-platform.sh state --location swedencentral` | `rg-idp-tfstate-dev`, storage `stidptfstatedevnv01` (containers `platform`, `apps`, `CanNotDelete` lock); your user gets **Storage Blob Data Contributor** on it; the stack's own state migrated into it | No: the pipeline keeps its state here |
| 7 | Identities (`10-identities`) | `scripts/bootstrap-platform.sh identities --location swedencentral` | 51 resources: see below | Later changes, yes (through `platform-apply`), except role definitions and app registrations |
| 7b | OIDC subject format | `terraform apply` of `10-identities` after setting `github_repo_id` | The 5 platform federated credentials now trust `repo:<owner>@<owner id>/<repo>@<repo id>:environment:<env>`, GitHub's immutable subject (the repository has `use_immutable_subject`). A re-created repository with the same name can't use them | Yes, later changes go through `platform-apply` |
| 7c | AKS admin group for the pipeline | `terraform apply` of `10-identities` (`azuread_group.aks_platform_admins`), then its ID added to `admin_group_object_ids` in `20-shared-dev` | Entra group `idp-aks-platform-dev` whose only member is the `platform` identity. The clusters use Kubernetes RBAC with Entra ID, so cluster-admin comes only from these groups; without it `30-cluster-config` can't list CRDs or create the Gateway | Membership changes, yes (through `platform-apply`); creating Entra groups needs an admin |
| 7d | Workload Identity federation rights | `terraform apply` of `10-identities` | Custom role `IDP Workload Identity Federation (dev)` (read identities; read/write/delete federated credentials only), assigned to the `platform` identity on the backstage, discovery and orchestrator identities. `30-cluster-config` creates their federated credentials, which need the cluster's OIDC issuer | No: role definitions need an admin |
| 7e | Identity for the dev in-cluster PostgreSQL | `terraform apply` of `10-identities` | `id-idp-postgres-dev` (Workload Identity), and the federation-only role on it for the `platform` identity. Per-secret Key Vault access for it follows `secrets_created = true` ([ADR-0009](../adr/0009-dev-in-cluster-postgres.md)) | Later changes, yes |
| 8 | GitHub settings | `scripts/bootstrap-platform.sh github --location swedencentral --base-domain <gateway-ip>.nip.io` | 12 repository secrets, 5 variables and 4 environments (`platform-plan` open to pull requests) | No: needs a repository admin |

### Step 7 in detail (`10-identities`, 51 resources)

| What | Names | Notes |
|---|---|---|
| Resource groups | `rg-idp-identities-dev`, `rg-idp-aks-dev`, `rg-idp-registry-dev`, `rg-idp-data-dev`, `rg-idp-network-dev`, `rg-idp-apps-dev` | Tagged for the landing zone policy (`workload`, `environment`, `owner`, CAF tags). The five workload groups are empty until `platform-provision` |
| Pipeline identities (OIDC) | `id-idp-platform-dev`, `id-idp-platform-plan-dev`, `id-idp-platform-deploy-dev`, `id-idp-vending-dev`, `id-idp-provisioning-dev`, `id-idp-deployment-dev` | 9 federated credentials, each bound to one GitHub environment. No secrets |
| Service identities | `id-idp-backstage-dev`, `id-idp-discovery-dev`, `id-idp-orchestrator-dev` | Workload Identity for the pods |
| Platform Key Vault | `kv-idp-plat-dev-nv01` | RBAC mode, purge protection. Secret **values** are not set yet |
| Entra app registrations | `idp-backstage-dev`, `idp-discovery-dev`, `idp-orchestrator-dev` (+ service principals) | Token audiences for service-to-service calls |
| Custom role | `IDP App Provisioner (dev)` | Created here because pipeline identities can't write role definitions |
| Role assignments | `platform`: Contributor + RBAC Administrator on the five workload groups, Reader on the subscription. `platform-plan`, `discovery`: Reader. `provisioning`: App Provisioner + RBAC Administrator (ABAC-limited) on `rg-idp-apps-dev`. State: per-container blob roles | **No identity can write outside the IDP's groups**: other workloads on the subscription are out of reach |

### Step 8 in detail (GitHub)

- **Secrets** (identifiers and configuration; GitHub masks them in logs, which are public for a public
  repository): `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, the client IDs (`PLATFORM_CLIENT_ID`,
  `PLATFORM_PLAN_CLIENT_ID`, `PLATFORM_DEPLOY_CLIENT_ID`, `VENDING_CLIENT_ID`, `BACKSTAGE_CLIENT_ID`,
  `DISCOVERY_CLIENT_ID`, `ORCHESTRATOR_CLIENT_ID`), `PLATFORM_BACKEND_HCL`, `PLATFORM_TFVARS_JSON`,
  `PLATFORM_CHART_VALUES_JSON`. Nothing is hardcoded in the repository.
- **Variables** (plain names and switches): `ACR_NAME`, `AKS_NAME`, `AKS_RESOURCE_GROUP`,
  `PLATFORM_AZURE_READY` (`true` once the secrets exist; job conditions can't read secrets).
- **Environments** (deployments only from `develop` and `main`): `platform` and `platform-deploy`
  (you approve each run), `platform-plan` (read-only), `platform-teardown` (destroy only, no approval,
  so the time-to-live teardown never waits).

## What the landing zone required

The subscription carries a landing zone policy (`xycorp-baseline`, from another workload). It was
**not changed**; the IDP was made to comply:

| Policy | IDP response |
|---|---|
| Allowed locations: `swedencentral` | Deployed there; `Standard_B2s_v2` nodes (the B-series offered in that region) |
| Resource groups need `workload`, `environment`, `owner` tags | All IDP groups carry them, plus `costCenter`, `criticality`, `dataClassification` |
| Storage shared keys, Key Vault RBAC, PaaS public access (audit) | Already compliant: Entra-only storage, RBAC vault |

## Still to do outside the pipeline

| Step | When | How |
|---|---|---|
| Register the GitHub Apps (Backstage, orchestrator) | Before sign-in and repository creation work in Backstage | Issue #19 |
| Set Key Vault secret values (GitHub App keys, webhook secret) | After the GitHub Apps exist | `scripts/create-platform-secrets.sh`, then `secrets_created = true` in `10-identities` |
| Map service identities to PostgreSQL roles | Once, after the first `platform-provision` creates PostgreSQL | `scripts/postgres-grant-identities.sql` |

## Undo

Run `platform-provision` with `action: teardown` first (it removes what the pipeline created). Then, in
reverse order of the steps above: delete the GitHub environments and variables; `terraform destroy`
in `10-identities`; delete the Entra group; and last, `00-bootstrap` as described in
[cleanup.md](cleanup.md) (export what you need, lift the delete lock, migrate state back to local,
destroy). Provider and feature registrations can stay; they cost nothing.
