# ADR-0002: Terraform structure

- **Status:** Accepted
- **Date:** 2026-10-10

## Context

The platform manages two kinds of infrastructure with different lifecycles and owners:

- **Shared platform infrastructure**, owned by the platform team: Terraform state storage, platform identities, the shared AKS cluster, the container registry, the shared Gateway (ingress) and DNS. It changes rarely, and a mistake affects every application.
- **Application infrastructure**, owned by the application team: the resource group (if new), runtime managed identity, federated credential, namespace, role assignments, and Storage or Key Vault (if new). There is one set per application per environment, and it is created through the golden path.

Every Azure resource on the form offers **Create new** or **Select existing**. Generated code must be reviewable, identical in structure across applications, and safe for the platform to plan and apply without running user-supplied Terraform.

## Decision

### 1. Two layers, in two places

| Layer | Lives in | State | Applied by |
|---|---|---|---|
| Reusable modules | Platform repo, `iac/modules/` | None (they are libraries) | — |
| Shared platform stacks | Platform repo, `iac/platform/` | One state file per stack | Platform team's workflow (platform identity) |
| Application infrastructure | Generated repo, `infra/terraform/` | One state file per application per environment | Generated repo's workflows (provisioning identity) |

**Create new** for a subscription, AKS cluster or container registry is handled by the platform stacks, never by an application repository. The orchestrator raises a pull request in the platform repository that adds the definition, and it is applied behind the `platform` environment reviewers (see the README). An application repository always references these as existing resources.

### 2. Platform repository layout

```
iac/
├── modules/                     # reusable, versioned, each with README, examples, tests
│   ├── naming/                  # names + standard tags (no resources)
│   ├── resource-group/
│   ├── app-identity/            # user-assigned identity + federated credential(s)
│   ├── app-namespace/           # namespace, ResourceQuota, LimitRange, deployer RoleBinding
│   ├── storage-account/         # secure defaults: no shared keys, TLS 1.2+, no public blobs
│   ├── key-vault/               # RBAC mode, purge protection, soft delete
│   ├── role-assignment/         # allowlisted roles only
│   ├── aks-cluster/             # shared cluster: OIDC issuer, Workload Identity, Entra RBAC
│   ├── container-registry/
│   ├── postgresql-flexible/     # Entra-only authentication, Burstable default
│   ├── subscription-vending/    # Microsoft.Subscription alias (EA/MCA only)
│   └── github-oidc-identity/    # platform identities federated to GitHub environments
└── platform/                    # root modules ("stacks"), applied in order
    ├── 00-bootstrap/            # state storage account and containers
    ├── 05-subscriptions/        # optional subscription vending (EA/MCA billing only)
    ├── 10-identities/           # identities (backstage, discovery, orchestrator, platform,
    │                            #   platform deployment, provisioning, deployment, vending),
    │                            #   federated credentials, platform Key Vault + per-secret RBAC
    ├── 20-shared-dev/           # AKS (system pool + zonal user pool, Key Vault secrets provider
    │                            #   add-on), ACR, App Routing Gateway API, DNS zone,
    │                            #   PostgreSQL flexible server, app-provisioner role
    └── 30-cluster-config/       # in-cluster config for an EXISTING cluster: namespaces, shared
                                 #   Gateway, ClusterRoles/bindings, Workload Identity federation
                                 #   for the platform services (needs the cluster's OIDC issuer)
```

