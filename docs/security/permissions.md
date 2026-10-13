# Permissions per identity

The exact access each identity has, as implemented in `iac/platform/10-identities`, `20-shared-dev` and `30-cluster-config`, and in the GitHub App registrations. Nothing else holds Azure or GitHub rights.

## Azure and Kubernetes

| Identity | Used by | Azure RBAC | Kubernetes RBAC | Trusted credential |
|---|---|---|---|---|
| `id-sportify-platform-<env>` | `platform-apply.yml` (stacks 20, 30) | **Contributor** + **RBAC Administrator** on the subscription; Blob Data Contributor on the `platform` state container | Cluster admin through the AKS admin group (break-glass only) | `repo:<org>/azure-backstage-goldenpath:environment:platform` (required reviewers) |
| `id-sportify-platform-plan-<env>` | `platform-plan.yml` | **Reader** on the subscription; Blob Data Reader on the `platform` state container | — | `…:environment:platform-plan` |
| `id-sportify-platform-deploy-<env>` | `platform-release.yml` | AcrPush on the registries; AKS Cluster User | `sportify-app-deployer` in `sportify-platform` only | `…:environment:platform-deploy` |
| `id-sportify-vending-<env>` | `platform-apply.yml` (stack 05) | Subscription creator on the EA/MCA billing scope (granted by the billing admin); Blob Data Contributor on `platform` state | — | `…:environment:platform-vending` |
| `id-sportify-provisioning-<env>` | `reusable-terraform.yml` (generated repos) | **Sportify App Provisioner** (custom: resource groups, identities and federated credentials, Storage, Key Vault, `*/read`; no key listing) + **RBAC Administrator** limited by ABAC to Storage Blob Data Contributor/Reader and Key Vault Secrets User; Blob Data Contributor on the `apps` state container; AKS Cluster User | `sportify-namespace-provisioner` (namespaces, quotas, limit ranges, role bindings; may bind only `sportify-app-deployer`) | `repository_owner_id:<id>:environment:<env>-infra[-plan]:job_workflow_ref:…/reusable-terraform.yml@<ref>` |
| `id-sportify-deployment-<env>` | `reusable-application-ci.yml` (push), `reusable-application-deploy.yml` | AcrPush; AKS Cluster User | `sportify-app-deployer` in each application namespace (no Secrets) | `…:environment:<env>-build` and `…:environment:<env>` with the matching `job_workflow_ref` |
| `id-sportify-discovery-<env>` | `azure-discovery` pods | **Reader** on allowlisted subscriptions | — | Workload Identity: `system:serviceaccount:sportify-platform:azure-discovery` |
| `id-sportify-orchestrator-<env>` | orchestrator API, worker, migration job | None on Azure resources; Key Vault Secrets User on its 2 secrets; PostgreSQL role for database `orchestrator` | — | Workload Identity: `…:sportify-platform:provisioning-orchestrator` |
| `id-sportify-backstage-<env>` | Backstage pods | None on Azure resources; Key Vault Secrets User on its 3 secrets; PostgreSQL role for database `backstage` | — | Workload Identity: `…:sportify-platform:backstage` |
| `id-<app>-<env>` (one per application) | Application pods | Storage Blob Data Contributor **or** Key Vault Secrets User on its chosen resource only | — | Workload Identity: `…:<namespace>:<app>` |
| AKS kubelet identity | Image pulls | AcrPull on the shared registry | — | Managed by AKS |

## Service-to-service tokens

| Caller → callee | Audience (Entra app registration) | Callee accepts |
|---|---|---|
| Backstage → discovery / orchestrator | `api://sportify-discovery-<env>` / `api://sportify-orchestrator-<env>` | `SPORTIFY_ALLOWED_CALLERS` = Backstage identity object ID (+ orchestrator for discovery) |
| Orchestrator worker → discovery | `api://sportify-discovery-<env>` | as above |
| Orchestrator worker → Backstage notifications | `api://sportify-backstage-<env>` | `backend.auth.externalAccess` (JWKS), restricted to the `notifications` plugin |
| Orchestrator worker → Backstage catalog cleanup | `api://sportify-backstage-<env>` | The same JWKS entry grants `catalog.entity.read` and `catalog.entity.delete` for unregistering cleaned-up applications |
| GitHub Actions → orchestrator callbacks | GitHub OIDC, audience `sportify-orchestrator` | Repository and owner claims must match the request; the callback run ID must match the token's run ID |
| GitHub → orchestrator webhooks | HMAC-SHA256 with the App webhook secret | Signature, with dual-secret rotation |

## GitHub Apps

| App | Installed on | Repository permissions | Events |
|---|---|---|---|
| **#1 Backstage** | Organisation (all repos) | Administration: write (create repos and environments), Contents: write, Metadata: read, Variables: write (repo variables), Environments: write; Members: read (org) | — |
| **#2 Orchestrator** | Organisation (generated repos + platform repo) | Actions: write, Deployments: write (custom protection rules), Contents: write, Pull requests: write, Metadata: read | `workflow_run`, `deployment_protection_rule`, `deployment_status`, `pull_request` |

GitHub App #2 must be enabled as a **custom deployment protection rule** integration for the organisation.

## Notes

- The platform identity is the most privileged. It is usable only from `platform-apply.yml` on `main`, behind the `platform` environment's required reviewers.
- The provisioning identity's subscription-level scope is broader than a single resource group, because "Create new resource group" can't be pre-scoped. Plan policies, the resource-type allowlist and approval in Backstage compensate ([ADR-0005](../adr/0005-reusable-workflows-and-ci-identity.md) §5). Production should add Azure Policy assignments (allowed locations, SKUs, required tags).
- Initial bootstrap (stacks 00 and 10, Entra app registrations, Key Vault secrets) is done once by a human admin with temporary elevated rights.
