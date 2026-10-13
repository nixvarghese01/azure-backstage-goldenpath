# Troubleshooting

Start with the request's **Provisioning** tab in Backstage. It shows the failed stage, the message, the workflow run link, and the resources that exist. Then use the table for that stage.

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
| `FAILED` at `apply` with `created_resources` | Partial apply | Fix the cause and re-run via a new plan, or use **Clean up** |
| Stuck in `APPLICATION_BUILDING` | App PR checks failing, or not mergeable (branch protection) | Open the PR; the orchestrator merges when checks pass |
| `FAILED` at `ci` | Tests, Trivy (CRITICAL), gitleaks, or ACR push | Open the run; for push, check the `<env>-build` environment and AcrPush |
| `FAILED` at `deploy` | Rollout timeout, failing probes, Gateway/route, Workload Identity | `kubectl describe pod`, check `/health/ready` details; Helm rolled back automatically (`--atomic`) |
| `/health/ready` reports storage `HTTP 403` | Role assignment not yet propagated, or wrong identity client ID in the ServiceAccount | Wait a few minutes; compare the annotation with `terraform output identity_client_id` |

## Platform services

| Symptom | Check |
|---|---|
| Discovery `/readyz` 503 | Workload Identity federation (stack 30), `azure.workload.identity/use` label, `Reader` assignment |
| Orchestrator `/readyz` 503 | PostgreSQL reachability and the Entra login role (`scripts/postgres-grant-identities.sql`) |
| Orchestrator can't read GitHub App key | Key Vault per-secret assignment (`secrets_created = true`), SecretProviderClass, CSI driver pods |
| Backstage → services 401/403 | Audience/scope config (`service_auth` output of stack 10) and `SPORTIFY_ALLOWED_CALLERS` |
| Notifications not arriving | Outbox backlog (`outbox_messages` with `last_error`), Backstage `externalAccess` JWKS config |

## Useful queries (orchestrator database)

```sql
SELECT id, application_name, state, error->>'message' FROM requests ORDER BY created_at DESC LIMIT 20;
SELECT kind, status, attempts, last_error FROM steps WHERE request_id = '<id>' ORDER BY id;
SELECT at, actor, action, details FROM audit_events WHERE request_id = '<id>' ORDER BY id;
SELECT event_type, error FROM inbox_events WHERE error IS NOT NULL ORDER BY id DESC LIMIT 20;
```
