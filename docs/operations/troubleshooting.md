# Troubleshooting

Start with the request's **Provisioning** tab in Backstage. It shows the failed stage, the message, the workflow run link, and the resources that exist. Then use the table for that stage. Once the cause is fixed, **Retry** continues the request from the step that failed; **Clean up** removes what was created instead.

## By stage

| Symptom | Likely cause | Fix |
|---|---|---|
| Form: "Select existing unavailable: nothing approved was found" | Discovery identity lacks `Reader`, or the resource isn't in `policies/allowlist.yaml` | Check the `Reader` assignment (stack 10) and the allowlist entry (name, subscription, environment) |
| Form: "Create new unavailable: …" | Capability check (billing type, vCPU quota, policy switch) | Read the reason; request quota, or choose Select existing |
| Submit fails: `not_owner_member` | The user isn't in the owning group in the catalog | Fix group membership in `portal/catalog/org.yaml` (or your org provider) |
| Submit fails: `duplicate_application` | An active request exists for the same app and environment | Finish, cancel or clean up the existing request |
| Stuck in `PLATFORM_PROVISIONING` | Platform PR not reviewed or merged, or `platform-apply` waiting for reviewers | Review the PR linked on the Provisioning tab; approve the `platform` environment |
| `REPOSITORY_CREATED` then `FAILED` at `validate` | `terraform fmt`/`validate`, TFLint, Checkov, Helm or gitleaks failed | Open the run, fix in a PR to the app repo |
| `FAILED` at `plan` | Azure login (federated credential subject), plan policy violation, missing state access | Check the subject matches ADR-0005, the org OIDC customisation and environment names; read the Conftest output |
| `INFRASTRUCTURE_PLANNED` never becomes `AWAITING_APPROVAL` | `deployment_protection_rule` webhook not received | Check App #2 webhook deliveries; confirm the rule is attached to `<env>-infra`; the reconcile poll fails stale requests after 6h |
| Approve fails: `plan_changed` | A newer plan exists | Review the new plan and approve that one |
| Approve fails: `separation_of_duties` | The requester tried to approve | Another approver must approve |
| `FAILED` at `apply` with `created_resources` | Partial apply | Fix the cause, then **Retry** (a new plan, approved again), or use **Clean up** |
| `FAILED` at `open_app_pr` (`HTTPStatusError: 403` on `git/trees`) | The orchestrator GitHub App lacks **Workflows: write**, or the account hasn't accepted it on the installation | Grant it in the App's permissions, accept it under Settings → Installations, then **Retry** |
| Stuck in `APPLICATION_BUILDING` | App PR checks failing, or not mergeable (branch protection) | Open the PR; the orchestrator merges when checks pass |
| `FAILED` at `ci` | Tests, Trivy (CRITICAL), gitleaks, or ACR push | Open the run; for push, check the `<env>-build` environment and AcrPush |
| `FAILED` at `deploy` | Rollout timeout, failing probes, Gateway/route, Workload Identity | The error says which check failed and what was restored, as the cluster confirms it: Helm `--atomic` for a failed upgrade, or a verified rollback to the recorded revision for a failed readiness or smoke check (a first install is left for diagnosis). Download the run's `deploy-diagnostics` artifact (Helm history, events, logs), then `kubectl describe pod` and check `/health/ready` |
| `/health/ready` reports storage `HTTP 403` | Role assignment not yet propagated, or wrong identity client ID in the ServiceAccount | Wait a few minutes; compare the annotation with `terraform output identity_client_id` |

## Platform services

| Symptom | Check |
|---|---|
| Discovery `/readyz` 503 | Workload Identity federation (stack 30), `azure.workload.identity/use` label, `Reader` assignment |
| Orchestrator `/readyz` 503 | PostgreSQL reachability and the Entra login role (`scripts/postgres-grant-identities.sql`) |
| Orchestrator can't read GitHub App key | Key Vault per-secret assignment (`secrets_created = true`), SecretProviderClass, CSI driver pods |
| Backstage → services 401/403 | Audience/scope config (`service_auth` output of stack 10) and `IDP_ALLOWED_CALLERS` |
| Notifications not arriving | Outbox backlog (`outbox_messages` with `last_error`), Backstage `externalAccess` JWKS config |

## Platform provisioning (bootstrap and `platform-provision`)

Found during the first real provisioning on an Azure Free Trial inside a CAF landing zone. Each row
names the fix that is now in the code, so a recurrence points at configuration rather than design.