- Stacks are numbered to show their apply order, and each stack has its own state. Destroying the dev cluster stack can't touch identities or state storage.
- `00-bootstrap` starts with local state, then migrates its own state into the storage account it creates. This is the only use of local state outside tests.
- Each module contains `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `README.md`, `examples/basic/` and `tests/*.tftest.hcl`.

### 3. Generated application repository layout

```
infra/terraform/
├── versions.tf             # required_version, required_providers, backend "azurerm" {} (partial)
├── providers.tf            # azurerm (OIDC), kubernetes (AKS Entra auth through kubelogin)
├── variables.tf            # typed, validated inputs, including Create new / Select existing modes
├── main.tf                 # module calls (pinned refs) + data sources for existing resources
├── outputs.tf              # identity client ID, namespace, resource IDs: no secrets
├── .terraform.lock.hcl     # committed; provider checksums pinned
└── environments/
    └── dev/
        ├── backend.hcl         # state location only, no credentials
        └── terraform.tfvars    # rendered by the scaffolder from the form
```

- **One root module, with configuration per environment.** Every environment runs the same code. Only `terraform.tfvars` and `backend.hcl` differ, so environments can't drift in structure. Adding `test` or `prod` later means adding a directory, not copying code.
- **The scaffolder renders only `terraform.tfvars`.** The `.tf` files are static and come from the stack template. Every application's Terraform is therefore identical apart from its values, which keeps review and policy checks simple and removes any route for user-supplied HCL.
- **No local `modules/` directory by default.** It is added only if a team writes application-specific modules. Empty folders are not generated.

Commands, run from `infra/terraform/`:

```bash
terraform init -backend-config=environments/dev/backend.hcl
terraform plan -var-file=environments/dev/terraform.tfvars -out=dev.tfplan
terraform apply dev.tfplan
```

### 4. Create new or select existing in HCL

Each selectable resource is one typed variable with a `mode`:

```hcl
variable "storage" {
  type = object({
    mode = string                 # "new" | "existing"
    name = optional(string)       # required when mode = "new"
    id   = optional(string)       # required when mode = "existing"
  })
  validation {
    condition = (
      (var.storage.mode == "new" && var.storage.name != null && var.storage.id == null) ||
      (var.storage.mode == "existing" && var.storage.id != null && var.storage.name == null)
    )
    error_message = "storage: set name for mode \"new\" or id for mode \"existing\", not both."
  }
}

module "storage" {
  count  = var.storage.mode == "new" ? 1 : 0
  source = "git::https://github.com/nixvarghese01/azure-backstage-goldenpath.git//iac/modules/storage-account?ref=storage-account/v1.0.0"
  # ...
}

data "azurerm_storage_account" "existing" {
  count = var.storage.mode == "existing" ? 1 : 0
  # name and resource group parsed from var.storage.id
}

locals {
  storage_id = var.storage.mode == "new" ? module.storage[0].id : data.azurerm_storage_account.existing[0].id
}
```

- **New** resources are created by a module and carry the standard tags.
- **Existing** resources are read through `data` sources. They are never modified, imported or destroyed. The platform only adds role assignments to them.
- The same pattern applies to the resource group, namespace, Storage account and Key Vault. The subscription, AKS cluster and registry are always `data` sources in application repositories.

### 5. Module sourcing and versioning

- Application repositories use modules from the platform repository through a **Git source pinned to a module tag**, for example `?ref=app-identity/v1.2.0`. The repository is public, so no credentials are needed.
- Modules follow semantic versioning, with tags of the form `<module>/vX.Y.Z`. A breaking change means a major version, and generated repositories update through an ordinary pull request.
- A private Terraform registry was rejected for now. It adds infrastructure without adding value for a single-organisation model project.

### 6. Versions

These were checked on 2026-10-10. The full matrix and its reasons are in [COMPATIBILITY.md](../../COMPATIBILITY.md).

- Terraform `required_version = "~> 1.16.0"` (latest 1.16.5).
- `azurerm ~> 5.9`. The 5.x line has been current since 2026-07, and new code starts there rather than on 4.x.
- `kubernetes ~> 3.3`. The 3.x line has been current since 2025-12.
- `azapi ~> 2.13`, **in the platform AKS stack only**, to enable the App Routing Gateway API `ingressProfile` settings until `azurerm` supports them natively ([ADR-0003](0003-ingress-gateway-api.md)).
- `azuread ~> 3.10`, **in `10-identities` only**, for the Entra app registrations that act as token audiences for service-to-service calls (Backstage, discovery, orchestrator). Federated credentials on managed identities are `azurerm` resources and don't need it.
- `.terraform.lock.hcl` is committed, with hashes for `linux_amd64` (runners) and the developers' platforms.

### 7. State

| Item | Decision |
|---|---|
| Backend | `azurerm`, with `use_azuread_auth = true` and `use_oidc = true`. Storage account keys are disabled (`shared_access_key_enabled = false`) |
| Account | One per environment: `stsportifytfstate<env>` in `rg-sportify-tfstate-<env>` |
| Containers | `platform` (platform stacks) and `apps` (application states) |
| Keys | `platform/<stack>.tfstate`, `apps/<application>/<env>.tfstate` |
| Access | The platform identity has `Storage Blob Data Contributor` on `platform` only. The provisioning identity has it on `apps` only. Nobody else has write access |
| Protection | Blob versioning, blob and container soft delete, and a `CanNotDelete` lock on the account |
| Locking | Native blob-lease locking of the `azurerm` backend |
| Network | A public endpoint with Entra-only authentication, because GitHub-hosted runners have no fixed IP addresses. Private endpoints with self-hosted runners are the production upgrade |

State files and plan files are treated as sensitive. They are never committed or printed, and plan artifacts are kept for a short time only.

### 8. Tags and naming

The `naming` module produces every name and the standard tags, and all modules take `tags` as input:

| Tag | Example |
|---|---|
| `managed-by` | `sportify-platform` |
| `application` | `orders-api` |
| `owner` | `team-orders` |
| `environment` | `dev` |
| `request-id` | orchestrator request ID |
| `lifecycle` | `application` or `platform` |
| `repository` | `nixvarghese01/orders-api` |
| `availability-tier` | `standard` or `ha` ([ADR-0004](0004-availability-tier-option.md)) |

Cleanup relies on `managed-by` and `request-id` to find only the resources the platform created.

### 9. Kubernetes resources in Terraform

- The application's **namespace, ResourceQuota, LimitRange and deployer RoleBinding** are managed by Terraform (`app-namespace`), because they are infrastructure that has to exist before deployment.
- **Workloads** (Deployment, Service, ServiceAccount, HTTPRoute, HPA) are managed by **Helm**, not Terraform.
- The provisioning identity has a narrow cluster role, `sportify-namespace-provisioner`, limited to namespaces, quotas, limit ranges and role bindings. The deployment identity is bound only inside its application's namespace.
- The `kubernetes` provider is only ever used against an *existing* cluster, never one created in the same configuration.

### 10. Checks in CI

| Check | Tool | Where |
|---|---|---|
| Format | `terraform fmt -check -recursive` | `terraform-validate.yml` |
| Validate | `terraform init -backend=false` + `terraform validate` | `terraform-validate.yml` |
| Lint | TFLint with the `azurerm` ruleset | `terraform-validate.yml` |
| Security | Checkov (static IaC scan). Trivy is used for images and secrets, not IaC | `terraform-validate.yml` |
| Helm policy | Conftest on the rendered chart: no `Secret` objects, no secret-like env values | `terraform-validate.yml` |
| Module tests | `terraform test` using mock providers | Platform repo CI, per module |
| Plan policy | Conftest with OPA rules in `policies/terraform/`, run on `terraform show -json` output | `terraform-plan.yml` |

The plan policies deny:
- regions, SKUs or resource types that aren't allowlisted
- missing standard tags
- any update or delete of a resource without `managed-by = sportify-platform`
- any role assignment outside the role allowlist
- public network access where the module forbids it

### 11. Plan and apply

- `terraform-plan.yml` uploads `dev.tfplan`, a JSON rendering of the plan and a human-readable summary. It reports the **SHA-256 hash of the plan file** to the orchestrator.
- `terraform-apply.yml` downloads that artifact, checks that its hash matches the **approved** hash, and applies the plan file. It never re-plans.
- An approval is valid for one plan only. Any new plan needs a new approval in Backstage.

## Alternatives considered

| Option | Why not |
|---|---|
| One directory per environment, duplicating `.tf` files | Environments drift apart, and every application repository would multiply the duplication |
| Terraform workspaces for environments | Hidden state selection and easy mistakes, and it is hard to give each environment different access |
| Terragrunt | It would add a tool and a layer of indirection, and the structure above is already DRY enough for one golden path |
| Generating full HCL per request in the scaffolder | Every repository would be different, so review and policy checks would get harder and user input could end up as code |
| Application infrastructure inside the platform repository | Breaks the one-repository-per-application ownership model and mixes blast radii |
| Local modules copied into each application repository | Fixes can't be rolled out, and copies drift from the source |

## Consequences

- Application teams own a small, readable Terraform root whose values come from the form, and can upgrade modules through pull requests.
- The platform team controls security defaults in versioned modules and policy rules in one place.
- Shared infrastructure and application infrastructure have separate state, access and blast radius.
- The Entra-only public state endpoint is an accepted model-project trade-off and is documented as such.
