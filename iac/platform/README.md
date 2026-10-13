# Platform stacks

Shared platform infrastructure, one Terraform state per stack, applied in order (ADR-0002). Changes go through `platform-plan.yml` (pull requests) and `platform-apply.yml` (behind the `platform` environment's required reviewers).

| Stack | Creates | Applied by |
|---|---|---|
| `00-bootstrap` | Terraform state storage account and `platform` / `apps` containers | A platform admin, once (local state, then migrated) |
| `05-subscriptions` | Vended subscriptions from `subscriptions.d/*.json` (EA/MCA only) | Vending identity |
| `10-identities` | All platform identities, GitHub OIDC federation, platform Key Vault and per-secret RBAC, discovery `Reader`, state access | A platform admin the first time, then the platform identity |
| `20-shared-dev` | Platform and apps resource groups, shared AKS (+ `clusters.d/*.json`), ACR (+ `registries.d/*.json`), PostgreSQL, DNS, shared demo storage, role assignments | Platform identity |
| `30-cluster-config` | Kubernetes namespaces, shared Gateway, ClusterRoles/bindings, Workload Identity federation for the platform services | Platform identity |

## First-time setup (demo)

```bash
az login
# 00: local state first, then migrate into the storage account it created
cd iac/platform/00-bootstrap
terraform init && terraform apply -var-file=terraform.tfvars
cp backend.tf.example backend.tf
terraform init -migrate-state -backend-config=backend.hcl

# 10 → 20 → 30, each with its own backend.hcl and terraform.tfvars
for s in 10-identities 20-shared-dev 30-cluster-config; do
  (cd ../$s && terraform init -backend-config=backend.hcl && terraform apply -var-file=terraform.tfvars)
done

# Once: map the service identities to PostgreSQL roles
psql "host=<server>.postgres.database.azure.com dbname=postgres user=<platform-identity> sslmode=require" \
  -f ../../../scripts/postgres-grant-identities.sql
```

Copy each `terraform.tfvars.example` to `terraform.tfvars` and `backend.hcl.example` to `backend.hcl` first. Neither contains secrets, but they contain your IDs, so they stay out of the public repo unless you choose otherwise.

## Platform change requests from the orchestrator

A **Create new** AKS cluster or registry adds `clusters.d/<name>.json` or `registries.d/<name>.json` to `20-shared-<env>` through a pull request; a new subscription adds `subscriptions.d/<name>.json` to `05-subscriptions`. The stacks read these files with `fileset()`, so no HCL is generated.