| Symptom | Cause | Fix |
|---|---|---|
| `az login` device code: `AADSTS530035` "blocked by security defaults" | Security defaults block the device-code flow | Interactive sign-in for the tenant: `az login --tenant <id>` (a private window helps when another account is signed in) |
| Bootstrap `state`: `RequestDisallowedByPolicy` on the resource group | Landing zone policy: allowed locations, required tags | Deploy in the allowed region; the stacks set CAF tags (`workload`, `environment`, `owner`, ...). [bootstrap-record.md](bootstrap-record.md#what-the-landing-zone-required) |
| Bootstrap on Windows: `MissingSubscription`, 403 on state migration, empty `PLATFORM_TFVARS_JSON` | Git Bash path conversion; Windows Python can't open `/e/...` or `/tmp` | Fixed in `bootstrap-platform.sh` (`MSYS_NO_PATHCONV`, `cygpath`, values through the environment, empty values refused) |
| Pipeline `azure/login`: `AADSTS700213` "No matching federated identity record" | The repository sends GitHub's immutable subject `repo:<owner>@<id>/<repo>@<id>:environment:<env>` | Set `github_repo_id` in `10-identities` and apply |
| Checkov plan gate fails on AKS with waivers already in the module | Enrichment matched `azurerm_kubernetes_cluster.this` to a data source of the same name in another stack | `--repo-root-for-plan-enrichment` is `iac/modules` |
| AKS create: VM scale set `RequestDisallowedByPolicy` | "Require a tag on resources": the scale set takes the node pool's tags | `default_node_pool.tags` set |
| PostgreSQL: `RegionalAllocationFailed` | The zone Azure picked had no capacity for the size | Pin another zone: `postgres = { zone = "2" }` in `20-shared-dev` |
| A plan proposes removing `web_app_routing` from AKS | App Routing is enabled through `azapi_update_resource` | The cluster ignores `web_app_routing` |
| `30-cluster-config`: `cannot list customresourcedefinitions` | Kubernetes RBAC with Entra ID: only `admin_group_object_ids` are cluster-admin | `idp-aks-platform-<env>` group (platform identity) in `admin_group_object_ids` |
| `30-cluster-config`: 403 writing federated identity credentials | The platform identity is Reader on the identities group | Custom role *IDP Workload Identity Federation* on the three service identities |
| Release: `cannot delete resource jobs` (orchestrator migration hook) | `platform-deploy` had only the application deployer role | Namespaced `platform-jobs` role in `idp-platform` |
| Gateway has no address; `istiod` and `nginx` pods `Pending` | One 2-vCPU node: AKS add-ons already request ~1.5 vCPU, the ingress add-ons ~2 vCPU more | Free regional vCPU quota for a second node, or a leaner dev profile; see [demo-environment.md](demo-environment.md) |
| Gateway `Programmed=False`, `AddressNotAssigned`; gateway pods `FailedCreate` "violates PodSecurity restricted" | AKS App Routing's managed `istio-proxy` sets no seccomp profile | `idp-gateway` enforces `baseline` and warns/audits `restricted` (`30-cluster-config`) |
| Volume claim `Pending`; `ProvisioningFailed ... RequestDisallowedByPolicy` (StatefulSet `Ready: 0/1`) | The disk CSI driver creates untagged disks; the landing zone requires tags on every resource | Storage class `managed-csi-tagged` (`30-cluster-config`) tags each disk; use it for platform and app volumes. Delete the stuck claim before retrying |
| First orchestrator install: migration Job `FailedCreate ... error looking up service account` | The migration is a pre-install hook and ran before the chart's ServiceAccount existed | ServiceAccount and SecretProviderClass are earlier hooks (weight -5) |
| Backstage / orchestrator pods can't start | Key Vault has no GitHub App secrets yet; PostgreSQL roles not created | GitHub Apps (#19), `scripts/create-platform-secrets.sh`, then `postgres-grant-identities.sql` |

## Useful queries (orchestrator database)

```sql
SELECT id, application_name, state, error->>'message' FROM requests ORDER BY created_at DESC LIMIT 20;
SELECT kind, status, attempts, last_error FROM steps WHERE request_id = '<id>' ORDER BY id;
SELECT at, actor, action, details FROM audit_events WHERE request_id = '<id>' ORDER BY id;
SELECT event_type, error FROM inbox_events WHERE error IS NOT NULL ORDER BY id DESC LIMIT 20;
```
