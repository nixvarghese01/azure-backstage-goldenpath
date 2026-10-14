# Platform stacks

Shared platform infrastructure, one Terraform state per stack, applied in order (ADR-0002). Changes go through `platform-plan.yml` (pull requests) and `platform-apply.yml` (behind the `platform` environment's required reviewers).

| Stack | Creates | Applied by |
|---|---|---|
| `00-bootstrap` | Terraform state storage account and `platform` / `apps` containers | A platform admin, once (local state, then migrated) |
| `05-subscriptions` | Vended subscriptions from `subscriptions.d/*.json` (EA/MCA only) | Vending identity |
| `10-identities` | All platform identities, GitHub OIDC federation, platform Key Vault and per-secret RBAC, discovery `Reader`, state access, the `IDP App Provisioner` custom role and the provisioning identity's subscription-level assignments (role definitions need an admin) | A platform admin the first time, then the platform identity |
| `20-shared-dev` | Platform and apps resource groups, shared AKS (+ `clusters.d/*.json`), ACR (+ `registries.d/*.json`), PostgreSQL, DNS, shared demo storage, role assignments | Platform identity |
| `30-cluster-config` | Kubernetes namespaces, shared Gateway, ClusterRoles/bindings, Workload Identity federation for the platform services | Platform identity |

## First-time setup

Two stacks run once from an admin's machine, because they create what the pipelines need: `00-bootstrap`
creates the Terraform state storage, and `10-identities` creates the identities the pipelines sign in
with. Everything else runs in GitHub Actions. State handling, locking and recovery are in
[terraform-state.md](../../docs/operations/terraform-state.md).

1. Copy `terraform.tfvars.example` to `terraform.tfvars` in `10-identities`, `20-shared-dev` and
   (optionally) `30-cluster-config`, and fill in your IDs. They're git-ignored; they hold IDs, not secrets.
2. Sign in with `az login --tenant <tenant id>` and `gh auth login`, then run each step and review it:

   ```bash
   scripts/bootstrap-platform.sh preflight    # read-only: sign-in, tools, providers, vCPU quota, inputs
   scripts/bootstrap-platform.sh providers    # resource providers + EncryptionAtHost
   scripts/bootstrap-platform.sh state        # 00-bootstrap, then migrate its state into itself
   scripts/bootstrap-platform.sh identities   # 10-identities
   scripts/bootstrap-platform.sh github       # repository variables and environments (IDs only)
   ```

3. Map the service identities to PostgreSQL roles once the server exists (`scripts/postgres-grant-identities.sql`).
4. **Actions → platform-provision → Run workflow** on `develop`. It applies `20-shared-dev` (AKS, ACR,
   PostgreSQL, Key Vault) and `30-cluster-config`, each after your approval of the `platform` environment,
   then runs `platform-release` to build and deploy Backstage, azure-discovery and the orchestrator into
   AKS. Pick `ttl_hours`: `platform-ttl` destroys 30 and 20 when it expires, or choose `teardown` to end
   earlier (state and identities stay). Cost and lifecycle: [demo-environment.md](../../docs/operations/demo-environment.md#5-cost-estimate-and-lifecycle).

| Pipeline | When | Identity |
|---|---|---|
| `platform-plan` | Pull requests touching `iac/`, and every Monday for drift | `platform-plan` (Reader) |
| `platform-provision` | Manually: provision or tear down the dev platform | `platform`, then `platform-deploy` |
| `platform-apply` | One stack; called by `platform-provision` or dispatched by the orchestrator | `platform` (`vending` for 05) |
| `platform-release` | Images and Helm releases; on `main` pushes, or called by `platform-provision` | `platform-deploy` |
| `platform-ttl` | Hourly: tears the dev platform down when the provision's `ttl_hours` expires | `platform-plan` to check, `platform` (teardown environment) to destroy |

The dev platform deploys from `develop`; `main` is for releases.

## Platform change requests from the orchestrator

A **Create new** AKS cluster or registry adds `clusters.d/<name>.json` or `registries.d/<name>.json` to `20-shared-<env>` through a pull request; a new subscription adds `subscriptions.d/<name>.json` to `05-subscriptions`. The stacks read these files with `fileset()`, so no HCL is generated.
